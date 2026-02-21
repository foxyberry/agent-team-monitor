# agent-team-monitor

## Codex Setup (Project Root)
- Root: `/Users/miyoungjang/Repository/quant/tools`
- Project instructions: `AGENTS.md`
- Execution workflow: `WORKFLOW.md`
- Agent Office server: `agent_office/live_server.py`

## Quick Start
```bash
cd /Users/miyoungjang/Repository/quant/tools
python3 agent_office/live_server.py --port 8765
```

## Basic Checks
```bash
git config user.name
git config user.email
git fetch
```

## Agent Task API
Install:
```bash
cd /Users/miyoungjang/Repository/quant/tools
python3 -m pip install -r requirements-api.txt
```

Run:
```bash
python3 -m uvicorn api.main:app --port 8765
```
