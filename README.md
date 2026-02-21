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

UI:
```bash
open http://127.0.0.1:8765/ui
```

Key APIs:
- `GET /api/agent-tasks`
- `GET /api/agent-graph`
- `GET /api/agent-chat/rooms`
- `GET /api/agent-chat/messages?room_key=general`
- `GET /api/agent-presence`
- `WS /ws/office`
- `POST /api/integrations/agent-office/sync`

## Contribution Policy
- PR-only merge workflow is mandatory.
- See `CONTRIBUTING.md` and `.github/pull_request_template.md`.

Real data sync (from agent_office server):
```bash
curl -X POST http://127.0.0.1:8765/api/integrations/agent-office/sync \
  -H "Content-Type: application/json" \
  -d '{"source_url":"http://127.0.0.1:8766/api/agent-office/status"}'
```
