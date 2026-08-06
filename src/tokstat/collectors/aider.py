# aider.py
"""Aider collector (REAL token usage from .aider.model.stats.json).

Aider writes `<repo>/.aider.model.stats.json` with per-model usage:
    {"<model>": {"cost": float, "tokens_in": int, "tokens_out": int, ...}}
We emit one status='ok' event per model per stats file.
"""
import datetime
import hashlib
import json
import os

from .base import BaseCollector

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".cache",
    ".config", ".local", ".gemini", ".claude", ".tokstat", "Library",
}
MAX_DEPTH = 3


class AiderCollector(BaseCollector):
    name = "aider"

    def poll(self, bookmark: dict):
        files_state = bookmark.get("files", {})
        new_state = {}
        events = []
        seen = set()

        search_dirs = [os.getcwd(), os.path.expanduser("~")]
        for base in search_dirs:
            for root, dirs, files in self._walk(base):
                if ".aider.model.stats.json" in files:
                    path = os.path.join(root, ".aider.model.stats.json")
                    if path in seen:
                        continue
                    seen.add(path)
                    try:
                        mtime = os.path.getmtime(path)
                    except OSError:
                        continue
                    if files_state.get(path) == mtime:
                        new_state[path] = mtime
                        continue
                    events.extend(self._parse_stats(path))
                    new_state[path] = mtime
        return events, {"files": new_state}

    def _walk(self, base: str):
        base = os.path.abspath(base)
        if not os.path.isdir(base):
            return
        for root, dirs, files in os.walk(base):
            depth = root[len(base):].count(os.sep)
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            if depth >= MAX_DEPTH:
                dirs[:] = []
            yield root, dirs, files

    def _parse_stats(self, path: str):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return []
        if not isinstance(data, dict):
            return []

        mtime = os.path.getmtime(path)
        occurred_at = datetime.datetime.fromtimestamp(
            mtime, datetime.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        day = occurred_at[:10]
        workspace = os.path.basename(os.path.dirname(path)) or "Global/No Project"
        path_hash = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]

        events = []
        for model, stats in data.items():
            if not isinstance(stats, dict):
                continue
            in_tok = int(stats.get("tokens_in") or 0)
            out_tok = int(stats.get("tokens_out") or 0)
            cost = float(stats.get("cost") or 0.0)
            total = in_tok + out_tok
            if total <= 0:
                continue
            events.append({
                "event_id": None,
                "occurred_at": occurred_at,
                "provider_id": None,
                "agent_name": "aider",
                "workspace_id": workspace,
                "session_id": f"aider-{day}",
                "turn_id": None,
                "event_type": "message_usage",
                "model_raw": model,
                "model_canonical": model,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "total_tokens": total,
                "cost_usd": cost,
                "requests": 1,
                "status": "ok",
                "dedup_key": f"aider-{model}-{day}-{path_hash}",
            })
        return events
