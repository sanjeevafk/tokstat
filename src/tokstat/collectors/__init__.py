# collectors/__init__.py
"""Embedded telemetry collectors: poll local tool data into usage_events.

Priority order (highest value / most accurate first):
  legacy_sync (OpenUsage+Tokentop augmentary history) > claude_code (real) >
  aider (real) > gemini_antigravity (estimated) > copilot (estimated) >
  vscode_cursor (spike, usually no-op).
"""
import sys

from .aider import AiderCollector
from .base import EVENT_COLUMNS, BaseCollector  # noqa: F401
from .claude_code import ClaudeCodeCollector
from .copilot import CopilotCollector
from .gemini_antigravity import GeminiAntigravityCollector
from .legacy_sync import LegacySyncCollector
from .vscode_cursor import VSCodeCursorCollector

COLLECTOR_CLASSES = [
    LegacySyncCollector,
    ClaudeCodeCollector,
    AiderCollector,
    GeminiAntigravityCollector,
    CopilotCollector,
    VSCodeCursorCollector,
]


def get_collectors():
    return [cls() for cls in COLLECTOR_CLASSES]


def run_collectors_once(conn=None) -> list[dict]:
    """Run every collector once against the native DB. Returns per-collector
    summaries. Creates its own connection unless one is passed in."""
    from .. import config

    own_conn = conn is None
    if own_conn:
        conn = config.connect_db()
    results = []
    try:
        for collector in get_collectors():
            try:
                res = collector.run_once(conn)
            except Exception as exc:
                # One broken source must never abort the remaining collectors
                # (or the bare `tokstat` pipeline that calls us).
                res = {"collector": type(collector).__name__, "error": str(exc)}
                print(f"[collect] {res}", file=sys.stderr)
            results.append(res)
            print(f"[collect] {res}")
    finally:
        if own_conn:
            conn.close()
    return results
