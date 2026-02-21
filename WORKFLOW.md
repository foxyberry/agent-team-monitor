# Workflow Guide

## Repository Scope Rule
- Always work inside `/Users/miyoungjang/Repository/quant/tools`.
- Do not switch to other repositories unless the user explicitly requests it.

## Default Execution Rule
- If required paths do not exist (for example `api/`, `.claude/`), create the scaffold in this repository and continue.
- Do not pause for confirmation when the intent is clear and implementation can proceed safely.

## Agent Task Tracking Epic Rule
Process child issues in this order:
1. `#2` DB model
2. `#3` Pydantic schemas
3. `#4` Service write path
4. `#5` Service read/delete path
5. `#6` Router
6. `#7` App wiring
7. `#8` Hook script
8. `#9` Hook registration
9. `#10` Validation/E2E docs

Parallelization guidance:
- Wave 1: `#2`, `#3`, `#8`
- Wave 2: `#4`, `#5`, `#9`
- Wave 3: `#6`, `#7`
- Wave 4: `#10`

## GitHub Issue Tracking Rule
- When starting an issue: add a short `start` comment.
- After implementation: add `done` comment with changed files and verification commands.
- Keep parent issue `#1` as progress index.

## PR Rule (Mandatory)
- Do not push implementation commits directly to `main`.
- Create a feature branch and open PR to `main`.
- Merge only after at least one approval and validation completion.
- Use squash merge.

PR quick flow:
```bash
git checkout -b feat/<topic>
git push -u origin feat/<topic>
gh pr create --base main --fill
```

## Validation Rule
Run at minimum:
```bash
python3 -m pip install -r requirements-api.txt
python3 -m py_compile api/main.py api/database.py api/models/agent_task.py api/services/agent_task_service.py api/routers/agent_task.py .claude/hooks/agent-task-tracker.py
python3 -m uvicorn api.main:app --port 8765
```

Smoke test:
```bash
curl -X POST http://127.0.0.1:8765/api/agent-tasks -H "Content-Type: application/json" -d '{"task_id":"test-1","subject":"Test task","status":"pending"}'
curl -X PUT http://127.0.0.1:8765/api/agent-tasks/test-1 -H "Content-Type: application/json" -d '{"task_id":"test-1","status":"completed"}'
curl http://127.0.0.1:8765/api/agent-tasks
curl http://127.0.0.1:8765/api/agent-graph
curl http://127.0.0.1:8765/api/agent-chat/rooms
curl http://127.0.0.1:8765/api/agent-presence
```

UI:
```bash
open http://127.0.0.1:8765/ui
```
