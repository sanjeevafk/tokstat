# sync.py
"""Opt-in provider usage poller (writes balance_observations).

`tokstat sync` pulls authoritative all-time token/cost totals from the
providers' usage APIs and writes them into balance_observations using the
metric-key vocabulary that analytics.compute_analytics() already reconciles
(see docs/hybrid_sync_plan.md). This closes the accuracy gap for tools whose
local logs TokStat can only estimate, without giving up the local-first
default.

Contract (non-negotiable, mirrored in docs/hybrid_sync_plan.md):
  * No outbound by default. Runs only on explicit `tokstat sync`, or when the
    daemon has [sync] enabled = true (interval-guarded via collector_state).
  * Credentials are discovered from existing local config; nothing is stored
    outside ~/.tokstat, and keys never appear in telemetry.
  * A provider failure is isolated: other providers still sync; the exit code
    is non-zero only if every *attempted* provider failed.
  * Google Gemini has no API-key usage endpoint (usage is exposed only via
    Google Cloud Billing / BigQuery), so it is skipped with a documented
    reason rather than guessed.
"""
import datetime
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from . import config
from .collectors.base import now_iso

# --- metric vocabulary (must match analytics.compute_analytics) ------------
KEY_INPUT = "client_ide_input_tokens"
KEY_OUTPUT = "client_ide_output_tokens"
KEY_CACHED = "client_ide_cached_tokens"
KEY_CODEX_INPUT = "provider_codex_input_tokens"
KEY_CODEX_OUTPUT = "provider_codex_output_tokens"
KEY_CODEX_CACHED = "provider_codex_cached_tokens"
KEY_COST_ANTHROPIC = "all_time_api_cost"
KEY_COST_OPENAI = "total_cost_usd"

_BALANCE_COLUMNS = [
    "provider_id", "account_id", "metric_key", "observed_at",
    "used", "limit_val", "remaining", "unit", "semantics",
]

_HTTP_TIMEOUT_SEC = 20.0
_MAX_PAGES = 12

# Codex CLI's public OAuth client id (device flow); used only to refresh an
# existing ~/.codex/auth.json token rather than require a fresh login.
CODEX_OAUTH_CLIENT_ID = "OzTWHgL3GgL6iDSNrkC6GZtT6jDVs0n4"
OPENAI_OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"

ANTHROPIC_USAGE_URL = (
    "https://api.anthropic.com/v1/organizations/usage_report/claude_code"
)
ANTHROPIC_COST_URL = "https://api.anthropic.com/v1/organizations/cost_report"
OPENAI_USAGE_URL = "https://api.openai.com/v1/organization/usage/completions"
OPENAI_COST_URL = "https://api.openai.com/v1/organization/costs"


class ProviderError(Exception):
    """A provider poll failed in a way that should be reported, not raised."""


class ProviderAuthError(ProviderError):
    """Authentication/authorization problem (missing key, 401/403, expired token)."""


# --- HTTP ------------------------------------------------------------------
def _http_get_json(url: str, headers: dict):
    """GET a JSON payload; raises ProviderError/ProviderAuthError on failure."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SEC) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ProviderAuthError(f"HTTP {exc.code} {exc.reason} ({url})")
        raise ProviderError(f"HTTP {exc.code} {exc.reason} ({url})")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ProviderError(f"request failed: {exc}")


def _fetch_paginated(url: str, headers: dict) -> dict:
    """GET url, following next_page cursors; returns merged {"data": [...]}.

    Provider usage APIs page over time buckets; merging pages gives one flat
    list for the normalizers. Capped at _MAX_PAGES to stay bounded.
    """
    merged = []
    page_url = url
    for _ in range(_MAX_PAGES):
        payload = _http_get_json(page_url, headers)
        if not isinstance(payload, dict):
            break
        data = payload.get("data")
        if isinstance(data, list):
            merged.extend(data)
        next_page = payload.get("next_page")
        if not next_page:
            break
        sep = "&" if "?" in page_url else "?"
        page_url = f"{page_url}{sep}page={urllib.parse.quote(str(next_page))}"
    return {"data": merged}


# --- credential discovery (read-only, existing local config) ---------------
def _discover_anthropic_key() -> Optional[str]:
    """Existing Anthropic credentials: env or Claude Code settings files.

    The usage report API requires an Admin API key; a regular key will surface
    a clear auth error at sync time rather than being guessed at here.
    """
    for var in ("ANTHROPIC_ADMIN_KEY", "ANTHROPIC_API_KEY"):
        val = os.environ.get(var)
        if val:
            return val.strip()
    for path in (
        os.path.expanduser("~/.claude/settings.json"),
        os.path.expanduser("~/.config/claude/settings.json"),
    ):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        env = data.get("env")
        if isinstance(env, dict) and env.get("ANTHROPIC_API_KEY"):
            return str(env["ANTHROPIC_API_KEY"]).strip()
    return None


def _discover_openai_credentials() -> Optional[dict]:
    """Existing OpenAI credentials: env key, or ~/.codex/auth.json.

    Returns {"type": "api_key", "key": ...} or an oauth dict with
    access_token / refresh_token / expires_at (epoch sec, may be None).
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return {"type": "api_key", "key": api_key.strip()}
    auth_path = os.path.expanduser("~/.codex/auth.json")
    try:
        with open(auth_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    # Codex stores either an API-key entry or an OAuth tokens block.
    key_entry = data.get("OPENAI_API_KEY")
    if isinstance(key_entry, dict) and key_entry.get("key"):
        return {"type": "api_key", "key": str(key_entry["key"])}
    tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else data
    access = tokens.get("access_token")
    if not access:
        return None
    expires_at = tokens.get("expires_at")
    try:
        expires_at = float(expires_at) if expires_at is not None else None
    except (TypeError, ValueError):
        expires_at = None
    return {
        "type": "oauth",
        "access_token": str(access),
        "refresh_token": str(tokens.get("refresh_token") or "") or None,
        "expires_at": expires_at,
    }


def _oauth_refresh(refresh_token: str) -> str:
    """Exchange a refresh token for a fresh access token (Codex device flow)."""
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CODEX_OAUTH_CLIENT_ID,
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_OAUTH_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
        raise ProviderAuthError(f"OAuth token refresh failed: {exc}")
    token = data.get("access_token")
    if not token:
        raise ProviderAuthError("OAuth token refresh returned no access_token")
    return str(token)


# --- normalization ---------------------------------------------------------
def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sanitize_model(name) -> str:
    """Model key fragment: lowercase, non-alnum -> underscore."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def _extract_buckets(payload) -> list:
    """Flatten a usage/cost report into a list of result entries."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    entries = []
    for bucket in data:
        if not isinstance(bucket, dict):
            continue
        results = bucket.get("results")
        if isinstance(results, list):
            entries.extend(results)
        else:
            entries.append(bucket)
    return entries


def _normalize_anthropic(usage_payload, cost_payload) -> dict:
    """Map Anthropic usage/cost reports to the client_ide_* vocabulary.

    Response shapes evolve; each bucket entry is scanned for whichever token
    fields are present and summed. Cost is taken from total_cost_usd / cost_usd
    (USD) when present, else from the cost report's amount values.
    """
    totals = {"input": 0.0, "output": 0.0, "cached": 0.0, "cost": 0.0}
    models = {}
    for entry in _extract_buckets(usage_payload):
        uncached = _as_float(entry.get("uncached_input_tokens"))
        cached = _as_float(entry.get("cached_input_tokens"))
        cache_write = _as_float(entry.get("cache_creation_input_tokens"))
        output = _as_float(entry.get("output_tokens"))
        in_tok = _as_float(entry.get("input_tokens"))
        if not any((uncached, cached, cache_write, output, in_tok)):
            continue  # not a token row (e.g. requests-only aggregate)
        input_tok = in_tok or (uncached + cached)
        cached_tot = cached + cache_write
        cost = _as_float(entry.get("total_cost_usd")) or _as_float(entry.get("cost_usd"))
        totals["input"] += input_tok
        totals["output"] += output
        totals["cached"] += cached_tot
        totals["cost"] += cost
        name = entry.get("model")
        if name:
            m = models.setdefault(
                _sanitize_model(name),
                {"input": 0.0, "output": 0.0, "cached": 0.0, "cost": 0.0},
            )
            m["input"] += input_tok
            m["output"] += output
            m["cached"] += cached_tot
            m["cost"] += cost
    # Cost is best-effort and only ever taken from clearly-USD-named fields
    # (total_cost_usd / cost_usd). Anthropic's cost_report `amount` values are
    # documented in cents in some doc versions; guessing the unit could inflate
    # the total ~100x, so ambiguous amounts are deliberately skipped.
    for entry in _extract_buckets(cost_payload):
        totals["cost"] += (
            _as_float(entry.get("total_cost_usd"))
            or _as_float(entry.get("cost_usd"))
        )
    return {"totals": totals, "models": models}


def _normalize_openai(usage_payload, cost_payload) -> dict:
    """Map OpenAI organization usage/cost reports to the provider_codex_* keys."""
    totals = {"input": 0.0, "output": 0.0, "cached": 0.0, "cost": 0.0}
    models = {}
    for entry in _extract_buckets(usage_payload):
        in_tok = _as_float(entry.get("input_tokens"))
        out_tok = _as_float(entry.get("output_tokens"))
        cached = _as_float(entry.get("input_cached_tokens"))
        if not any((in_tok, out_tok, cached)):
            continue
        totals["input"] += in_tok
        totals["output"] += out_tok
        totals["cached"] += cached
        name = entry.get("model")
        if name:
            m = models.setdefault(
                _sanitize_model(name),
                {"input": 0.0, "output": 0.0, "cached": 0.0, "cost": 0.0},
            )
            m["input"] += in_tok
            m["output"] += out_tok
            m["cached"] += cached
    for entry in _extract_buckets(cost_payload):
        amount = entry.get("amount")
        if isinstance(amount, dict) and str(amount.get("currency", "usd")).lower() == "usd":
            totals["cost"] += _as_float(amount.get("value"))
    return {"totals": totals, "models": models}


def _metrics_from_normalized(
    norm: dict, input_key: str, output_key: str, cached_key: str, cost_key: str
) -> dict:
    """Flatten normalized totals+models into metric-key -> value (zeros dropped)."""
    metrics = {}
    t = norm["totals"]
    if t["input"] > 0:
        metrics[input_key] = t["input"]
    if t["output"] > 0:
        metrics[output_key] = t["output"]
    if t["cached"] > 0:
        metrics[cached_key] = t["cached"]
    if t["cost"] > 0:
        metrics[cost_key] = t["cost"]
    for mname, m in norm["models"].items():
        base = f"model_{mname}"
        if m["input"] > 0:
            metrics[f"{base}_input_tokens"] = m["input"]
        if m["output"] > 0:
            metrics[f"{base}_output_tokens"] = m["output"]
        if m["cached"] > 0:
            metrics[f"{base}_cached_tokens"] = m["cached"]
        if m["cost"] > 0:
            metrics[f"{base}_cost_usd"] = m["cost"]
    return metrics


# --- provider fetchers -----------------------------------------------------
def _fetch_anthropic(key: str, lookback_days: int) -> dict:
    start = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=lookback_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    usage_url = (
        f"{ANTHROPIC_USAGE_URL}?starting_at={urllib.parse.quote(start)}"
        f"&bucket_width=1d&limit=180&group_by%5B%5D=model"
    )
    usage_payload = _fetch_paginated(usage_url, headers)
    cost_payload = None
    try:
        cost_url = (
            f"{ANTHROPIC_COST_URL}?starting_at={urllib.parse.quote(start)}"
            f"&bucket_width=1d&limit=180"
        )
        cost_payload = _fetch_paginated(cost_url, headers)
    except ProviderError:
        cost_payload = None  # tokens still sync; cost is best-effort
    return _normalize_anthropic(usage_payload, cost_payload)


def _fetch_openai(credentials: dict, lookback_days: int) -> dict:
    now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    start_ts = now_ts - lookback_days * 86400
    headers = {
        "Authorization": f"Bearer {credentials['access_token']}",
        "Content-Type": "application/json",
    }
    usage_url = (
        f"{OPENAI_USAGE_URL}?start_time={start_ts}&end_time={now_ts}"
        f"&bucket_width=1d&limit=180&group_by=model"
    )
    usage_payload = _fetch_paginated(usage_url, headers)
    cost_payload = None
    try:
        cost_url = (
            f"{OPENAI_COST_URL}?start_time={start_ts}&end_time={now_ts}"
            f"&bucket_width=1d&limit=180"
        )
        cost_payload = _fetch_paginated(cost_url, headers)
    except ProviderError:
        cost_payload = None
    return _normalize_openai(usage_payload, cost_payload)


def _fetch_openai_with_refresh(credentials: dict, lookback_days: int) -> dict:
    """Fetch OpenAI usage with OAuth token lifecycle handling.

    - Proactively refreshes an OAuth token whose expires_at has passed.
    - On an auth failure with a refresh token available, refreshes once and
      retries before giving up.
    """
    creds = credentials
    if (
        creds.get("type") == "oauth"
        and creds.get("refresh_token")
        and creds.get("expires_at") is not None
        and creds["expires_at"]
        < datetime.datetime.now(datetime.timezone.utc).timestamp()
    ):
        creds = dict(creds, access_token=_oauth_refresh(creds["refresh_token"]))
    try:
        return _fetch_openai(creds, lookback_days)
    except ProviderAuthError:
        if creds.get("type") != "oauth" or not creds.get("refresh_token"):
            raise
        fresh = _oauth_refresh(creds["refresh_token"])
        return _fetch_openai(dict(creds, access_token=fresh), lookback_days)


# --- write path ------------------------------------------------------------
def _write_observations(
    conn, provider_id: str, account_id: str, metrics: dict,
    semantics: str = "all_time",
) -> int:
    """INSERT OR REPLACE observations (skips zero/absent values)."""
    observed_at = now_iso()
    placeholders = ", ".join("?" * len(_BALANCE_COLUMNS))
    cols = ", ".join(_BALANCE_COLUMNS)
    written = 0
    for key, value in metrics.items():
        if value is None or value <= 0:
            continue
        unit = (
            "usd"
            if key.endswith("_cost_usd")
            or key in (KEY_COST_ANTHROPIC, KEY_COST_OPENAI)
            else "tokens"
        )
        conn.execute(
            f"INSERT OR REPLACE INTO balance_observations ({cols}) VALUES ({placeholders})",
            (provider_id, account_id, key, observed_at, float(value), None, None, unit, semantics),
        )
        written += 1
    if written:
        conn.commit()
    return written


# --- per-provider sync steps -----------------------------------------------
def _sync_anthropic(conn, lookback_days: int) -> dict:
    key = _discover_anthropic_key()
    if not key:
        return {
            "status": "skipped",
            "reason": "no credentials found (ANTHROPIC_API_KEY env or ~/.claude/settings.json)",
        }
    try:
        norm = _fetch_anthropic(key, lookback_days)
        metrics = _metrics_from_normalized(
            norm, KEY_INPUT, KEY_OUTPUT, KEY_CACHED, KEY_COST_ANTHROPIC
        )
        written = _write_observations(conn, "anthropic", "default", metrics)
        return {
            "status": "ok",
            "observations_written": written,
            "total_tokens": int(
                norm["totals"]["input"] + norm["totals"]["output"] + norm["totals"]["cached"]
            ),
        }
    except ProviderAuthError as exc:
        return {
            "status": "error",
            "reason": f"{exc}. The usage report API requires an Anthropic Admin API key (ANTHROPIC_ADMIN_KEY).",
        }
    except ProviderError as exc:
        return {"status": "error", "reason": str(exc)}


def _sync_openai(conn, lookback_days: int) -> dict:
    credentials = _discover_openai_credentials()
    if not credentials:
        return {
            "status": "skipped",
            "reason": "no credentials found (OPENAI_API_KEY env or ~/.codex/auth.json)",
        }
    try:
        norm = _fetch_openai_with_refresh(credentials, lookback_days)
        metrics = _metrics_from_normalized(
            norm, KEY_CODEX_INPUT, KEY_CODEX_OUTPUT, KEY_CODEX_CACHED, KEY_COST_OPENAI
        )
        written = _write_observations(conn, "openai", "default", metrics)
        return {
            "status": "ok",
            "observations_written": written,
            "total_tokens": int(
                norm["totals"]["input"] + norm["totals"]["output"] + norm["totals"]["cached"]
            ),
        }
    except ProviderAuthError as exc:
        return {
            "status": "error",
            "reason": f"{exc}. The organization usage API needs an Admin API key or an authorized Codex session.",
        }
    except ProviderError as exc:
        return {"status": "error", "reason": str(exc)}


# --- public entry points ---------------------------------------------------
def run_sync_once(conn=None, lookback_days: Optional[int] = None) -> dict:
    """Run every provider poll once and write observations.

    Never raises for a provider failure; returns per-provider results and an
    exit_code that is non-zero only when every attempted provider errored
    (permanent documented skips such as Google do not count as failures).
    """
    own_conn = conn is None
    if own_conn:
        conn = config.connect_db()
    settings = config.sync_settings()
    lookback = int(lookback_days or settings.get("lookback_days") or 365)
    providers = {}
    try:
        providers["anthropic"] = _sync_anthropic(conn, lookback)
        providers["openai"] = _sync_openai(conn, lookback)
        providers["google"] = {
            "status": "skipped",
            "reason": (
                "Google has no API-key usage endpoint; usage is exposed only via "
                "Google Cloud Billing / Vertex (out of scope for the local-first poller)"
            ),
        }
    finally:
        if own_conn:
            conn.close()
    attempted = [r for r in providers.values() if r.get("status") in ("ok", "error")]
    errored = [r for r in attempted if r.get("status") == "error"]
    exit_code = 1 if attempted and len(errored) == len(attempted) else 0
    return {"providers": providers, "exit_code": exit_code}


_SYNC_STATE_ID = "provider_sync"


def maybe_sync(conn=None, force: bool = False):
    """Interval-guarded daemon entry point.

    Returns the run_sync_once() result dict, or None when the interval has not
    elapsed. Uses the existing collector_state table for the last-run stamp.
    """
    own_conn = conn is None
    if own_conn:
        conn = config.connect_db()
    settings = config.sync_settings()
    try:
        if not force:
            row = conn.execute(
                "SELECT bookmark FROM collector_state WHERE collector_id = ?",
                (_SYNC_STATE_ID,),
            ).fetchone()
            last = None
            if row and row["bookmark"]:
                try:
                    last = json.loads(row["bookmark"]).get("last_sync_at")
                except (ValueError, TypeError):
                    last = None
            if last:
                try:
                    last_dt = datetime.datetime.fromisoformat(last)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=datetime.timezone.utc)
                    elapsed_h = (
                        datetime.datetime.now(datetime.timezone.utc) - last_dt
                    ).total_seconds() / 3600.0
                except ValueError:
                    elapsed_h = float("inf")
                if elapsed_h < float(settings.get("interval_hours") or 6.0):
                    return None  # not due yet
        result = run_sync_once(conn=conn)
        conn.execute(
            "INSERT OR REPLACE INTO collector_state (collector_id, bookmark, updated_at) "
            "VALUES (?, ?, ?)",
            (_SYNC_STATE_ID, json.dumps({"last_sync_at": now_iso()}), now_iso()),
        )
        conn.commit()
        return result
    finally:
        if own_conn:
            conn.close()
