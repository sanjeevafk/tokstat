# copilot.py
"""GitHub Copilot collector (ESTIMATED tokens).

~/.copilot/session-store.db holds no official token counts; we reuse the
proven character-length heuristic (len(content)/4, split 70/30 in/out) and
flag the aggregate event status='estimated'.
"""
import datetime
import os

from .. import config, db_access
from .base import BaseCollector


class CopilotCollector(BaseCollector):
    name = "copilot"

    def poll(self, bookmark: dict):
        if not os.path.exists(config.COPILOT_DB):
            return [], None
        in_tok, out_tok, total, reqs = db_access.query_copilot_db()
        if total <= 0:
            return [], None

        last_total = bookmark.get("last_total", 0)
        last_in = bookmark.get("last_in", 0)
        last_out = bookmark.get("last_out", 0)
        last_reqs = bookmark.get("last_reqs", 0)

        delta_total = max(0, total - last_total)
        delta_in = max(0, in_tok - last_in)
        delta_out = max(0, out_tok - last_out)
        delta_reqs = max(0, (reqs or 0) - last_reqs)

        # If no new tokens or requests since last poll, skip
        if delta_total <= 0 and delta_reqs <= 0:
            return [], bookmark

        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        event = {
            "event_id": None,
            "occurred_at": now,
            "provider_id": "github",
            "agent_name": "copilot",
            "workspace_id": "Global/No Project",
            "session_id": None,
            "turn_id": None,
            "event_type": "message_usage",
            "model_raw": "copilot-default",
            "model_canonical": "copilot-default",
            "input_tokens": delta_in,
            "output_tokens": delta_out,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "total_tokens": delta_total,
            "cost_usd": 0.0,
            "requests": delta_reqs or 1,
            "status": "estimated",
            "dedup_key": f"copilot-{now}",
        }
        new_bookmark = {
            "last_total": total,
            "last_in": in_tok,
            "last_out": out_tok,
            "last_reqs": reqs or 0,
        }
        return [event], new_bookmark
