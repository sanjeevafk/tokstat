# vscode_cursor.py
"""Cursor / VS Code state.vscdb collector (SPIKE - typically no-op).

Verified 2026-08-06: ~/.config/Cursor/User/globalStorage/state.vscdb contains
no token/usage keys (only auth + git IPC secrets). Cursor usage is server-side.
This collector therefore no-ops with a warning unless a future Cursor/VS Code
version stores usage keys - in which case it best-effort parses them as
status='estimated' events. Do NOT block on this source; the ingestion endpoint
or a proxy wrapper is the supported path for these tools.
"""
import datetime
import hashlib
import json
import os
import sqlite3
import sys

from .. import config
from .base import BaseCollector

_KEY_PATTERN = ("%usage%", "%token%", "%aiService%")
_WARNED = set()


class VSCodeCursorCollector(BaseCollector):
    name = "vscode_cursor"

    def poll(self, bookmark: dict):
        if not os.path.exists(config.CURSOR_STATE_DB):
            return [], None
        try:
            occurred_at = datetime.datetime.fromtimestamp(
                os.path.getmtime(config.CURSOR_STATE_DB), datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        except OSError:
            return [], None
        try:
            conn = sqlite3.connect(f"file:{config.CURSOR_STATE_DB}?mode=ro", uri=True)
            try:
                rows = conn.execute(
                    "SELECT key, value FROM ItemTable "
                    "WHERE key LIKE ? OR key LIKE ? OR key LIKE ?",
                    _KEY_PATTERN,
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return [], None

        events = []
        for key, value in rows:
            if not value:
                continue
            try:
                data = json.loads(value)
            except (ValueError, TypeError):
                continue
            parsed = self._extract_tokens(data)
            if parsed is None:
                continue
            in_tok, out_tok, total = parsed
            if total <= 0:
                continue
            events.append({
                "event_id": None,
                "occurred_at": occurred_at,
                "provider_id": None,
                "agent_name": "cursor",
                "workspace_id": "Global/No Project",
                "session_id": None,
                "turn_id": key[:60],
                "event_type": "message_usage",
                "model_raw": "cursor-default",
                "model_canonical": "cursor-default",
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "total_tokens": total,
                "cost_usd": 0.0,
                "requests": 1,
                "status": "estimated",
                "dedup_key": "cursor-"
                + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16],
            })
        if not events and self.name not in _WARNED:
            _WARNED.add(self.name)
            print(
                "Warning: Cursor/VS Code state.vscdb exposes no local token usage; "
                "use the ingestion endpoint (/v1/events) or a proxy wrapper for these tools.",
                file=sys.stderr,
            )
        return events, None

    @staticmethod
    def _extract_tokens(data):
        """Best-effort: find numeric token fields anywhere in nested dicts."""
        if isinstance(data, dict):
            inp = data.get("input_tokens") or data.get("inputTokens")
            out = data.get("output_tokens") or data.get("outputTokens")
            tot = data.get("total_tokens") or data.get("totalTokens")
            if inp is not None or out is not None or tot is not None:
                try:
                    inp = int(inp or 0)
                    out = int(out or 0)
                    tot = int(tot or 0) or (inp + out)
                    return inp, out, tot
                except (TypeError, ValueError):
                    pass
            for v in data.values():
                res = VSCodeCursorCollector._extract_tokens(v)
                if res is not None:
                    return res
        elif isinstance(data, list):
            for v in data:
                res = VSCodeCursorCollector._extract_tokens(v)
                if res is not None:
                    return res
        return None
