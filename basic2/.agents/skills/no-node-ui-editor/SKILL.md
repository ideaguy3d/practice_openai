---
name: no-node-ui-editor
description: Build or modify small static frontend UIs without Node.js or package installs. Use when requests involve HTML/CSS/vanilla JS changes and the workflow should explicitly practice Context7 MCP research, one web search verification pass, apply_patch file edits, and shell-only verification commands.
---

# No Node Ui Editor

## Overview

Build fast static UI changes while enforcing a strict tool order:
Context7 docs lookup -> web verification -> apply_patch edits -> shell verification.

## Workflow

1. Resolve the task into a static output (`index.html`, `app.js`, optional `styles.css`).
2. Use Context7 MCP first to confirm current API or framework usage.
3. Run one web search to cross-check a snippet or syntax likely to drift.
4. Read target files with shell commands (`cat`, `ls`) before editing.
5. Edit files using `apply_patch` (no shell redirection for file content).
6. Verify with quick shell checks (`ls`, `wc -l`, optional `python3 -m http.server`).
7. Return changed files, verification commands, and manual browser checks.

## Guardrails

- Never run `npm`, `npx`, `pnpm`, `yarn`, `bun`, `node install`, or `create-next-app`.
- Never write file contents through shell heredocs or redirection.
- Keep dependencies zero unless the user explicitly asks to add them.
- Keep code minimal, readable, and easy to run locally.

## Output Contract

- List every changed file path.
- Show exact local run commands.
- Give 2-4 manual verification checks.
- If blocked, report the failing tool step and the smallest unblocking action.

## Prompt Templates

Use one of the templates in `references/prompt-templates.md` and adapt it to the user request.
