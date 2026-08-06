# db_access.py
import datetime
import os
import re
import sqlite3
import sys

from . import config, migration
from .queries import (
    QUERY_ALL_EVENTS,
    QUERY_DAILY_ROLLUP,
    QUERY_PROJECTS_BREAKDOWN,
    QUERY_SESSIONS_BREAKDOWN,
    QUERY_TOOL_TOTALS,
)

# Native database is the single source of truth for reads. Legacy OpenUsage /
# Tokentop databases are optional augmentary sources consumed by the
# legacy_sync collector (src/tokstat/collectors/legacy_sync.py).
# Paths are read from config at CALL time so they stay patchable in tests and
# the config module remains the single source of truth.


def sanitize_field(value):
    """Strip control characters, newlines, and HTML tags from string fields.
    Prevents broken JSON injection when workspace_id or model names contain garbage."""
    if not value or not isinstance(value, str):
        return value
    # Strip newlines, carriage returns, tabs
    value = re.sub(r'[\r\n\t]', ' ', value)
    # Strip HTML/XML tags
    value = re.sub(r'<[^>]+>', '', value)
    # Strip null bytes
    value = value.replace('\x00', '')
    return value.strip() or None


def get_db_connection(path):
    """Open a SQLite database read-only style helper (returns None when absent)."""
    if not os.path.exists(path):
        return None
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to database at {path}: {e}", file=sys.stderr)
        return None


def ensure_native_db():
    """Bootstrap the native database (schema + optional legacy migration)."""
    migration.check_and_run_migrations()


def query_copilot_db():
    """Estimate Copilot usage from ~/.copilot/session-store.db.
    Returns (input, output, total, requests). Estimates only (status='estimated'
    is applied by the copilot collector); analytics merges these totals."""
    copilot_db_path = config.COPILOT_DB
    if not os.path.exists(copilot_db_path):
        return 0, 0, 0, 0
    try:
        conn = sqlite3.connect(copilot_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]

        if 'messages' in tables:
            cursor.execute("SELECT count(*), sum(length(content))/4 FROM messages;")
            res = cursor.fetchone()
            requests = res[0] or 0
            total_tokens = int(res[1] or 0)
            conn.close()
            # Approximation as in original code
            return int(total_tokens * 0.7), int(total_tokens * 0.3), total_tokens, requests
        conn.close()
    except Exception as e:
        print(f"Warning: Could not read Copilot DB: {e}", file=sys.stderr)
    return 0, 0, 0, 0


def fetch_tokentop_events():
    """Read Tokentop usage_events as normalized event dicts (legacy source).
    Used by the legacy_sync collector; kept here for reuse."""
    tokentop_db_path = config.LEGACY_TOKENTOP_DB
    if not os.path.exists(tokentop_db_path):
        return []
    conn = get_db_connection(tokentop_db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id, timestamp, source, provider, model, agent_id, session_id, project_path,
                input_tokens, output_tokens, cache_read_tokens, cost_usd, request_count
            FROM usage_events
        """)
        rows = []
        for r in cursor.fetchall():
            ts = r['timestamp']
            # timestamp is unix epoch, determine if ms or seconds
            if ts > 5000000000:
                dt_obj = datetime.datetime.fromtimestamp(ts / 1000.0, datetime.timezone.utc)
            else:
                dt_obj = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)

            occurred_at = dt_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
            proj = os.path.basename(r['project_path']) if r['project_path'] else 'Global/No Project'

            in_tok = r['input_tokens'] or 0
            out_tok = r['output_tokens'] or 0
            cache_tok = r['cache_read_tokens'] or 0
            cost_u = r['cost_usd'] or 0.0
            req_cnt = r['request_count'] or 1

            rows.append({
                "event_id": f"tokentop-{r['id']}",
                "occurred_at": occurred_at,
                "provider_id": r['provider'] or 'unknown',
                "agent_name": r['agent_id'] or 'unknown',
                "workspace_id": proj,
                "session_id": r['session_id'],
                "turn_id": str(r['id']),
                "event_type": "message_usage",
                "model_raw": r['model'] or 'unknown',
                "model_canonical": r['model'],
                "model_lineage_id": None,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cache_read_tokens": cache_tok,
                "cache_write_tokens": 0,
                "total_tokens": in_tok + out_tok,
                "cost_usd": cost_u,
                "requests": req_cnt,
                "status": "ok",
                "dedup_key": f"tokentop-{r['id']}"
            })
        conn.close()
        return rows
    except Exception as e:
        print(f"Warning: Failed to fetch tokentop events: {e}", file=sys.stderr)
        if conn:
            conn.close()
        return []


def _read_native_events():
    """Read usage_events from the native DB (bootstrap first if needed)."""
    if not os.path.exists(config.DB_PATH):
        migration.check_and_run_migrations()
    conn = config.connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(QUERY_ALL_EVENTS)
        raw_rows = [dict(r) for r in cursor.fetchall()]
        events = []
        for row in raw_rows:
            row['workspace_id'] = sanitize_field(row.get('workspace_id'))
            row['model_raw'] = sanitize_field(row.get('model_raw'))
            row['agent_name'] = sanitize_field(row.get('agent_name'))
            events.append(row)
        return events
    except Exception as e:
        print(f"Error running QUERY_ALL_EVENTS: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()


def fetch_all_events():
    """All usage events from the native database (post-migration this includes
    OpenUsage + Tokentop history; collectors and the ingestion server append)."""
    return _read_native_events()


def fetch_daily_rollup():
    conn = config.connect_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(QUERY_DAILY_ROLLUP)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"Error running QUERY_DAILY_ROLLUP: {e}", file=sys.stderr)
        if conn:
            conn.close()
        return []


def fetch_projects_breakdown():
    conn = config.connect_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(QUERY_PROJECTS_BREAKDOWN)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"Error running QUERY_PROJECTS_BREAKDOWN: {e}", file=sys.stderr)
        if conn:
            conn.close()
        return []


def fetch_sessions_breakdown():
    conn = config.connect_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(QUERY_SESSIONS_BREAKDOWN)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"Error running QUERY_SESSIONS_BREAKDOWN: {e}", file=sys.stderr)
        if conn:
            conn.close()
        return []


def fetch_tool_totals():
    conn = config.connect_db()
    if not conn:
        return {}
    try:
        cursor = conn.cursor()
        cursor.execute(QUERY_TOOL_TOTALS)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        tools_data = {}
        for r in rows:
            agent = r['agent']
            tools_data[agent] = {
                "input": r['input'],
                "output": r['output'],
                "cache_read": r['cache_read'],
                "total": r['total'],
                "requests": r['requests']
            }

        # Merge Copilot
        cop_in, cop_out, cop_tot, cop_req = query_copilot_db()
        if 'copilot' not in tools_data:
            tools_data['copilot'] = {"input": 0, "output": 0, "cache_read": 0, "total": 0, "requests": 0}
        tools_data['copilot']['input'] += cop_in
        tools_data['copilot']['output'] += cop_out
        tools_data['copilot']['total'] += cop_tot
        tools_data['copilot']['requests'] += cop_req

        return tools_data
    except Exception as e:
        print(f"Error running QUERY_TOOL_TOTALS: {e}", file=sys.stderr)
        if conn:
            conn.close()
        return {}


def fetch_balance_observations():
    """Latest per-metric balance observations from the native DB (populated by
    legacy_sync from OpenUsage, or a future provider poller)."""
    conn = config.connect_db()
    if not conn:
        return {}
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT provider_id, account_id, metric_key, used, observed_at
            FROM balance_observations
            ORDER BY observed_at DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        latest_metrics = {}
        for r in rows:
            key = r['metric_key']
            if key not in latest_metrics:
                latest_metrics[key] = r['used']

        return latest_metrics
    except Exception as e:
        print(f"Error reading balance_observations: {e}", file=sys.stderr)
        if conn:
            conn.close()
        return {}
