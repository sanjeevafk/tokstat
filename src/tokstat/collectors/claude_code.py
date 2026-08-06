# claude_code.py
"""Claude Code transcript collector (REAL token usage).

Targets ~/.claude/projects/<encoded-path>/<session-id>.jsonl. Assistant lines
carry `message.usage` with real input/output/cache token counts.

Known caveats handled here:
  - SSE streaming logs the same requestId multiple times with incremental
    values -> we keep the highest token totals per requestId.
  - `input_tokens` is often a 0/1 streaming placeholder -> when <= 1 we fall
    back to cache_creation_input_tokens.
  - output_tokens excludes extended thinking tokens (documented limitation).
"""
import json
import os
import urllib.parse

from .. import config
from .base import BaseCollector

STATUS = "ok"  # real usage, not an estimate


class ClaudeCodeCollector(BaseCollector):
    name = "claude_code"

    def poll(self, bookmark: dict):
        files_state = bookmark.get("files", {})
        new_state = {}
        events = []
        if not os.path.isdir(config.CLAUDE_PROJECTS_DIR):
            return [], {"files": files_state}

        for root, _dirs, files in os.walk(config.CLAUDE_PROJECTS_DIR):
            for fname in files:
                if not fname.endswith(".jsonl"):
                    continue
                path = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if files_state.get(path) == mtime:
                    new_state[path] = mtime
                    continue
                session_id = fname[:-6]  # strip ".jsonl"
                workspace = self._decode_workspace(os.path.basename(root))
                events.extend(self._parse_file(path, session_id, workspace))
                new_state[path] = mtime
        return events, {"files": new_state}

    # -- parsing --------------------------------------------------------------
    def _parse_file(self, path: str, session_id: str, workspace: str):
        by_request = {}
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # incomplete trailing line mid-write
                    if obj.get("type") != "assistant":
                        continue
                    msg = obj.get("message") or {}
                    usage = msg.get("usage") or {}
                    if not usage:
                        continue
                    req_id = (
                        obj.get("requestId")
                        or obj.get("uuid")
                        or msg.get("id")
                        or "anon"
                    )
                    cand = {
                        "occurred_at": obj.get("timestamp") or "",
                        "model_raw": msg.get("model") or obj.get("model") or "unknown",
                        "input_tokens": usage.get("input_tokens", 0) or 0,
                        "output_tokens": usage.get("output_tokens", 0) or 0,
                        "cache_read": usage.get("cache_read_input_tokens", 0) or 0,
                        "cache_create": usage.get("cache_creation_input_tokens", 0) or 0,
                    }
                    prev = by_request.get(req_id)
                    if prev is None or self._total(cand) > self._total(prev):
                        by_request[req_id] = cand
        except OSError:
            return []

        events = []
        for req_id, e in by_request.items():
            input_tok = e["input_tokens"] if e["input_tokens"] > 1 else (e["cache_create"] or 0)
            cache_read = e["cache_read"]
            output_tok = e["output_tokens"]
            total = input_tok + output_tok + cache_read
            if total <= 0:
                continue
            events.append({
                "event_id": None,
                "occurred_at": e["occurred_at"],
                "provider_id": "anthropic",
                "agent_name": "claude_code",
                "workspace_id": workspace,
                "session_id": session_id,
                "turn_id": str(req_id)[:40],
                "event_type": "message_usage",
                "model_raw": e["model_raw"],
                "model_canonical": e["model_raw"],
                "input_tokens": input_tok,
                "output_tokens": output_tok,
                "cache_read_tokens": cache_read,
                "cache_write_tokens": e["cache_create"],
                "total_tokens": total,
                "cost_usd": 0.0,
                "requests": 1,
                "status": STATUS,
                "dedup_key": f"claude-{req_id}",
            })
        return events

    @staticmethod
    def _total(e) -> int:
        return e["input_tokens"] + e["output_tokens"] + e["cache_read"] + e["cache_create"]

    @staticmethod
    def _decode_workspace(folder: str) -> str:
        """Folder is an encoded absolute path; best-effort decode to a project
        name. Falls back to the raw folder name."""
        try:
            decoded = urllib.parse.unquote(folder.replace("-", "/"))
            if "/" in decoded:
                return os.path.basename(decoded.rstrip("/")) or decoded
        except Exception:
            pass
        return folder
