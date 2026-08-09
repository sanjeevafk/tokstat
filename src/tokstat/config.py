# config.py
"""Centralized configuration and database connectivity for TokStat.

All filesystem paths live here (never hardcode them in other modules).
Environment overrides:
  TOKSTAT_DIR            - override the data directory (default ~/.tokstat)
  TOKSTAT_SYNC_LEGACY    - "0" disables automatic legacy-sync/migration
                           (pure self-reliant mode). Explicit `tokstat migrate`
                           is unaffected by this flag.
  TOKSTAT_CONFIG         - override the config.toml path (default ~/.tokstat/config.toml)
  TOKSTAT_PROXY_UPSTREAM - override the local-model proxy upstream URL
  TOKSTAT_PROXY_PORT     - override the local-model proxy listen port
  TOKSTAT_PROXY_AGENT_NAME - override the local-model proxy agent name
  TOKSTAT_SYNC_ENABLED     - "1" lets the daemon run `tokstat sync` on an
                             interval (opt-in provider usage polling; see
                             [sync] in config.toml)
"""
import os
import sqlite3
from typing import Optional

# --- Data directory & native database -------------------------------------
TOKSTAT_DIR = os.environ.get("TOKSTAT_DIR") or os.path.expanduser("~/.tokstat")
DB_PATH = os.path.join(TOKSTAT_DIR, "telemetry.db")
DAEMON_PID_PATH = os.path.join(TOKSTAT_DIR, "daemon.pid")
DAEMON_LOG_PATH = os.path.join(TOKSTAT_DIR, "daemon.log")
CONFIG_FILE = os.environ.get("TOKSTAT_CONFIG") or os.path.join(TOKSTAT_DIR, "config.toml")

# --- Local-model proxy (see docs/local_model_support_plan.md) -------------
PROXY_UPSTREAM = "http://localhost:11434"   # Ollama default
PROXY_LISTEN_PORT = 11435
PROXY_AGENT_NAME = "ollama_proxy"
PROXY_PROVIDER_ID = "local"
PROXY_PID_PATH = os.path.join(TOKSTAT_DIR, "proxy.pid")

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


# --- config.toml loading (stdlib only, no new runtime deps) -----------------
def _parse_toml_mini(text: str) -> dict:
    """Minimal TOML parser for the flat schema used by config.toml.

    Supports `[section]` / `[section.sub]` headers and `key = value` lines with
    strings, ints, floats, booleans and arrays of those. Deliberately small:
    enough for [proxy] and [pricing.overrides]; Python 3.9/3.10 have no
    tomllib, so this keeps the zero-dependency constraint on all supported
    runtimes. Returns nested dicts mirroring the section paths.
    """
    root: dict = {}
    section = root
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = root
            for part in line[1:-1].strip().split("."):
                section = section.setdefault(part.strip(), {})
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip().strip('"').strip("'")
        val = val.strip()
        if not key:
            continue
        if val.startswith('"') or val.startswith("'"):
            section[key] = val[1:-1]
        elif val == "true":
            section[key] = True
        elif val == "false":
            section[key] = False
        elif val.startswith("[") and val.endswith("]"):
            items: list = []
            for tok in val[1:-1].split(","):
                tok = tok.strip()
                if not tok:
                    continue
                if tok.startswith('"') or tok.startswith("'"):
                    items.append(tok[1:-1])
                elif tok == "true":
                    items.append(True)
                elif tok == "false":
                    items.append(False)
                else:
                    try:
                        items.append(int(tok))
                    except ValueError:
                        try:
                            items.append(float(tok))
                        except ValueError:
                            items.append(tok)
            section[key] = items
        else:
            try:
                section[key] = int(val)
            except ValueError:
                try:
                    section[key] = float(val)
                except ValueError:
                    section[key] = val
    return root


_config_cache = {"path": None, "mtime_ns": None, "data": {}}


def load_config() -> dict:
    """Read config.toml into a plain dict, cached by (path, mtime).

    Uses stdlib tomllib on Python 3.11+ and a small fallback parser on
    3.9/3.10. A missing or unparseable file yields {} (callers fall back to
    defaults). Environment overrides are applied by the typed getters below,
    never here.

    The result is cached and only re-read when the file's path or mtime
    changes, so hot paths (e.g. per-event cost estimation) don't hit the disk
    on every call. Edits to config.toml are picked up on the next read
    automatically.
    """
    try:
        mtime_ns = os.stat(CONFIG_FILE).st_mtime_ns
    except OSError:
        if _config_cache["path"] is not None:
            _config_cache["path"] = None
            _config_cache["mtime_ns"] = None
            _config_cache["data"] = {}
        return {}
    if _config_cache["path"] == CONFIG_FILE and _config_cache["mtime_ns"] == mtime_ns:
        return _config_cache["data"]
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}
    try:
        import tomllib  # Python 3.11+

        data = tomllib.loads(text)
    except ImportError:
        data = _parse_toml_mini(text)
    except Exception:
        data = {}
    _config_cache["path"] = CONFIG_FILE
    _config_cache["mtime_ns"] = mtime_ns
    _config_cache["data"] = data
    return data


def proxy_settings() -> dict:
    """Merged [proxy] settings: config.toml values overridden by env vars."""
    cfg = load_config().get("proxy") or {}
    toml_port = cfg.get("listen_port")
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "upstream": os.environ.get("TOKSTAT_PROXY_UPSTREAM") or cfg.get("upstream") or PROXY_UPSTREAM,
        # Keep 0 as a valid value (ephemeral port); only fall back when absent.
        "listen_port": int(
            os.environ.get("TOKSTAT_PROXY_PORT")
            if os.environ.get("TOKSTAT_PROXY_PORT") is not None
            else (toml_port if toml_port is not None else PROXY_LISTEN_PORT)
        ),
        "agent_name": os.environ.get("TOKSTAT_PROXY_AGENT_NAME") or cfg.get("agent_name") or PROXY_AGENT_NAME,
        "provider_id": str(cfg.get("provider_id") or PROXY_PROVIDER_ID),
    }


def pricing_overrides() -> dict:
    """[pricing.overrides] map: glob pattern -> [input_rate_per_1M, output_rate_per_1M]."""
    return (load_config().get("pricing") or {}).get("overrides") or {}


def gpu_cost_settings() -> dict:
    """[proxy.gpu_cost] optional electricity/cloud-GPU hourly cost (informational)."""
    return (load_config().get("proxy") or {}).get("gpu_cost") or {}


def sync_settings() -> dict:
    """Merged [sync] settings: config.toml values overridden by env vars.

    Controls the opt-in provider usage poller (`tokstat sync`): enabled makes
    the daemon run it on an interval; lookback_days is the provider history
    window; interval_hours is the minimum time between daemon-triggered runs.
    The bare `tokstat` command and the daemon default make NO outbound calls
    unless enabled here (see docs/hybrid_sync_plan.md).
    """
    cfg = load_config().get("sync") or {}
    env_enabled = os.environ.get("TOKSTAT_SYNC_ENABLED")
    return {
        "enabled": (
            (env_enabled == "1") if env_enabled is not None else bool(cfg.get("enabled", False))
        ),
        "lookback_days": int(cfg.get("lookback_days", 365)),
        "interval_hours": float(cfg.get("interval_hours", 6.0)),
        "anthropic_api_key": str(cfg.get("anthropic_api_key") or ""),
        "openai_api_key": str(cfg.get("openai_api_key") or ""),
    }

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


def connect_db(path: Optional[str] = None) -> sqlite3.Connection:
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
