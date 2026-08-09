# gemini_antigravity.py
"""Gemini / Antigravity brain-log collector (ESTIMATED tokens - no fabrication).

Scans ~/.gemini/*/brain/<session>/.system_generated/logs/ for:
  1. transcript_full.jsonl (complete, untruncated logs)
  2. transcript.jsonl (compact logs)
  3. overview.txt (IDE session logs, same JSONL format)

Features:
  - Dynamic model tracking: extracts <USER_SETTINGS_CHANGE> tags turn-by-turn
    to accurately detect model switches (e.g., Claude Sonnet 4.6, Claude Opus 4.6,
    Gemini 3.6 Flash, Gemini 3.1 Pro). Falls back to settings.json in the
    brain's parent directory if no in-session change tag is present.
  - Accurate provider attribution ('anthropic' vs 'google' vs 'openai').
  - agent_name distinguishes 'gemini_ide' vs 'gemini_cli' by brain_dir path.
  - Context-aware prompt token modeling: accumulates conversation context (user inputs,
    tool execution payloads, and prior turns) to reflect real LLM prompt context windows.
    Resets the accumulator when step_index rolls back to 0 (session restart detection).
  - Deterministic token estimation from content length (len/4 heuristic).
  - Flags every event status='estimated' (never fabricated).
  - seen_sessions is global across all brain_dirs to prevent double-counting.
"""
import json
import os
import re

from .. import config
from .base import BaseCollector

EXCLUDED_PROJECT_DIRS = {
    "Downloads", "Documents", "Desktop", "Music", "Pictures", "Videos",
    "Templates", ".gemini", ".local", ".config", ".cache", ".claude",
    ".tokstat",
}

# Matches:  Model Selection` from <anything> to <New Model Name>
# Uses MULTILINE so $ anchors to end-of-line, stopping at the period in "4.6".
MODEL_CHANGE_RE = re.compile(
    r"Model Selection`\s+from\s+\S.*?\s+to\s+(.+?)(?:\.\s|\.$|\s*$)",
    re.IGNORECASE | re.MULTILINE,
)

TARGET_LOG_FILES = ["transcript_full.jsonl", "transcript.jsonl", "overview.txt"]

# Map brain_dir suffix → agent_name label
_AGENT_NAME_MAP = {
    "antigravity-cli": "gemini_cli",
    "antigravity":     "gemini_ide",
}


def _agent_name_for_brain_dir(brain_dir: str) -> str:
    """Return 'gemini_cli' or 'gemini_ide' based on the brain dir path."""
    for suffix, name in _AGENT_NAME_MAP.items():
        if suffix in brain_dir:
            return name
    return "gemini_cli"


def normalize_antigravity_model(raw_name: str) -> tuple[str, str]:
    """Extracts canonical model identifier and provider_id from raw settings string.

    Strips parenthetical qualifiers like '(Thinking)' or '(High)', then
    lowercases and hyphenates the result.
    """
    clean = re.sub(r"\s*\([^)]*\)", "", raw_name).strip()
    clean_lower = clean.lower()

    if "claude" in clean_lower:
        provider = "anthropic"
    elif "gpt" in clean_lower or "o1" in clean_lower or "o3" in clean_lower:
        provider = "openai"
    else:
        provider = "google"

    canonical = clean_lower.replace(" ", "-")
    return canonical, provider


def _load_settings_model(brain_dir: str) -> tuple[str, str]:
    """Read settings.json next to the brain dir to get the configured model.

    Walks up from <root>/brain to <root>/settings.json.  Returns
    (canonical_model, provider) or the safe default ('gemini-2.5-flash', 'google').
    """
    default = ("gemini-2.5-flash", "google")
    # brain_dir is e.g. ~/.gemini/antigravity-cli/brain
    parent = os.path.dirname(brain_dir)          # ~/.gemini/antigravity-cli
    settings_path = os.path.join(parent, "settings.json")
    if not os.path.isfile(settings_path):
        return default
    try:
        with open(settings_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        raw = data.get("model", "")
        if raw:
            return normalize_antigravity_model(raw)
    except (OSError, json.JSONDecodeError):
        pass
    return default


class GeminiAntigravityCollector(BaseCollector):
    name = "gemini_antigravity"

    def poll(self, bookmark: dict):
        files_state = bookmark.get("files", {})
        new_state = {}
        events = []

        # Global across all brain_dirs — prevents double-counting if a session
        # UUID somehow appears under both IDE and CLI brain directories.
        seen_sessions: set[str] = set()

        for brain_dir in config.GEMINI_BRAIN_DIRS:
            if not os.path.isdir(brain_dir):
                continue

            agent_name = _agent_name_for_brain_dir(brain_dir)
            settings_model, settings_provider = _load_settings_model(brain_dir)

            for root, _dirs, files in os.walk(brain_dir):
                found_target = None
                for target in TARGET_LOG_FILES:
                    if target in files:
                        found_target = os.path.join(root, target)
                        break

                if not found_target:
                    continue

                session_id = self._extract_session(found_target)
                if session_id in seen_sessions:
                    continue
                seen_sessions.add(session_id)

                try:
                    mtime = os.path.getmtime(found_target)
                except OSError:
                    continue

                if files_state.get(found_target) == mtime:
                    new_state[found_target] = mtime
                    continue

                parsed_events = self._parse_log_file(
                    found_target, session_id, agent_name,
                    settings_model, settings_provider,
                )
                events.extend(parsed_events)
                new_state[found_target] = mtime

        return events, {"files": new_state}

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _extract_session(path: str) -> str:
        parts = path.split(os.sep)
        for i, part in enumerate(parts):
            if part in (".system_generated", "logs") and i > 0:
                for candidate in reversed(parts[:i]):
                    if candidate and candidate not in (
                        "brain", ".gemini", "antigravity", "antigravity-cli",
                    ):
                        return candidate
        parent = os.path.basename(os.path.dirname(path))
        if parent and parent not in (
            "brain", ".gemini", "antigravity", "antigravity-cli",
            "logs", ".system_generated",
        ):
            return parent
        return "Global/No Session"

    def _parse_log_file(
        self,
        path: str,
        session_id: str,
        agent_name: str,
        settings_model: str,
        settings_provider: str,
    ):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            return []

        project = self._extract_project(lines)
        events = []

        # Use the settings.json value as the starting default — this fixes the
        # "initial model always gemini-3.5-flash" bug by grounding the default
        # in the actual user configuration rather than a hardcoded constant.
        current_model = settings_model
        current_provider = settings_provider
        accumulated_context_tokens = 0
        last_step_index = -1

        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue

            content = str(step.get("content") or "")
            tool_calls = step.get("tool_calls") or []
            step_idx = step.get("step_index", line_num)

            # Session restart detection: step_index rolled back to 0 (or below
            # the previous index unexpectedly) — reset the context accumulator.
            if isinstance(step_idx, int) and step_idx <= 0 and last_step_index > 0:
                accumulated_context_tokens = 0
            last_step_index = step_idx if isinstance(step_idx, int) else last_step_index

            # Check for model switch tags in content
            m = MODEL_CHANGE_RE.search(content)
            if m:
                raw_name = m.group(1).strip()
                if raw_name and raw_name.lower() not in ("none", "<model name>", ""):
                    current_model, current_provider = normalize_antigravity_model(raw_name)

            # Measure step payload
            content_tokens = max(1, len(content) // 4) if content else 0
            tool_tokens = (
                max(1, len(json.dumps(tool_calls, default=str)) // 4)
                if tool_calls else 0
            )
            step_tokens = content_tokens + tool_tokens

            # Accumulate prompt context for subsequent turns
            accumulated_context_tokens += step_tokens

            if step.get("source") != "MODEL" or step.get("status") != "DONE":
                continue

            created_at = step.get("created_at")
            if not created_at:
                continue

            # Input tokens = accumulated conversation context presented to model
            input_est = max(1, accumulated_context_tokens)
            output_est = max(1, step_tokens)

            # Estimate cache read tokens for multi-turn prefix reuse
            cache_read_est = max(0, input_est - step_tokens) if input_est > step_tokens else 0

            # dedup_key must include created_at: dedup_key is UNIQUE in the schema
            # and step_index rolls back to 0 on session restarts (and on file
            # truncate-and-rewrite). Without a time discriminator, a restarted
            # session's steps would collide with the original session's and be
            # silently dropped by INSERT OR IGNORE.
            events.append({
                "event_id": None,
                "occurred_at": created_at,
                "provider_id": current_provider,
                "agent_name": agent_name,
                "workspace_id": project,
                "session_id": session_id,
                "turn_id": str(step_idx),
                "event_type": "message_usage",
                "model_raw": current_model,
                "model_canonical": current_model,
                "input_tokens": input_est,
                "output_tokens": output_est,
                "cache_read_tokens": cache_read_est,
                "cache_write_tokens": 0,
                "total_tokens": input_est + output_est,
                "cost_usd": 0.0,
                "requests": 1,
                "status": "estimated",
                "dedup_key": f"antigravity-{session_id}-{step_idx}-{created_at}",
            })

        return events

    @staticmethod
    def _extract_project(lines) -> str:
        """Find the user's project name in the transcript content using the
        real home directory (never a hardcoded username)."""
        home = os.path.expanduser("~")
        if not home or home == "~":
            return "Global/No Project"
        pattern = re.compile(re.escape(home) + r"/([^/ \n\t\r\"']+)/")
        for line in lines[:200]:
            m = pattern.search(line)
            if m and m.group(1) not in EXCLUDED_PROJECT_DIRS:
                return m.group(1)
        return "Global/No Project"
