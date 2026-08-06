# migration.py
"""Native schema bootstrap and read-only migration of legacy databases.

The native schema is OpenUsage-compatible (see docs/openusage_independence_plan.md
section 3.1) so analytics/queries/renderer keep working unchanged. Migration is
idempotent, non-destructive (legacy DBs are opened read-only) and deduplicated.
"""
import datetime
import os
import re
import sqlite3
import sys

from . import config

# --- Schema DDL (OpenUsage-compatible) -------------------------------------
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS usage_events (
        event_id TEXT PRIMARY KEY,
        occurred_at TEXT NOT NULL,
        provider_id TEXT,
        agent_name TEXT NOT NULL,
        account_id TEXT,
        workspace_id TEXT,
        session_id TEXT,
        turn_id TEXT,
        message_id TEXT,
        tool_call_id TEXT,
        event_type TEXT NOT NULL,
        model_raw TEXT,
        model_canonical TEXT,
        model_lineage_id TEXT,
        input_tokens INTEGER,
        output_tokens INTEGER,
        reasoning_tokens INTEGER,
        cache_read_tokens INTEGER,
        cache_write_tokens INTEGER,
        total_tokens INTEGER,
        cost_usd REAL,
        requests INTEGER,
        tool_name TEXT,
        status TEXT NOT NULL,
        dedup_key TEXT UNIQUE,  -- matches the live OpenUsage unique index
        raw_event_id TEXT,
        normalization_version INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS usage_raw_events (
        raw_event_id TEXT PRIMARY KEY,
        ingested_at TEXT NOT NULL,
        source_system TEXT NOT NULL,
        source_channel TEXT NOT NULL,
        source_schema_version TEXT NOT NULL,
        source_payload TEXT NOT NULL,
        source_payload_hash TEXT NOT NULL,
        workspace_id TEXT,
        agent_session_id TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS balance_observations (
        provider_id TEXT NOT NULL,
        account_id TEXT NOT NULL,
        metric_key TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        used REAL,
        limit_val REAL,
        remaining REAL,
        unit TEXT,
        semantics TEXT NOT NULL,
        PRIMARY KEY (provider_id, account_id, metric_key, observed_at)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS collector_state (
        collector_id TEXT PRIMARY KEY,
        bookmark TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS _migrations (
        migration_id TEXT PRIMARY KEY,
        applied_at TEXT NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_usage_events_occurred ON usage_events(occurred_at);",
    "CREATE INDEX IF NOT EXISTS idx_usage_events_raw_event_id ON usage_events(raw_event_id);",
]

OPENUSAGE_USAGE_EVENT_COLUMNS = [
    "event_id", "occurred_at", "provider_id", "agent_name", "account_id",
    "workspace_id", "session_id", "turn_id", "message_id", "tool_call_id",
    "event_type", "model_raw", "model_canonical", "model_lineage_id",
    "input_tokens", "output_tokens", "reasoning_tokens", "cache_read_tokens",
    "cache_write_tokens", "total_tokens", "cost_usd", "requests", "tool_name",
    "status", "dedup_key", "raw_event_id", "normalization_version",
]

TOKENTOP_EVENT_COLUMNS = [
    "id", "timestamp", "source", "provider", "model", "agent_id", "session_id",
    "project_path", "input_tokens", "output_tokens", "cache_read_tokens",
    "cache_write_tokens", "cost_usd", "request_count", "pricing_source",
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create native tables/indexes if missing (idempotent)."""
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    conn.commit()


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _migration_applied(conn: sqlite3.Connection, migration_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM _migrations WHERE migration_id = ?", (migration_id,))
    return cur.fetchone() is not None


def _record_migration(conn: sqlite3.Connection, migration_id: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO _migrations (migration_id, applied_at) VALUES (?, ?)",
        (migration_id, _now_iso()),
    )


def _open_legacy_readonly(path: str) -> sqlite3.Connection | None:
    """Open a legacy SQLite database strictly read-only; None if unusable."""
    if not os.path.exists(path):
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as exc:
        print(f"Warning: could not open legacy DB read-only at {path}: {exc}", file=sys.stderr)
        return None


def fingerprint(occurred_at, model_raw, input_tokens, output_tokens):
    """10-second time-bucket fingerprint for cross-source dedup.

    Bucket = first 15 chars of the ISO timestamp (YYYY-MM-DDTHH:MM + 1 digit),
    matching the proven logic previously in db_access.fetch_all_events.
    """
    ts_str = str(occurred_at or "")
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d)", ts_str)
    ts_bucket = (m.group(1) + " " + m.group(2)) if m else ts_str[:15]
    return (
        ts_bucket,
        str(model_raw or "").lower(),
        input_tokens or 0,
        output_tokens or 0,
    )


def _copy_table(
    conn: sqlite3.Connection,
    src: sqlite3.Connection,
    table: str,
    columns: list[str],
) -> int:
    """Copy rows from `table` in src into the identically-named native table.

    Uses INSERT OR IGNORE on the primary key so re-runs are safe. Returns the
    number of rows attempted (ignored duplicates included) for reporting.
    """
    placeholders = ",".join("?" * len(columns))
    col_sql = ",".join(columns)
    count = 0
    for row in src.execute(f"SELECT {col_sql} FROM {table}"):
        conn.execute(
            f"INSERT OR IGNORE INTO {table} ({col_sql}) VALUES ({placeholders})",
            tuple(row[c] for c in columns),
        )
        count += 1
    return count


def migrate_openusage(src_db: str, conn: sqlite3.Connection, force: bool = False) -> int:
    """Copy usage_events, usage_raw_events and balance_observations from an
    OpenUsage telemetry.db into the native DB. Read-only on the source."""
    migration_id = "migration_openusage_v1"
    if not force and _migration_applied(conn, migration_id):
        return 0
    src = _open_legacy_readonly(src_db)
    if src is None:
        return 0
    total = 0
    try:
        total += _copy_table(conn, src, "usage_events", OPENUSAGE_USAGE_EVENT_COLUMNS)
        raw_cols = [
            "raw_event_id", "ingested_at", "source_system", "source_channel",
            "source_schema_version", "source_payload", "source_payload_hash",
            "workspace_id", "agent_session_id",
        ]
        total += _copy_table(conn, src, "usage_raw_events", raw_cols)
        bal_cols = [
            "provider_id", "account_id", "metric_key", "observed_at",
            "used", "limit_val", "remaining", "unit", "semantics",
        ]
        total += _copy_table(conn, src, "balance_observations", bal_cols)
    except sqlite3.Error as exc:
        print(f"Warning: partial OpenUsage migration (continuing): {exc}", file=sys.stderr)
    finally:
        src.close()
    _record_migration(conn, migration_id)
    conn.commit()  # commit AFTER recording so fresh invocations see the record
    print(f"[migrate] OpenUsage: {total} rows imported (deduped via PK).")
    return total


def migrate_tokentop(src_db: str, conn: sqlite3.Connection, force: bool = False) -> int:
    """Copy Tokentop usage_events into the native DB, cross-source deduplicated
    against OpenUsage events already present via the 10s fingerprint."""
    migration_id = "migration_tokentop_v1"
    if not force and _migration_applied(conn, migration_id):
        return 0
    src = _open_legacy_readonly(src_db)
    if src is None:
        return 0
    try:
        # Build the fingerprint set from OpenUsage events already in the native DB.
        ou_fp = set()
        for row in conn.execute(
            "SELECT occurred_at, model_raw, input_tokens, output_tokens FROM usage_events"
        ):
            ou_fp.add(
                fingerprint(
                    row["occurred_at"], row["model_raw"],
                    row["input_tokens"], row["output_tokens"],
                )
            )

        inserted = 0
        skipped = 0
        for row in src.execute(
            "SELECT " + ",".join(TOKENTOP_EVENT_COLUMNS) + " FROM usage_events"
        ):
            ts = row["timestamp"]
            if ts > 5_000_000_000:  # milliseconds
                dt = datetime.datetime.fromtimestamp(ts / 1000.0, datetime.timezone.utc)
            else:
                dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
            occurred_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            in_tok = row["input_tokens"] or 0
            out_tok = row["output_tokens"] or 0
            cache_tok = row["cache_read_tokens"] or 0
            proj = os.path.basename(row["project_path"]) if row["project_path"] else "Global/No Project"

            if fingerprint(occurred_at, row["model"], in_tok, out_tok) in ou_fp:
                skipped += 1
                continue

            conn.execute(
                """
                INSERT OR IGNORE INTO usage_events (
                    event_id, occurred_at, provider_id, agent_name, account_id,
                    workspace_id, session_id, turn_id, event_type, model_raw,
                    model_canonical, model_lineage_id, input_tokens, output_tokens,
                    cache_read_tokens, cache_write_tokens, total_tokens, cost_usd,
                    requests, status, dedup_key, normalization_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"tokentop-{row['id']}", occurred_at, row["provider"] or "unknown",
                    row["agent_id"] or "unknown", None, proj, row["session_id"],
                    str(row["id"]), "message_usage", row["model"], row["model"], None,
                    in_tok, out_tok, cache_tok, row["cache_write_tokens"] or 0,
                    in_tok + out_tok, row["cost_usd"] or 0.0,
                    row["request_count"] or 1, "ok", f"tokentop-{row['id']}", "v1",
                ),
            )
            inserted += 1
    except sqlite3.Error as exc:
        print(f"Warning: partial Tokentop migration (continuing): {exc}", file=sys.stderr)
    finally:
        src.close()
    _record_migration(conn, migration_id)
    conn.commit()  # commit AFTER recording so fresh invocations see the record
    print(f"[migrate] Tokentop: {inserted} imported, {skipped} deduped against OpenUsage.")
    return inserted


def check_and_run_migrations(force: bool = False, explicit: bool = False) -> dict:
    """Bootstrap the native DB and optionally import legacy data.

    Auto-run on first `tokstat` (respects config.SYNC_LEGACY). The explicit
    `tokstat migrate` command always imports (explicit=True).
    """
    config.ensure_tokstat_dir()
    conn = config.connect_db()
    try:
        ensure_schema(conn)
        if not explicit and not config.SYNC_LEGACY:
            return {"migrated": False, "reason": "TOKSTAT_SYNC_LEGACY=0"}
        ou_count = migrate_openusage(config.LEGACY_OPENUSAGE_DB, conn, force=force)
        tt_count = migrate_tokentop(config.LEGACY_TOKENTOP_DB, conn, force=force)
        return {
            "migrated": True,
            "openusage_imported": ou_count,
            "tokentop_imported": tt_count,
        }
    finally:
        conn.close()
