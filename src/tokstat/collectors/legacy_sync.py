# legacy_sync.py
"""Optional augmentary collector: sync OpenUsage + Tokentop legacy DBs.

Reads the legacy databases strictly read-only and merges their events into the
native DB (this is what makes OpenUsage/tokentop optional augmentary sources
rather than dependencies). Disabled entirely when TOKSTAT_SYNC_LEGACY=0.
"""
import sqlite3
import sys

from .. import config, db_access, migration
from .base import BaseCollector

_BALANCE_COLUMNS = [
    "provider_id", "account_id", "metric_key", "observed_at",
    "used", "limit_val", "remaining", "unit", "semantics",
]


class LegacySyncCollector(BaseCollector):
    name = "legacy_sync"

    def poll(self, bookmark: dict):
        """Merge new OpenUsage + Tokentop events (balance observations are
        copied in run_once)."""
        if not config.SYNC_LEGACY:
            return [], None

        new_bookmark = dict(bookmark)
        events = []

        # 1. OpenUsage usage_events delta (>= boundary so same-timestamp events
        #    are never lost; INSERT OR IGNORE on event_id keeps it idempotent).
        ou_conn = db_access.get_db_connection(config.LEGACY_OPENUSAGE_DB)
        if ou_conn is not None:
            try:
                last_ou = bookmark.get("openusage_last_occurred_at") or ""
                sql = "SELECT * FROM usage_events"
                params = []
                if last_ou:
                    sql += " WHERE occurred_at >= ?"
                    params.append(last_ou)
                sql += " ORDER BY occurred_at ASC"
                for row in ou_conn.execute(sql, params):
                    d = dict(row)
                    for field in ("workspace_id", "model_raw", "agent_name"):
                        d[field] = db_access.sanitize_field(d.get(field))
                    events.append(d)
                    new_bookmark["openusage_last_occurred_at"] = d.get("occurred_at") or ""
            except sqlite3.Error as exc:
                print(f"Warning: legacy_sync openusage delta failed: {exc}", file=sys.stderr)
            finally:
                ou_conn.close()

        # 2. Tokentop delta (monotonic id cursor) with cross-source dedup.
        last_tt_id = int(bookmark.get("tokentop_last_id", 0) or 0)
        for ev in db_access.fetch_tokentop_events():
            tt_id = int(ev.get("turn_id") or 0)
            if tt_id <= last_tt_id:
                continue
            if self._matches_openusage(ev):
                continue
            events.append(ev)
            new_bookmark["tokentop_last_id"] = max(new_bookmark.get("tokentop_last_id", 0), tt_id)

        return events, new_bookmark

    # -- helpers --------------------------------------------------------------
    def _matches_openusage(self, ev) -> bool:
        """True if a native OpenUsage event shares the 10s fingerprint."""
        fp = migration.fingerprint(
            ev.get("occurred_at"), ev.get("model_raw"),
            ev.get("input_tokens"), ev.get("output_tokens"),
        )
        conn = config.connect_db()
        try:
            row = conn.execute(
                "SELECT 1 FROM usage_events WHERE substr(occurred_at,1,15) = ? "
                "AND lower(model_raw) = ? AND input_tokens = ? AND output_tokens = ? LIMIT 1",
                fp,
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def run_once(self, conn) -> dict:
        result = super().run_once(conn)
        result["balance_observations_copied"] = 0
        if not config.SYNC_LEGACY:
            return result
        # balance_observations: always copy (small table), INSERT OR REPLACE on
        # the natural PK so the latest snapshot per metric wins.
        bal_conn = db_access.get_db_connection(config.LEGACY_OPENUSAGE_DB)
        if bal_conn is None:
            return result
        try:
            placeholders = ",".join("?" * len(_BALANCE_COLUMNS))
            cols = ",".join(_BALANCE_COLUMNS)
            for row in bal_conn.execute(f"SELECT {cols} FROM balance_observations"):
                conn.execute(
                    f"INSERT OR REPLACE INTO balance_observations ({cols}) VALUES ({placeholders})",
                    tuple(row[c] for c in _BALANCE_COLUMNS),
                )
                result["balance_observations_copied"] += 1
            conn.commit()
        except sqlite3.Error as exc:
            print(f"Warning: legacy_sync balance copy failed: {exc}", file=sys.stderr)
        finally:
            bal_conn.close()
        return result
