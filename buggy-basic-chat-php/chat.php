<?php
// public/chat.php

// ---- config ----
// Simple .env loader for local development.

function loadEnvValue(string $key, ?string $filePath = null): ?string {
  $filePath = $filePath ?? __DIR__ . '/.env';
  if (!is_readable($filePath)) {
    return null;
  }

  $lines = file($filePath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
  if ($lines === false) {
    return null;
  }

  foreach ($lines as $line) {
    $line = trim($line);
    if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) {
      continue;
    }

    [$k, $value] = explode('=', $line, 2);
    $k = trim($k);
    if ($k !== $key) {
      continue;
    }

    $value = trim($value);
    $value = trim($value, "'\""); // strip simple quotes
    putenv("$k=$value");
    $_ENV[$k] = $value;
    $_SERVER[$k] = $value;
    return $value;
  }

  return null;
}

// Prefer environment variable in production, but allow .env fallback locally.
$apiKey = getenv("OPENAI_API_KEY") ?: loadEnvValue("OPENAI_API_KEY");
if (!$apiKey) {
  http_response_code(500);
  header("Content-Type: text/plain");
  echo "Missing OPENAI_API_KEY env var.";
  exit;
}

// ---- SSE headers ----
header("Content-Type: text/event-stream; charset=utf-8");
header("Cache-Control: no-cache, no-transform");
header("X-Accel-Buffering: no"); // helpful for nginx
header("Connection: keep-alive");

// Disable PHP output buffering (important for streaming)
@ini_set('zlib.output_compression', '0');
@ini_set('output_buffering', '0');
@ini_set('implicit_flush', '1');
while (ob_get_level() > 0) { ob_end_flush(); }
ob_implicit_flush(true);

// Read JSON body
$raw = file_get_contents("php://input");
$body = json_decode($raw, true);
$userMessage = $body["message"] ?? "";

if (!$userMessage) {
  echo "event: error\n";
  echo "data: Missing 'message'\n\n";
  flush();
  exit;
}

// Build Responses API payload.
// NOTE: Model name may vary depending on your account and current API.
// Use a model you have access to.
$payload = [
  "model" => "gpt-4.1-mini",
  "input" => [
    [
      "role" => "user",
      "content" => [
        ["type" => "input_text", "text" => $userMessage]
      ]
    ]
  ],
  "stream" => true
];

$ch = curl_init("https://api.openai.com/v1/responses");
curl_setopt_array($ch, [
  CURLOPT_POST => true,
  CURLOPT_HTTPHEADER => [
    "Authorization: Bearer " . $apiKey,
    "Content-Type: application/json"
  ],
  CURLOPT_POSTFIELDS => json_encode($payload),
  CURLOPT_RETURNTRANSFER => false,
  CURLOPT_HEADER => false,

  // Streaming:
  CURLOPT_WRITEFUNCTION => function($ch, $data) {
    // The Responses streaming format is SSE-like lines, often with "data: {json}\n\n".
    // We'll parse lines and extract incremental text deltas if present.
    static $buffer = "";
    $buffer .= $data;

    // Process complete SSE frames separated by blank line
    while (($pos = strpos($buffer, "\n\n")) !== false) {
      $frame = substr($buffer, 0, $pos);
      $buffer = substr($buffer, $pos + 2);

      $lines = explode("\n", $frame);
      foreach ($lines as $line) {
        $line = trim($line);
        if ($line === "" || !str_starts_with($line, "data:")) continue;

        $json = trim(substr($line, 5));
        if ($json === "[DONE]") {
          echo "event: done\n";
          echo "data: ok\n\n";
          @ob_flush(); flush();
          continue;
        }

        $evt = json_decode($json, true);
        if (!$evt) continue;

        // Typical pattern: look for text delta fields in the event.
        // The exact shape can vary; we defensively search common locations.
        $text = "";

        // Option A: "type": "response.output_text.delta", delta in ["delta"]
        if (($evt["type"] ?? "") === "response.output_text.delta") {
          $text = $evt["delta"] ?? "";
        }

        // Option B: output items; try to harvest any delta-like field
        // (Keeps it resilient across minor schema changes.)
        if (!$text && isset($evt["delta"]) && is_string($evt["delta"])) {
          $text = $evt["delta"];
        }

        if ($text !== "") {
          // Emit to browser
          echo "event: token\n";
          // SSE requires no raw newlines in data lines; split if needed
          $textLines = preg_split("/\r\n|\n|\r/", $text);
          foreach ($textLines as $tl) {
            echo "data: " . $tl . "\n";
          }
          echo "\n";
          @ob_flush(); flush();
        }
      }
    }

    return strlen($data);
  },

  CURLOPT_TIMEOUT => 0,
]);

$ok = curl_exec($ch);
if ($ok === false) {
  echo "event: error\n";
  echo "data: " . curl_error($ch) . "\n\n";
  @ob_flush(); flush();
}
curl_close($ch);
