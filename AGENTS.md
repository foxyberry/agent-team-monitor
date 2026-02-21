# AGENTS.md

This repository root is:
- `/Users/miyoungjang/Repository/quant/tools`

Codex should treat this directory as the default project root.

## Default Working Rules
- Always run commands from this root unless a task requires a subdirectory.
- Prefer `rg`/`rg --files` for search.
- Do not modify files outside this repository unless explicitly requested.
- Validate changes with lightweight checks before finishing.

## Codex Preflight Checklist
- Git user is configured (`user.name`, `user.email`).
- Remote access works (`ssh -T git@github.com` and `git fetch`).
- Codex auth is available (`~/.codex/auth.json` or `OPENAI_API_KEY`).
- Trust level includes this repo path in `~/.codex/config.toml`.

## Agent Office
- Main server script: `agent_office/live_server.py`
- Default `--qi2-repo` now points to this repository root.
- Run example:
  - `python3 agent_office/live_server.py --port 8765`
