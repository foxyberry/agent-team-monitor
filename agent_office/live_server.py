#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class AgentDef:
    agent_id: str
    dirs: tuple[str, ...]


AGENTS: tuple[AgentDef, ...] = (
    AgentDef("chief", ("api/", "web/", "engine/", "portfolio/", "scripts/", "docs/", "tests/")),
    AgentDef("planner", ("docs/works/",)),
    AgentDef("designer", ("web/",)),
    AgentDef("quant", ("engine/", "discovery/", "screener/")),
    AgentDef("data", ("pipeline/", "data_enrichment/", "news/", "models/", "llm/")),
    AgentDef("portfolio", ("portfolio/",)),
    AgentDef("server", ("api/",)),
    AgentDef("frontend", ("web/",)),
    AgentDef("qa", ("tests/", "api/tests/")),
)

PROJECTS = (
    {
        "id": "qi1",
        "name": "quant-investment",
        "roomName": "개발1실",
        "color": "#6366f1",
        "bgColor": "rgba(99,102,241,0.15)",
    },
    {
        "id": "qi2",
        "name": "quant-investment2",
        "roomName": "개발2실",
        "color": "#f59e0b",
        "bgColor": "rgba(245,158,11,0.15)",
    },
)

STATUS_COLOR = {
    "active": "#22c55e",
    "waiting_input": "#38bdf8",
    "working": "#f59e0b",
    "idle": "#6b7280",
    "sleeping": "#374151",
}
STATUS_LABEL = {
    "active": "Active",
    "waiting_input": "Waiting",
    "working": "Working",
    "idle": "Idle",
    "sleeping": "Sleeping",
}
RATE_LIMIT_TS_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z).*(rate_limit_error|would exceed your account's rate limit)"
)
ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")
BASH_BLOCK_RE = re.compile(r"Bash\((?P<cmd>.*?)\)", re.DOTALL)
SECRET_RE = re.compile(r"(?i)(api[-_]?key|token|secret|password)\s*[:=]\s*([^\s\"']+)")
FORKED_USAGE_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}T[0-9:.]+Z).+Forked agent \[(?P<agent>[^\]]+)\] finished:.*totalUsage: input=(?P<input>\d+) output=(?P<output>\d+)"
)
BG_DONE_RE = re.compile(r'Background command "(?P<label>[^"]+)" completed \(exit code (?P<code>-?\d+)\)')
AGENT_DONE_RE = re.compile(r'Agent "(?P<label>[^"]+)" completed')
PR_LINK_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
BULLET_NOTE_RE = re.compile(r"[⏺•]\s+(?P<msg>.+)")
QI1_PATH_RE = re.compile(r"/quant/quant-investment(?:/|$)")
QI2_PATH_RE = re.compile(r"/quant/quant-investment2(?:/|$)")
MCP_RUNNING_RE = re.compile(r"""MCP server "codex": Tool '(?:codex|codex-reply)' still running""")
MCP_DONE_RE = re.compile(r"""MCP server "codex": Tool '(?:codex|codex-reply)' completed successfully""")
MCP_FAIL_RE = re.compile(r"""MCP server "codex": Tool '(?:codex|codex-reply)' failed after""")

EVENT_WEIGHT: dict[str, float] = {
    "bash": 5.0,
    "stream_chunk": 4.0,
    "forked_usage": 4.0,
    "tool_running": 3.0,
    "query_input": 2.0,
    "tool_done": 1.5,
    "tool_failed": 1.0,
}


def run_git(repo: Path, args: list[str]) -> str:
    cmd = ["git", "-C", str(repo), *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        return ""
    return proc.stdout.strip()


def branch_name(repo: Path) -> str:
    out = run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    return out or "unknown"


def count_commits(repo: Path, days: int, dirs: tuple[str, ...]) -> int:
    out = run_git(
        repo,
        ["rev-list", "--count", "--since", f"{days}.days", "HEAD", "--", *dirs],
    )
    return int(out) if out.isdigit() else 0


def tracked_files(repo: Path, dirs: tuple[str, ...]) -> int:
    out = run_git(repo, ["ls-files", "--", *dirs])
    if not out:
        return 0
    return len([line for line in out.splitlines() if line.strip()])


def last_active(repo: Path, dirs: tuple[str, ...]) -> str | None:
    out = run_git(repo, ["log", "-n", "1", "--pretty=format:%cI", "--", *dirs])
    return out or None


def has_uncommitted_changes(repo: Path, dirs: tuple[str, ...]) -> bool:
    out = run_git(repo, ["status", "--porcelain", "--", *dirs])
    return bool(out.strip())


def files_changed_for_commit(repo: Path, commit_hash: str, dirs: tuple[str, ...]) -> int:
    out = run_git(repo, ["show", "--pretty=format:", "--name-only", commit_hash, "--", *dirs])
    if not out:
        return 0
    return len([line for line in out.splitlines() if line.strip()])


def recent_activity(repo: Path, dirs: tuple[str, ...], limit: int = 2) -> list[dict[str, Any]]:
    fmt = "%h%x1f%cI%x1f%s"
    out = run_git(repo, ["log", f"-n{limit}", f"--pretty=format:{fmt}", "--", *dirs])
    acts: list[dict[str, Any]] = []
    if not out:
        return acts
    for row in out.splitlines():
        parts = row.split("\x1f")
        if len(parts) != 3:
            continue
        short_hash, date_iso, message = parts
        acts.append(
            {
                "hash": short_hash,
                "message": message,
                "date": date_iso,
                "files_changed": files_changed_for_commit(repo, short_hash, dirs),
            }
        )
    return acts


def parse_iso(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def state_from_last_active(last_active_iso: str | None, now_utc: datetime) -> str:
    dt = parse_iso(last_active_iso)
    if dt is None:
        return "sleeping"

    age = now_utc - dt.astimezone(timezone.utc)
    if age <= timedelta(minutes=20):
        return "active"
    if age <= timedelta(hours=2):
        return "waiting_input"
    if age <= timedelta(days=3):
        return "working"
    if age <= timedelta(days=14):
        return "idle"
    return "sleeping"


def detect_claude_rate_limit(now_utc: datetime) -> dict[str, Any]:
    debug_dir = Path.home() / ".claude" / "debug"
    if not debug_dir.exists():
        return {"is_limited": False, "last_hit_at": None}

    candidates = sorted(
        [p for p in debug_dir.glob("*.txt") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:8]
    newest_hit: datetime | None = None

    for path in candidates:
        try:
            with path.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(size - 220_000, 0))
                tail = f.read().decode("utf-8", errors="ignore")
        except OSError:
            continue

        for m in RATE_LIMIT_TS_RE.finditer(tail):
            dt = parse_iso(m.group(1))
            if dt is None:
                continue
            dt_utc = dt.astimezone(timezone.utc)
            if newest_hit is None or dt_utc > newest_hit:
                newest_hit = dt_utc

    if newest_hit is None:
        return {"is_limited": False, "last_hit_at": None}

    is_limited = (now_utc - newest_hit) <= timedelta(hours=6)
    return {"is_limited": is_limited, "last_hit_at": newest_hit.isoformat()}


def detect_claude_code_state(now_utc: datetime, is_limited: bool) -> dict[str, Any]:
    debug_dir = Path.home() / ".claude" / "debug"
    newest_seen: datetime | None = None

    if debug_dir.exists():
        for p in debug_dir.glob("*.txt"):
            try:
                dt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if newest_seen is None or dt > newest_seen:
                newest_seen = dt

    if is_limited:
        return {
            "state": "waiting_input",
            "label": "Limited",
            "color": "#f87171",
            "last_active": newest_seen.isoformat() if newest_seen else None,
        }
    if newest_seen is None:
        return {"state": "idle", "label": "Idle", "color": STATUS_COLOR["idle"], "last_active": None}

    age = now_utc - newest_seen
    if age <= timedelta(minutes=3):
        state = "active"
    elif age <= timedelta(minutes=20):
        state = "waiting_input"
    elif age <= timedelta(hours=4):
        state = "working"
    else:
        state = "idle"

    return {
        "state": state,
        "label": STATUS_LABEL[state],
        "color": STATUS_COLOR[state],
        "last_active": newest_seen.isoformat(),
    }


def sanitize_command(cmd: str) -> str:
    s = " ".join(cmd.strip().split())
    s = SECRET_RE.sub(r"\1=***", s)
    s = re.sub(r"(?i)(bearer\s+)[a-z0-9._-]+", r"\1***", s)
    return s[:220]


def infer_cmd_status(context: str) -> tuple[str, str]:
    lower = context.lower()
    if "running in the background" in lower or "running" in lower:
        return ("running", "Running")
    if "failed" in lower or "error" in lower:
        return ("failed", "Failed")
    return ("done", "Done")


def parse_recent_commands(now_utc: datetime, limit: int = 10) -> list[dict[str, Any]]:
    debug_dir = Path.home() / ".claude" / "debug"
    if not debug_dir.exists():
        return []

    files = sorted(
        [p for p in debug_dir.glob("*.txt") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:8]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for path in files:
        try:
            with path.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(size - 300_000, 0))
                text = f.read().decode("utf-8", errors="ignore")
        except OSError:
            continue

        file_ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        for m in BASH_BLOCK_RE.finditer(text):
            cmd = sanitize_command(m.group("cmd"))
            if not cmd:
                continue
            post = text[m.end() : m.end() + 280]
            status, label = infer_cmd_status(post)
            ts_match = ISO_TS_RE.search(text[max(0, m.start() - 220) : m.start()])
            ts = parse_iso(ts_match.group(0)).isoformat() if ts_match and parse_iso(ts_match.group(0)) else file_ts
            dedupe = (cmd, status)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            rows.append(
                {
                    "cmd": cmd,
                    "status": status,
                    "label": label,
                    "time": ts,
                    "source": path.name,
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def parse_recent_runtime_notes(now_utc: datetime, repo_map: dict[str, Path], limit: int = 12) -> list[dict[str, Any]]:
    debug_dir = Path.home() / ".claude" / "debug"
    if not debug_dir.exists():
        return []
    repo_markers = {k: str(v).replace("\\", "/") for k, v in repo_map.items()}

    files = sorted(
        [p for p in debug_dir.glob("*.txt") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:10]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for path in files:
        try:
            with path.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(size - 500_000, 0))
                text = f.read().decode("utf-8", errors="ignore")
        except OSError:
            continue

        file_ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        file_repo = "unknown"
        hit_len = -1
        for key, marker in repo_markers.items():
            if marker and marker in text and len(marker) > hit_len:
                file_repo = key
                hit_len = len(marker)
        for ln in text.splitlines():
            repo = "unknown"
            hit_len = -1
            for key, marker in repo_markers.items():
                if marker and marker in ln and len(marker) > hit_len:
                    repo = key
                    hit_len = len(marker)
            if repo == "unknown":
                repo = file_repo
            ts_m = ISO_TS_RE.search(ln)
            ts = parse_iso(ts_m.group(0)).isoformat() if ts_m and parse_iso(ts_m.group(0)) else file_ts
            msg = ""
            kind = "note"

            bg = BG_DONE_RE.search(ln)
            if bg:
                code = int(bg.group("code"))
                state = "완료" if code == 0 else f"실패({code})"
                msg = f'Background "{bg.group("label")}" {state}'
                kind = "background"

            ag = AGENT_DONE_RE.search(ln)
            if ag:
                msg = f'Agent "{ag.group("label")}" completed'
                kind = "agent"

            if not msg and ("PR #" in ln or "pull/" in ln):
                pr = PR_LINK_RE.search(ln)
                if pr:
                    msg = f"PR update: {pr.group(0)}"
                    kind = "pr"

            if not msg:
                b = BULLET_NOTE_RE.search(ln)
                if b:
                    bmsg = b.group("msg").strip().strip('"')
                    low = bmsg.lower()
                    if bmsg.startswith("Background command") or "background" in low:
                        kind = "background"
                    elif bmsg.startswith("Agent ") or "agent " in low:
                        kind = "agent"
                    elif "pull/" in low or "pr #" in low:
                        kind = "pr"
                    elif "lgtm" in low or "review" in low:
                        kind = "review"
                    else:
                        kind = "note"
                    msg = bmsg[:260]

            if not msg:
                if "all work" in ln.lower() and "complete" in ln.lower():
                    msg = "All work complete update"
                    kind = "summary"
                elif "lgtm" in ln.lower():
                    msg = "Review LGTM update"
                    kind = "review"

            if not msg:
                continue
            dedupe = f"{repo}:{kind}:{msg}"
            if dedupe in seen:
                continue
            seen.add(dedupe)
            rows.append({"repo": repo, "kind": kind, "message": msg, "time": ts, "source": path.name})
            if len(rows) >= limit:
                return rows

    rows.sort(key=lambda r: r.get("time", ""), reverse=True)
    return rows[:limit]


def detect_repo_key(text: str, repo_markers: dict[str, str] | None = None) -> str:
    if repo_markers:
        hit: str | None = None
        hit_len = -1
        for key, marker in repo_markers.items():
            if marker and marker in text and len(marker) > hit_len:
                hit = key
                hit_len = len(marker)
        if hit:
            return hit
    # Check qi2 first because qi1 is a prefix of qi2.
    if QI2_PATH_RE.search(text):
        return "qi2"
    if QI1_PATH_RE.search(text):
        return "qi1"
    return "unknown"


def score_decay(age_sec: float) -> float:
    if age_sec <= 120:
        return 1.0
    if age_sec <= 600:
        return 0.6
    if age_sec <= 1800:
        return 0.3
    if age_sec <= 3600:
        return 0.1
    return 0.0


def infer_runtime_state(
    now_utc: datetime,
    score: float,
    last_event_at: str | None,
    token_rate_10m: float,
    waiting_reason: str,
) -> tuple[str, str]:
    if waiting_reason in ("rate_limit", "user_reply"):
        return ("waiting_input", "high")
    dt = parse_iso(last_event_at)
    if dt is None:
        return ("sleeping", "low")
    age_sec = max(0.0, (now_utc - dt.astimezone(timezone.utc)).total_seconds())
    if age_sec <= 120 and (score >= 6.0 or token_rate_10m >= 120.0):
        return ("active", "high")
    if age_sec <= 600 and score >= 2.0:
        return ("working", "medium")
    if age_sec <= 1800 and score >= 1.0:
        return ("working", "low")
    if age_sec <= 86400:
        return ("idle", "low")
    return ("sleeping", "low")


def detect_agent_for_repo_line(text: str, repo_path: Path) -> str | None:
    lower = text.lower()
    repo_s = str(repo_path).replace("\\", "/")
    marker_idx = lower.find(repo_s.lower())
    if marker_idx < 0:
        return None
    rel = lower[marker_idx + len(repo_s) :].lstrip("/")
    if not rel:
        return None
    for agent in AGENTS:
        for d in agent.dirs:
            prefix = d.lower().lstrip("/")
            if rel.startswith(prefix):
                return agent.agent_id
    return None


def parse_runtime_event_type(line: str) -> tuple[str, int]:
    if "Bash(" in line:
        return ("bash", 0)
    if "Stream started - received first chunk" in line:
        return ("stream_chunk", 0)
    if "Query.streamInput" in line:
        return ("query_input", 0)
    if MCP_RUNNING_RE.search(line):
        return ("tool_running", 0)
    if MCP_DONE_RE.search(line):
        return ("tool_done", 0)
    if MCP_FAIL_RE.search(line):
        return ("tool_failed", 0)
    m = FORKED_USAGE_RE.search(line)
    if m:
        return ("forked_usage", int(m.group("input")) + int(m.group("output")))
    return ("", 0)


def build_token_series(now_utc: datetime, token_events: list[dict[str, Any]]) -> dict[str, Any]:
    series_1m = [0 for _ in range(30)]
    for ev in token_events:
        tok = int(ev.get("token_inc", 0))
        if tok <= 0:
            continue
        ts = parse_iso(str(ev.get("time"))) if ev.get("time") else None
        if ts is None:
            continue
        age_sec = (now_utc - ts.astimezone(timezone.utc)).total_seconds()
        if age_sec < 0 or age_sec >= 1800:
            continue
        idx = int(age_sec // 60)
        bucket = 29 - idx
        if 0 <= bucket < 30:
            series_1m[bucket] += tok

    series_5m = [sum(series_1m[i * 5 : (i + 1) * 5]) for i in range(6)]
    series_10m = [sum(series_1m[i * 10 : (i + 1) * 10]) for i in range(3)]
    return {
        "token_series_1m": series_1m,
        "token_series_5m": series_5m,
        "token_series_10m": series_10m,
        "token_series_updated_at": now_utc.isoformat(),
    }


def parse_runtime_telemetry(now_utc: datetime, repo_map: dict[str, Path], is_limited: bool) -> dict[str, Any]:
    debug_dir = Path.home() / ".claude" / "debug"
    repo_markers = {k: str(v).replace("\\", "/") for k, v in repo_map.items()}
    blank_project = {
        "active_commands": 0,
        "last_command": "",
        "last_seen": None,
        "observed_tokens": 0,
        "token_rate_10m": 0.0,
        "session_total_tokens": 0,
        "signal": "none",
        "score": 0.0,
        "state": "sleeping",
        "confidence": "low",
        "last_event_at": None,
        "last_event_type": "none",
        "waiting_reason": "none",
        "evidence": [],
        "token_series_1m": [0 for _ in range(30)],
        "token_series_5m": [0 for _ in range(6)],
        "token_series_10m": [0 for _ in range(3)],
        "token_series_updated_at": now_utc.isoformat(),
    }
    if not debug_dir.exists():
        return {
            "projects": {
                "qi1": dict(blank_project),
                "qi2": dict(blank_project),
            },
            "agents": {"qi1": {}, "qi2": {}},
            "events": [],
            "forked_agents": [],
        }

    files = sorted(
        [p for p in debug_dir.glob("*.txt") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:10]
    project_state = {"qi1": dict(blank_project), "qi2": dict(blank_project)}
    runtime_agents: dict[str, dict[str, Any]] = {"qi1": {}, "qi2": {}}
    usage: dict[tuple[str, str], dict[str, Any]] = {}
    token_10m: dict[str, int] = {"qi1": 0, "qi2": 0}
    event_rows: list[dict[str, Any]] = []

    for path in files:
        try:
            with path.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(size - 350_000, 0))
                text = f.read().decode("utf-8", errors="ignore")
        except OSError:
            continue

        file_repo_key = detect_repo_key(text, repo_markers)
        lines = text.splitlines()[-2000:]

        for ln in lines:
            repo_key = detect_repo_key(ln, repo_markers)
            if repo_key == "unknown":
                repo_key = file_repo_key
            if repo_key not in ("qi1", "qi2"):
                continue
            ts_m = ISO_TS_RE.search(ln)
            ts_dt = parse_iso(ts_m.group(0)) if ts_m else None
            if ts_dt is None:
                ts_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            event_type, token_inc = parse_runtime_event_type(ln)
            if not event_type:
                continue

            age_sec = max(0.0, (now_utc - ts_dt.astimezone(timezone.utc)).total_seconds())
            score_gain = EVENT_WEIGHT.get(event_type, 1.0) * score_decay(age_sec)
            st = project_state[repo_key]
            st["score"] += score_gain
            if st["last_event_at"] is None or ts_dt.isoformat() > str(st["last_event_at"]):
                st["last_event_at"] = ts_dt.isoformat()
                st["last_event_type"] = event_type
                st["last_seen"] = ts_dt.isoformat()
            if len(st["evidence"]) < 3:
                st["evidence"].append(f"{event_type} · {ts_dt.strftime('%H:%M:%S')} · {ln[:72]}")

            if event_type == "bash":
                st["active_commands"] += 1 if age_sec <= 600 else 0
                m = BASH_BLOCK_RE.search(ln)
                if m:
                    st["last_command"] = sanitize_command(m.group("cmd"))

            st["session_total_tokens"] += token_inc
            st["observed_tokens"] += token_inc
            if age_sec <= 600:
                token_10m[repo_key] += token_inc

            agent_id = detect_agent_for_repo_line(ln, repo_map[repo_key])
            if agent_id:
                bucket = runtime_agents[repo_key].setdefault(
                    agent_id,
                    {
                        "score": 0.0,
                        "last_event_at": None,
                        "last_event_type": "none",
                        "last_command": "",
                        "active_commands": 0,
                        "token_10m": 0,
                        "session_total_tokens": 0,
                        "evidence": [],
                    },
                )
                bucket["score"] += score_gain
                bucket["session_total_tokens"] += token_inc
                if age_sec <= 600:
                    bucket["token_10m"] += token_inc
                if event_type == "bash" and age_sec <= 600:
                    bucket["active_commands"] += 1
                if event_type == "bash":
                    m = BASH_BLOCK_RE.search(ln)
                    if m:
                        bucket["last_command"] = sanitize_command(m.group("cmd"))
                if bucket["last_event_at"] is None or ts_dt.isoformat() > str(bucket["last_event_at"]):
                    bucket["last_event_at"] = ts_dt.isoformat()
                    bucket["last_event_type"] = event_type
                if len(bucket["evidence"]) < 2:
                    bucket["evidence"].append(f"{event_type}@{ts_dt.strftime('%H:%M:%S')}")

            event_rows.append(
                {
                    "repo": repo_key,
                    "agent": agent_id if agent_id else "",
                    "type": event_type,
                    "time": ts_dt.isoformat(),
                    "token_inc": token_inc,
                }
            )

        # Forked-agent token usage for grouped display.
        for ln in lines:
            m = FORKED_USAGE_RE.search(ln)
            if not m:
                continue
            repo_key = detect_repo_key(ln, repo_markers)
            if repo_key == "unknown":
                repo_key = file_repo_key
            ag = m.group("agent")
            key = (repo_key, ag)
            if key not in usage:
                usage[key] = {
                    "repo": repo_key,
                    "agent": ag,
                    "events": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "last_time": None,
                }
            row = usage[key]
            row["events"] += 1
            in_tok = int(m.group("input"))
            out_tok = int(m.group("output"))
            row["input_tokens"] += in_tok
            row["output_tokens"] += out_tok
            ts = parse_iso(m.group("ts"))
            if ts:
                cur = parse_iso(row["last_time"]) if row["last_time"] else None
                if cur is None or ts > cur:
                    row["last_time"] = ts.isoformat()

    for key in ("qi1", "qi2"):
        st = project_state[key]
        series = build_token_series(now_utc, [r for r in event_rows if r.get("repo") == key])
        st.update(series)
        st["token_rate_10m"] = float(token_10m[key]) / 10.0
        waiting_reason = "rate_limit" if is_limited else "none"
        state, conf = infer_runtime_state(now_utc, float(st["score"]), st["last_event_at"], st["token_rate_10m"], waiting_reason)
        st["state"] = state
        st["confidence"] = conf
        st["waiting_reason"] = waiting_reason
        if state == "active":
            st["signal"] = "high"
        elif state == "working":
            st["signal"] = "medium"
        elif state == "waiting_input":
            st["signal"] = "medium"
        elif st["last_seen"]:
            st["signal"] = "low"
        else:
            st["signal"] = "none"

        for agent_id, row in runtime_agents[key].items():
            rate = float(row["token_10m"]) / 10.0
            a_state, a_conf = infer_runtime_state(now_utc, float(row["score"]), row["last_event_at"], rate, waiting_reason)
            a_series = build_token_series(
                now_utc,
                [r for r in event_rows if r.get("repo") == key and r.get("agent") == agent_id],
            )
            row.update(a_series)
            row["state"] = a_state
            row["confidence"] = a_conf
            row["token_rate_10m"] = rate
            row["waiting_reason"] = waiting_reason

    forked = sorted(
        usage.values(),
        key=lambda r: (r["repo"], -(r["input_tokens"] + r["output_tokens"])),
    )
    return {"projects": project_state, "agents": runtime_agents, "events": event_rows[-100:], "forked_agents": forked[:20]}


def apply_rate_limit_override(status_data: dict[str, Any]) -> None:
    agents = status_data.get("agents", {})
    for agent in agents.values():
        state = agent.get("status", {}).get("state")
        if state in ("active", "working", "waiting_input"):
            agent["status"] = {"state": "idle", "label": STATUS_LABEL["idle"], "color": STATUS_COLOR["idle"]}

    summary = {"total_agents": len(AGENTS), "active": 0, "waiting_input": 0, "working": 0, "idle": 0, "sleeping": 0}
    for agent in agents.values():
        s = agent.get("status", {}).get("state", "sleeping")
        if s not in summary:
            s = "sleeping"
        summary[s] += 1
    status_data["summary"] = summary


def recalc_summary(status_data: dict[str, Any]) -> None:
    agents = status_data.get("agents", {})
    summary = {"total_agents": len(AGENTS), "active": 0, "waiting_input": 0, "working": 0, "idle": 0, "sleeping": 0}
    for agent in agents.values():
        s = agent.get("status", {}).get("state", "sleeping")
        if s not in summary:
            s = "sleeping"
        summary[s] += 1
    status_data["summary"] = summary


def enrich_chief_activity(status_data: dict[str, Any], now_utc: datetime, project_name: str, is_limited: bool) -> None:
    agents = status_data.get("agents", {})
    chief = agents.get("chief")
    if not chief:
        return

    summary = status_data.get("summary", {})
    waiting_count = int(summary.get("waiting_input", 0))
    active_count = int(summary.get("active", 0))
    working_count = int(summary.get("working", 0))

    if is_limited:
        chief_state = "waiting_input"
        msg = "Claude limit 감지, 팀 작업을 일시 점검 중"
    elif waiting_count > 0:
        chief_state = "waiting_input"
        msg = f"사용자 응답 대기 {waiting_count}건 확인, 우선순위 정리 중"
    elif active_count + working_count > 0:
        chief_state = "active"
        msg = f"{project_name} 작업자 {active_count + working_count}명 조율 중"
    else:
        chief_state = "working"
        msg = "다음 작업 큐와 리뷰 순서를 정리 중"

    now_iso = now_utc.isoformat()
    chief["status"] = {"state": chief_state, "label": STATUS_LABEL[chief_state], "color": STATUS_COLOR[chief_state]}
    chief["last_active"] = now_iso
    chief["recent_activity"] = [
        {"hash": "chief", "message": msg, "date": now_iso, "files_changed": 0},
    ]
    recalc_summary(status_data)


def pick_claude_current_task(projects_payload: list[dict[str, Any]], runtime: dict[str, Any], is_limited: bool) -> str:
    if is_limited:
        return "Claude limit 감지, 요청 대기 및 작업 재배치 중"

    runtime_projects = runtime.get("projects", {}) if isinstance(runtime, dict) else {}
    active_projects: list[tuple[int, str]] = []
    for proj in projects_payload:
        pid = str(proj.get("id", ""))
        rp = runtime_projects.get(pid, {})
        if str(rp.get("state")) in ("active", "working") and rp.get("last_command"):
            active_projects.append((int(rp.get("active_commands", 0)), f"{proj.get('name')}: {rp.get('last_command')}"))
    if active_projects:
        active_projects.sort(key=lambda x: x[0], reverse=True)
        return active_projects[0][1]

    candidates: list[str] = []
    for proj in projects_payload:
        agents = proj.get("statusData", {}).get("agents", {})
        chief = agents.get("chief", {})
        acts = chief.get("recent_activity", [])
        if acts and acts[0].get("message"):
            candidates.append(str(acts[0]["message"]))

    if not candidates:
        return "진행 중인 조율 작업 없음"

    waiting = [msg for msg in candidates if "응답 대기" in msg]
    if waiting:
        return waiting[0]
    return candidates[0]


def build_agent_status(repo: Path, now_utc: datetime, runtime_agent_map: dict[str, Any], project_runtime: dict[str, Any]) -> dict[str, Any]:
    agents: dict[str, Any] = {}
    summary = {"total_agents": len(AGENTS), "active": 0, "waiting_input": 0, "working": 0, "idle": 0, "sleeping": 0}

    for agent in AGENTS:
        c7 = count_commits(repo, 7, agent.dirs)
        c30 = count_commits(repo, 30, agent.dirs)
        files = tracked_files(repo, agent.dirs)
        last = last_active(repo, agent.dirs)
        dirty = has_uncommitted_changes(repo, agent.dirs)
        runtime_row = runtime_agent_map.get(agent.agent_id, {})
        runtime_state = runtime_row.get("state")

        if runtime_state in STATUS_LABEL:
            state = str(runtime_state)
            source = "runtime"
        elif dirty:
            state = "working"
            source = "dirty"
        else:
            proj_state = str(project_runtime.get("state", "idle"))
            state = "idle" if proj_state in ("active", "working", "waiting_input") else "sleeping"
            source = "fallback"

        summary[state] += 1

        runtime_status = {
            "state": runtime_row.get("state", state),
            "confidence": runtime_row.get("confidence", "low"),
            "score": float(runtime_row.get("score", 0.0)),
            "last_signal_at": runtime_row.get("last_event_at"),
            "last_event_type": runtime_row.get("last_event_type", "none"),
            "last_command": runtime_row.get("last_command", ""),
            "token_rate_10m": float(runtime_row.get("token_rate_10m", 0.0)),
            "session_total_tokens": int(runtime_row.get("session_total_tokens", 0)),
            "active_command_count": int(runtime_row.get("active_commands", 0)),
            "waiting_reason": runtime_row.get("waiting_reason", "none"),
            "evidence": runtime_row.get("evidence", []),
            "token_series_1m": runtime_row.get("token_series_1m", [0 for _ in range(30)]),
            "token_series_5m": runtime_row.get("token_series_5m", [0 for _ in range(6)]),
            "token_series_10m": runtime_row.get("token_series_10m", [0 for _ in range(3)]),
            "token_series_updated_at": runtime_row.get("token_series_updated_at"),
            "source": source,
        }

        agents[agent.agent_id] = {
            "status": {"state": state, "label": STATUS_LABEL[state], "color": STATUS_COLOR[state]},
            "runtime_status": runtime_status,
            "stats": {
                "commits_7d": c7,
                "commits_30d": c30,
                "files_tracked": files,
                "dirty": dirty,
                "tokens_10m": runtime_status["token_rate_10m"],
                "tokens_session": runtime_status["session_total_tokens"],
            },
            "last_active": last,
            "recent_activity": recent_activity(repo, agent.dirs, limit=2),
        }

    return {"agents": agents, "summary": summary}


def build_payload(repo_map: dict[str, Path]) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    rate_limit = detect_claude_rate_limit(now_utc)
    claude_code = detect_claude_code_state(now_utc, rate_limit["is_limited"])
    recent_commands = parse_recent_commands(now_utc, limit=10)
    recent_notes = parse_recent_runtime_notes(now_utc, repo_map, limit=12)
    runtime = parse_runtime_telemetry(now_utc, repo_map, rate_limit["is_limited"])
    projects_payload: list[dict[str, Any]] = []

    for proj in PROJECTS:
        proj_id = str(proj["id"])
        repo = repo_map[proj["id"]]
        runtime_agents = runtime.get("agents", {}).get(proj_id, {})
        runtime_project = runtime.get("projects", {}).get(proj_id, {})
        status_data = build_agent_status(repo, now_utc, runtime_agents, runtime_project)
        enrich_chief_activity(status_data, now_utc, proj["name"], rate_limit["is_limited"])
        status_data["generated_at"] = now_utc.isoformat()
        status_data["project_runtime"] = runtime_project
        projects_payload.append(
            {
                "id": proj["id"],
                "name": proj["name"],
                "roomName": proj["roomName"],
                "color": proj["color"],
                "bgColor": proj["bgColor"],
                "branch": branch_name(repo),
                "statusData": status_data,
            }
        )

    claude_code["current_task"] = pick_claude_current_task(projects_payload, runtime, rate_limit["is_limited"])

    return {
        "generated_at": now_utc.isoformat(),
        "projects": projects_payload,
        "claude_limit": rate_limit,
        "claude_code": claude_code,
        "recent_commands": recent_commands,
        "recent_notes": recent_notes,
        "runtime": runtime,
    }


def make_handler(html_path: Path, repo_map: dict[str, Path]):
    assets_root = html_path.parent / "assets"

    def content_type_for(path: Path) -> str:
        ext = path.suffix.lower()
        if ext == ".svg":
            return "image/svg+xml"
        if ext == ".ico":
            return "image/x-icon"
        if ext == ".png":
            return "image/png"
        if ext == ".js":
            return "application/javascript; charset=utf-8"
        if ext == ".css":
            return "text/css; charset=utf-8"
        return "application/octet-stream"

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                try:
                    html = html_path.read_bytes()
                except OSError as exc:
                    self._send(500, f"Failed to read HTML: {exc}".encode(), "text/plain; charset=utf-8")
                    return
                self._send(200, html, "text/html; charset=utf-8")
                return

            if path.startswith("/assets/"):
                rel = path[len("/assets/") :]
                target = (assets_root / rel).resolve()
                try:
                    target.relative_to(assets_root.resolve())
                except ValueError:
                    self._send(403, b"Forbidden", "text/plain; charset=utf-8")
                    return
                if not target.exists() or not target.is_file():
                    self._send(404, b"Not Found", "text/plain; charset=utf-8")
                    return
                try:
                    body = target.read_bytes()
                except OSError as exc:
                    self._send(500, f"Failed to read asset: {exc}".encode(), "text/plain; charset=utf-8")
                    return
                self._send(200, body, content_type_for(target))
                return

            if path == "/api/agent-office/status":
                payload = build_payload(repo_map)
                self._send(
                    200,
                    json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
                return

            self._send(404, b"Not Found", "text/plain; charset=utf-8")

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return Handler


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    default_tools_root = script_dir.parent
    default_quant_root = default_tools_root.parent

    html_candidates = (
        default_tools_root / "quant-desktop-live.html",
        default_quant_root / "quant-desktop-live.html",
    )
    default_html = next((p for p in html_candidates if p.exists()), html_candidates[0])

    parser = argparse.ArgumentParser(description="Serve Quant Agent Office with live git status.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--html",
        default=str(default_html),
        help="Path to quant-desktop-live.html",
    )
    parser.add_argument(
        "--qi1-repo",
        default=str(default_quant_root / "quant-investment"),
        help="Path to quant-investment repo",
    )
    parser.add_argument(
        "--qi2-repo",
        default=str(default_tools_root),
        help="Path to quant-investment2 repo",
    )
    args = parser.parse_args()

    html_path = Path(args.html).resolve()
    repo_map = {
        "qi1": Path(args.qi1_repo).resolve(),
        "qi2": Path(args.qi2_repo).resolve(),
    }
    for repo in repo_map.values():
        if not (repo / ".git").exists():
            raise SystemExit(f"Not a git repo: {repo}")
    if not html_path.exists():
        raise SystemExit(f"HTML file not found: {html_path}")

    server = ThreadingHTTPServer((args.host, args.port), make_handler(html_path, repo_map))
    print(f"Serving Agent Office at http://{args.host}:{args.port}")
    print(f"HTML: {html_path}")
    print(f"API:  http://{args.host}:{args.port}/api/agent-office/status")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
