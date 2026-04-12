# Prompt Templates

## Template 1: Small UI Feature

Use Context7 MCP to confirm any API syntax first, then run one web search to verify.
Read existing files with shell, then use apply_patch only for edits.
Add [FEATURE] to [FILE_PATHS] with no Node or package installs.
After edits, run only lightweight verification commands and list manual browser checks.

## Template 2: Bug Fix

Use Context7 MCP to check relevant docs, then one web search to verify edge-case behavior.
Inspect files with shell and patch with apply_patch.
Fix [BUG] in [FILE_PATHS], keep changes minimal, avoid dependency installs, and provide test steps.

## Template 3: Responses API Add-On

Use Context7 MCP to confirm latest OpenAI Responses API usage, then one web search verification.
Patch files to add a summarize flow for [DATA_SOURCE] using model [MODEL_NAME].
Do not use Node/package managers unless explicitly requested.
Provide run commands and manual verification steps.
