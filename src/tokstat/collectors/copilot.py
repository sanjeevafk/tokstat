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
        day = datetime.date.today().isoformat()
        event = {
            "event_id": None,
            "occurred_at": day + "T00:00:00Z",
            "provider_id": "github",
            "agent_name": "copilot",
            "workspace_id": "Global/No Project",
            "session_id": None,
            "turn_id": None,
            "event_type": "message_usage",
            "model_raw": "copilot-default",
            "model_canonical": "copilot-default",
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "total_tokens": total,
            "cost_usd": 0.0,
            "requests": reqs or 1,
            "status": "estimated",
            "dedup_key": f"copilot-{day}",
        }
        return [event], {"last_day": day}
