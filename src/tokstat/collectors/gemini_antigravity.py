# gemini_antigravity.py
"""Gemini Antigravity brain-log collector (ESTIMATED tokens - no fabrication).

The brain logs (~/.gemini/*/brain/<session>/.system_generated/logs/overview.txt)
contain real structure (step_index, source, status, created_at, content,
tool_calls) but NO token usage fields (verified 2026-08-06). We therefore:

  - record real structure: occurred_at, session_id, turn_id, workspace;
  - estimate tokens deterministically from content length (len/4 heuristic);
  - flag every event status='estimated' so dashboards never mislabel them;
  - NEVER use random values (Non-Negotiable #1).
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


class GeminiAntigravityCollector(BaseCollector):
    name = "gemini_antigravity"

    def poll(self, bookmark: dict):
        files_state = bookmark.get("files", {})
        new_state = {}
        events = []
        for brain_dir in config.GEMINI_BRAIN_DIRS:
            if not os.path.isdir(brain_dir):
                continue
            for root, _dirs, files in os.walk(brain_dir):
                if "overview.txt" not in files:
                    continue
                path = os.path.join(root, "overview.txt")
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if files_state.get(path) == mtime:
                    new_state[path] = mtime
                    continue
                session_id = self._extract_session(path)
                events.extend(self._parse_overview(path, session_id))
                new_state[path] = mtime
        return events, {"files": new_state}

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _extract_session(path: str) -> str:
        parts = path.split(os.sep)
        for i, part in enumerate(parts):
            if part == ".system_generated" and i > 0:
                return parts[i - 1]
        return "Global/No Session"

    def _parse_overview(self, path: str, session_id: str):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            return []
        project = self._extract_project(lines)

        events = []
        for line_num, line in enumerate(lines):
            try:
                step = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            if step.get("source") != "MODEL" or step.get("status") != "DONE":
                continue
            created_at = step.get("created_at")
            if not created_at:
                continue
            step_idx = step.get("step_index", line_num)
            content = str(step.get("content") or "")
            tool_calls = step.get("tool_calls") or []
            # Deterministic estimate: ~4 chars per token, min 1.
            input_est = max(1, len(content) // 4)
            output_est = max(1, len(json.dumps(tool_calls, default=str)) // 4)

            events.append({
                "event_id": None,
                "occurred_at": created_at,
                "provider_id": "google",
                "agent_name": "gemini_cli",
                "workspace_id": project,
                "session_id": session_id,
                "turn_id": str(step_idx),
                "event_type": "message_usage",
                "model_raw": "gemini-3.5-flash",
                "model_canonical": "gemini-3.5-flash",
                "input_tokens": input_est,
                "output_tokens": output_est,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "total_tokens": input_est + output_est,
                "cost_usd": 0.0,
                "requests": 1,
                "status": "estimated",
                "dedup_key": f"antigravity-ide-{session_id}-{step_idx}",
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
