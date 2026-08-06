# base.py
"""Abstract collector base: bookmark persistence + idempotent ingestion."""
import json
from datetime import datetime, timezone

# usage_events columns that collectors and the ingestion server write.
EVENT_COLUMNS = [
    "event_id", "occurred_at", "provider_id", "agent_name", "account_id",
    "workspace_id", "session_id", "turn_id", "message_id", "tool_call_id",
    "event_type", "model_raw", "model_canonical", "model_lineage_id",
    "input_tokens", "output_tokens", "reasoning_tokens", "cache_read_tokens",
    "cache_write_tokens", "total_tokens", "cost_usd", "requests", "tool_name",
    "status", "dedup_key", "raw_event_id", "normalization_version",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BaseCollector:
    """Collectors poll a local data source and return normalized usage_events.

    Subclasses implement:
        poll(bookmark: dict) -> (events: list[dict], new_bookmark: dict)
    The bookmark is persisted in collector_state so unchanged files are never
    re-scanned, and dedup_key makes every run idempotent.
    """

    name = "base"

    # -- bookmark persistence ---------------------------------------------
    def get_bookmark(self, conn) -> dict:
        row = conn.execute(
            "SELECT bookmark FROM collector_state WHERE collector_id = ?", (self.name,)
        ).fetchone()
        if row and row["bookmark"]:
            try:
                return json.loads(row["bookmark"])
            except (ValueError, TypeError):
                pass
        return {}

    def save_bookmark(self, conn, state) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO collector_state (collector_id, bookmark, updated_at) "
            "VALUES (?, ?, ?)",
            (self.name, json.dumps(state), now_iso()),
        )

    # -- ingestion ----------------------------------------------------------
    def poll(self, bookmark: dict):
        """Return (events, new_bookmark). Must be deterministic and idempotent."""
        raise NotImplementedError

    def run_once(self, conn) -> dict:
        bookmark = self.get_bookmark(conn)
        events, new_bookmark = self.poll(bookmark)
        inserted = skipped = 0
        placeholders = ",".join("?" * len(EVENT_COLUMNS))
        cols = ",".join(EVENT_COLUMNS)
        for ev in events:
            cur = conn.execute(
                f"INSERT OR IGNORE INTO usage_events ({cols}) VALUES ({placeholders})",
                tuple(ev.get(c) for c in EVENT_COLUMNS),
            )
            if cur.rowcount and cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        if new_bookmark is not None:
            self.save_bookmark(conn, new_bookmark)
        conn.commit()
        return {
            "collector": self.name,
            "events": len(events),
            "inserted": inserted,
            "skipped": skipped,
        }
