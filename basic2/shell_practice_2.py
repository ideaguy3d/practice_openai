from dotenv import load_dotenv

load_dotenv()

import asyncio
import os
from collections.abc import Sequence
from pathlib import Path

from agents import Agent, ApplyPatchTool, ItemHelpers, Runner, ShellTool, WebSearchTool
from agents import ShellCallOutcome, ShellCommandOutput, ShellCommandRequest, ShellResult
from agents.apply_diff import apply_diff
from agents.editor import ApplyPatchEditor, ApplyPatchOperation, ApplyPatchResult
from agents.mcp import MCPServerStreamableHttp

assert "OPENAI_API_KEY" in os.environ, "Please set OPENAI_API_KEY first."

workspace_dir = Path("coding-agent-workspace").resolve()
workspace_dir.mkdir(exist_ok=True)
print(f"Workspace directory: {workspace_dir}")


async def require_approval(commands: Sequence[str]) -> None:
    if os.environ.get("SHELL_AUTO_APPROVE") == "1":
        return

    print("Shell command approval required:")
    
    for entry in commands:
        print(" ", entry)
    
    response = input("Proceed? [y/N] ").strip().lower()
    
    if response not in {"y", "yes"}:
        raise RuntimeError("Shell command execution rejected by user.")


class ShellExecutor:
    def __init__(self, cwd: Path):
        self.cwd = cwd

    async def __call__(self, request: ShellCommandRequest) -> ShellResult:
        action = request.data.action
        await require_approval(action.commands)

        outputs: list[ShellCommandOutput] = []
        for command in action.commands:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=self.cwd,
                env=os.environ.copy(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            timed_out = False
            try:
                timeout = (action.timeout_ms or 0) / 1000 or None
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                stdout_bytes, stderr_bytes = await proc.communicate()
                timed_out = True

            outputs.append(
                ShellCommandOutput(
                    command=command,
                    stdout=stdout_bytes.decode("utf-8", errors="ignore"),
                    stderr=stderr_bytes.decode("utf-8", errors="ignore"),
                    outcome=ShellCallOutcome(
                        type="timeout" if timed_out else "exit",
                        exit_code=getattr(proc, "returncode", None),
                    ),
                )
            )
            if timed_out:
                break

        return ShellResult(
            output=outputs,
            provider_data={"working_directory": str(self.cwd)},
        )


class WorkspaceApplyPatchEditor(ApplyPatchEditor):
    """ApplyPatch editor constrained to workspace_dir."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def _safe_path(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError(f"Path escapes workspace: {relative_path}")
        return target

    async def create_file(self, op: ApplyPatchOperation) -> ApplyPatchResult:
        try:
            target = self._safe_path(op.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = apply_diff("", op.diff or "", mode="create")
            target.write_text(content, encoding="utf-8")
            return ApplyPatchResult(status="completed", output=f"Created {op.path}")
        except Exception as exc:
            return ApplyPatchResult(status="failed", output=str(exc))

    async def update_file(self, op: ApplyPatchOperation) -> ApplyPatchResult:
        try:
            target = self._safe_path(op.path)
            if not target.exists():
                return ApplyPatchResult(status="failed", output=f"Missing file: {op.path}")
            old = target.read_text(encoding="utf-8")
            updated = apply_diff(old, op.diff or "", mode="default")
            target.write_text(updated, encoding="utf-8")
            return ApplyPatchResult(status="completed", output=f"Updated {op.path}")
        except Exception as exc:
            return ApplyPatchResult(status="failed", output=str(exc))

    async def delete_file(self, op: ApplyPatchOperation) -> ApplyPatchResult:
        try:
            target = self._safe_path(op.path)
            if target.exists():
                target.unlink()
            return ApplyPatchResult(status="completed", output=f"Deleted {op.path}")
        except Exception as exc:
            return ApplyPatchResult(status="failed", output=str(exc))


shell_tool = ShellTool(executor=ShellExecutor(cwd=workspace_dir))
apply_patch_tool = ApplyPatchTool(editor=WorkspaceApplyPatchEditor(root=workspace_dir))

INSTRUCTIONS = """
You are a coding assistant.
Goal: build a tiny static UI demo (no Node, no package manager, no Next.js).

You MUST use tools in this order:
1) Use Context7 MCP to check current Tailwind CDN usage.
2) Use WebSearchTool once to verify a Tailwind CDN snippet.
3) Use apply_patch to create files (do not use shell redirection for file content).
4) Use shell only for quick verification commands (`ls`, `wc -l`, optional `python3 -m http.server 8000`).

Build exactly:
- index.html: Tailwind table with columns Name, Role, Status
- app.js: very basic name filter on input

Rules:
- Do not run npm, npx, pnpm, yarn, bun, node install, create-next-app, or any dependency install.
- Keep code minimal and readable.
"""

prompt = """
Create the tiny static boilerplate now.
Use context7 + web search before writing files, then use apply_patch for file creation.
"""


async def run_coding_agent_with_logs(user_prompt: str) -> None:
    print("=== Run starting ===")
    print(f"[user] {user_prompt}\n")

    headers = {}
    if os.environ.get("CONTEXT7_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['CONTEXT7_API_KEY']}"

    params = {"url": "https://mcp.context7.com/mcp"}
    if headers:
        params["headers"] = headers

    async with MCPServerStreamableHttp(name="Context7", params=params) as context7_server:
        coding_agent = Agent(
            name="Simple Frontend Agent",
            model="gpt-5.1",
            instructions=INSTRUCTIONS,
            tools=[WebSearchTool(), shell_tool, apply_patch_tool],
            mcp_servers=[context7_server],
        )

        result = Runner.run_streamed(starting_agent=coding_agent, input=user_prompt)
        async for event in result.stream_events():
            if event.type != "run_item_stream_event":
                continue

            item = event.item
            if item.type == "tool_call_item":
                raw = item.raw_item
                raw_type_name = type(raw).__name__
                if raw_type_name == "ResponseFunctionWebSearch":
                    print("[tool] web_search")
                elif raw_type_name == "LocalShellCall":
                    commands = getattr(getattr(raw, "action", None), "commands", None)
                    print(f"[tool] shell - {commands if commands else 'running command'}")
                else:
                    print(f"[tool] {raw_type_name}")
            elif item.type == "tool_call_output_item":
                output_preview = str(item.output)
                if len(output_preview) > 400:
                    output_preview = output_preview[:400] + "..."
                print(f"[tool output] {output_preview}")
            elif item.type == "message_output_item":
                text = ItemHelpers.text_message_output(item)
                print(f"[assistant]\n{text}\n")

        print("=== Run complete ===\n")
        print("Final answer:\n")
        print(result.final_output)


async def main() -> None:
    await run_coding_agent_with_logs(prompt)


if __name__ == "__main__":
    asyncio.run(main())
