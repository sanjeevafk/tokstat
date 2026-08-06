# config.py
"""Centralized configuration and database connectivity for TokStat.

All filesystem paths live here (never hardcode them in other modules).
Environment overrides:
  TOKSTAT_DIR            - override the data directory (default ~/.tokstat)
  TOKSTAT_SYNC_LEGACY    - "0" disables automatic legacy-sync/migration
                           (pure self-reliant mode). Explicit `tokstat migrate`
                           is unaffected by this flag.
"""
import os
import sqlite3

# --- Data directory & native database -------------------------------------
TOKSTAT_DIR = os.environ.get("TOKSTAT_DIR") or os.path.expanduser("~/.tokstat")
DB_PATH = os.path.join(TOKSTAT_DIR, "telemetry.db")
DAEMON_PID_PATH = os.path.join(TOKSTAT_DIR, "daemon.pid")
DAEMON_LOG_PATH = os.path.join(TOKSTAT_DIR, "daemon.log")

# --- Dashboard / export output paths --------------------------------------
DASHBOARD_PATH = os.path.abspath("tokstat_dashboard.html")
COMPAT_DASHBOARD_PATH = os.path.abspath("openusage_dashboard.html")
EXPORT_DASHBOARD_NAME = "observatory_dashboard.html"

# --- Optional legacy / third-party sources (read-only, augmentary) --------
LEGACY_OPENUSAGE_DB = os.path.expanduser("~/.local/state/openusage/telemetry.db")
LEGACY_TOKENTOP_DB = os.path.expanduser("~/.local/share/tokentop/usage.db")
COPILOT_DB = os.path.expanduser("~/.copilot/session-store.db")
CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
GEMINI_BRAIN_DIRS = [
    os.path.expanduser(p)
    for p in ("~/.gemini/antigravity/brain", "~/.gemini/antigravity-cli/brain")
]
CURSOR_STATE_DB = os.path.expanduser(
    "~/.config/Cursor/User/globalStorage/state.vscdb"
)

# --- Behavior switches -----------------------------------------------------
SYNC_LEGACY = os.environ.get("TOKSTAT_SYNC_LEGACY", "1") == "1"

# --- Runtime tuning ---------------------------------------------------------
WATCH_POLL_INTERVAL_SEC = 3
COLLECTOR_POLL_INTERVAL_SEC = 5
COLLECTOR_BACKOFF_MIN_SEC = 1
COLLECTOR_BACKOFF_MAX_SEC = 5
SERVER_HOST = "127.0.0.1"  # localhost only - telemetry must never leave the machine
SERVER_PORT = 5000


def ensure_tokstat_dir() -> None:
    """Create the data directory if it does not exist yet."""
    os.makedirs(TOKSTAT_DIR, exist_ok=True)


def connect_db(path: str | None = None) -> sqlite3.Connection:
    """Open (creating if needed) the native TokStat database.

    Enables WAL mode, a 5s busy timeout and NORMAL synchronous for safe
    concurrent access between the daemon, CLI and ingestion server.
    The schema is bootstrapped lazily via migration.ensure_schema.
    """
    from . import migration  # lazy import to avoid a circular dependency

    path = path or DB_PATH
    ensure_tokstat_dir()
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    migration.ensure_schema(conn)
    return conn
