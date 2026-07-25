# db_access.py
import sqlite3
import os
import sys
import re
import datetime
from queries import (
    QUERY_ALL_EVENTS,
    QUERY_DAILY_ROLLUP,
    QUERY_PROJECTS_BREAKDOWN,
    QUERY_SESSIONS_BREAKDOWN,
    QUERY_TOOL_TOTALS
)

DB_PATH = os.path.expanduser("~/.local/state/openusage/telemetry.db")
COPILOT_DB_PATH = os.path.expanduser("~/.copilot/session-store.db")
TOKENTOP_DB_PATH = os.path.expanduser("~/.local/share/tokentop/usage.db")

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
    if not os.path.exists(path):
        return None
    try:
        conn = sqlite3.connect(path)
        # return rows as dicts for convenience
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to database at {path}: {e}", file=sys.stderr)
        return None

def query_copilot_db():
    # Returns (input, output, total, requests)
    if not os.path.exists(COPILOT_DB_PATH):
        return 0, 0, 0, 0
    try:
        conn = sqlite3.connect(COPILOT_DB_PATH)
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
    if not os.path.exists(TOKENTOP_DB_PATH):
        return []
    conn = get_db_connection(TOKENTOP_DB_PATH)
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
                "input_tokens": r['input_tokens'],
                "output_tokens": r['output_tokens'],
                "cache_read_tokens": r['cache_read_tokens'],
                "cache_write_tokens": 0,
                "total_tokens": r['input_tokens'] + r['output_tokens'],
                "cost_usd": r['cost_usd'],
                "requests": r['request_count'],
                "status": "ok",
                "dedup_key": f"tokentop-{r['id']}"
            })
        conn.close()
        return rows
    except Exception as e:
        print(f"Warning: Failed to fetch tokentop events: {e}", file=sys.stderr)
        if conn: conn.close()
        return []

def fetch_all_events():
    conn = get_db_connection(DB_PATH)
    ou_events = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(QUERY_ALL_EVENTS)
            raw_rows = [dict(r) for r in cursor.fetchall()]
            ou_events = []
            for row in raw_rows:
                row['workspace_id'] = sanitize_field(row.get('workspace_id'))
                row['model_raw'] = sanitize_field(row.get('model_raw'))
                row['agent_name'] = sanitize_field(row.get('agent_name'))
                ou_events.append(row)
            conn.close()
        except Exception as e:
            print(f"Error running QUERY_ALL_EVENTS: {e}", file=sys.stderr)
            if conn: conn.close()
    else:
        print(f"Warning: OpenUsage database not found at {DB_PATH}", file=sys.stderr)

    tt_events = fetch_tokentop_events()
    if not tt_events:
        return ou_events

    # Build unique fingerprints of OpenUsage events to avoid duplicate logging
    # Fingerprint: (timestamp_10s_bucket, model, input_tokens, output_tokens)
    ou_fingerprints = set()
    for ev in ou_events:
        ts_str = ev['occurred_at']
        try:
            m = re.match(r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d)', ts_str)
            ts_bucket = m.group(1) + " " + m.group(2) if m else ts_str[:15]
        except Exception:
            ts_bucket = ts_str[:15]
        
        fingerprint = (
            ts_bucket,
            str(ev['model_raw']).lower(),
            ev['input_tokens'],
            ev['output_tokens']
        )
        ou_fingerprints.add(fingerprint)

    merged_events = list(ou_events)
    for ev in tt_events:
        ts_str = ev['occurred_at']
        try:
            m = re.match(r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d)', ts_str)
            ts_bucket = m.group(1) + " " + m.group(2) if m else ts_str[:15]
        except Exception:
            ts_bucket = ts_str[:15]

        fingerprint = (
            ts_bucket,
            str(ev['model_raw']).lower(),
            ev['input_tokens'],
            ev['output_tokens']
        )
        
        if fingerprint not in ou_fingerprints:
            merged_events.append(ev)

    merged_events.sort(key=lambda x: x['occurred_at'] or '')
    return merged_events


def fetch_daily_rollup():
    conn = get_db_connection(DB_PATH)
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
        if conn: conn.close()
        return []

def fetch_projects_breakdown():
    conn = get_db_connection(DB_PATH)
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
        if conn: conn.close()
        return []

def fetch_sessions_breakdown():
    conn = get_db_connection(DB_PATH)
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
        if conn: conn.close()
        return []

def fetch_tool_totals():
    conn = get_db_connection(DB_PATH)
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
        if conn: conn.close()
        return {}

def fetch_balance_observations():
    conn = get_db_connection(DB_PATH)
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
        if conn: conn.close()
        return {}
