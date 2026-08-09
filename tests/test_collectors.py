# test_collectors.py
import json
import os
import unittest
from unittest.mock import patch

from tokstat import config
from tokstat.collectors.aider import AiderCollector
from tokstat.collectors.claude_code import ClaudeCodeCollector
from tokstat.collectors.copilot import CopilotCollector
from tokstat.collectors.gemini_antigravity import GeminiAntigravityCollector
from tokstat.collectors.vscode_cursor import VSCodeCursorCollector

CLAUDE_LINES = [
    {"type": "assistant", "requestId": "req-1", "uuid": "u1",
     "timestamp": "2026-08-01T10:00:00Z",
     "message": {"model": "claude-sonnet-4.5", "usage": {
         "input_tokens": 1, "output_tokens": 50, "cache_read_input_tokens": 1000}}},
    {"type": "assistant", "requestId": "req-1", "uuid": "u1",
     "timestamp": "2026-08-01T10:00:01Z",
     "message": {"model": "claude-sonnet-4.5", "usage": {
         "input_tokens": 1, "output_tokens": 120, "cache_read_input_tokens": 1000}}},
    {"type": "assistant", "requestId": "req-1", "uuid": "u1",
     "timestamp": "2026-08-01T10:00:02Z",
     "message": {"model": "claude-sonnet-4.5", "usage": {
         "input_tokens": 5000, "output_tokens": 120, "cache_read_input_tokens": 1000,
         "cache_creation_input_tokens": 200}}},
    {"type": "user", "requestId": "req-2", "uuid": "u2",
     "timestamp": "2026-08-01T10:00:03Z", "message": {"role": "user", "content": "hi"}},
]

GEMINI_LINES = [
    {"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT",
     "status": "DONE", "created_at": "2026-05-20T16:22:01Z", "content": "hello"},
    {"step_index": 4, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
     "created_at": "2026-05-20T16:22:01Z",
     "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": '"/home/user/proj/file.py"'}}]},
    {"step_index": 8, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
     "created_at": "2026-05-20T16:22:08Z", "content": "I did the thing"},
]


class TestClaudeCodeCollector(unittest.TestCase):
    def _projects_dir(self):
        import tempfile
        return tempfile.mkdtemp(prefix="claude-projects-", dir=config.TOKSTAT_DIR)

    def test_streaming_dupes_merged_with_cache_aware_input(self):
        projects = self._projects_dir()
        tmp = os.path.join(projects, "-home-user-proj")
        os.makedirs(tmp, exist_ok=True)
        path = os.path.join(tmp, "session-1.jsonl")
        with open(path, "w") as f:
            for line in CLAUDE_LINES:
                f.write(json.dumps(line) + "\n")

        with patch.object(config, "CLAUDE_PROJECTS_DIR", projects):
            events, _bookmark = ClaudeCodeCollector().poll({})

        self.assertEqual(len(events), 1)  # 3 streaming lines -> 1 request
        ev = events[0]
        self.assertEqual(ev["dedup_key"], "claude-req-1")
        self.assertEqual(ev["status"], "ok")
        self.assertEqual(ev["input_tokens"], 5000)      # real input beats placeholder
        self.assertEqual(ev["output_tokens"], 120)       # highest streaming value
        self.assertEqual(ev["cache_read_tokens"], 1000)
        self.assertEqual(ev["cache_write_tokens"], 200)
        self.assertEqual(ev["total_tokens"], 5000 + 120 + 1000)  # no double count
        self.assertEqual(ev["agent_name"], "claude_code")

    def test_mtime_bookmark_skips_unchanged_files(self):
        projects = self._projects_dir()
        tmp = os.path.join(projects, "-home-user-proj2")
        os.makedirs(tmp, exist_ok=True)
        path = os.path.join(tmp, "session-2.jsonl")
        with open(path, "w") as f:
            for line in CLAUDE_LINES:
                f.write(json.dumps(line) + "\n")

        with patch.object(config, "CLAUDE_PROJECTS_DIR", projects):
            collector = ClaudeCodeCollector()
            events, bookmark = collector.poll({})
            self.assertEqual(len(events), 1)
            events2, _ = collector.poll(bookmark)
            self.assertEqual(events2, [])


class TestGeminiAntigravityCollector(unittest.TestCase):
    def _fixture(self):
        # Mimic the real dir structure so _load_settings_model can find settings.json:
        # <TOKSTAT_DIR>/antigravity-cli/brain/sess-uuid/.system_generated/logs/
        brain = os.path.join(config.TOKSTAT_DIR, "antigravity-cli", "brain", "sess-uuid", ".system_generated", "logs")
        os.makedirs(brain, exist_ok=True)
        # Write a settings.json one level above brain/
        settings_path = os.path.join(config.TOKSTAT_DIR, "antigravity-cli", "settings.json")
        if not os.path.exists(settings_path):
            import json as _json
            with open(settings_path, "w") as sf:
                _json.dump({"model": "Gemini 2.5 Flash"}, sf)
        path = os.path.join(brain, "overview.txt")
        with open(path, "w") as f:
            for line in GEMINI_LINES:
                f.write(json.dumps(line) + "\n")
        brain_dir = os.path.join(config.TOKSTAT_DIR, "antigravity-cli", "brain")
        return brain_dir, path

    def test_deterministic_estimated_events_no_fabrication(self):
        brain, _path = self._fixture()
        with patch.object(config, "GEMINI_BRAIN_DIRS", [brain]):
            collector = GeminiAntigravityCollector()
            events, _ = collector.poll({})
            events2, _ = collector.poll({})  # fresh parse -> identical numbers
            _events3, bookmark = collector.poll({})
            events4, _ = collector.poll(bookmark)  # mtime bookmark -> no re-scan

        self.assertEqual(len(events), 2)  # only MODEL/DONE steps
        for ev in events:
            self.assertEqual(ev["status"], "estimated")
            self.assertEqual(ev["agent_name"], "gemini_cli")
            self.assertEqual(ev["model_raw"], "gemini-2.5-flash")
            self.assertGreaterEqual(ev["input_tokens"], 1)
            self.assertGreaterEqual(ev["output_tokens"], 1)
            self.assertEqual(ev["total_tokens"], ev["input_tokens"] + ev["output_tokens"])
        # determinism: parsing the same file twice yields identical numbers
        self.assertEqual(
            [(e["input_tokens"], e["output_tokens"]) for e in events],
            [(e["input_tokens"], e["output_tokens"]) for e in events2],
        )
        self.assertEqual(events4, [])  # unchanged files are skipped

    def test_session_extraction_from_path(self):
        _brain_dir, path = self._fixture()
        session = GeminiAntigravityCollector._extract_session(path)
        self.assertEqual(session, "sess-uuid")

    def _make_brain(self, subdir: str) -> str:
        """Helper: create a logs dir and return its path."""
        brain = os.path.join(config.TOKSTAT_DIR, "brain", subdir, ".system_generated", "logs")
        os.makedirs(brain, exist_ok=True)
        return brain

    def _write_transcript(self, brain: str, lines: list, filename: str = "transcript_full.jsonl") -> str:
        path = os.path.join(brain, filename)
        with open(path, "w") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")
        return path

    # --- Bug 1 & 2: settings.json fallback + regex captures full version number ---
    def test_settings_json_fallback_no_change_tag(self):
        """When no USER_SETTINGS_CHANGE is present, model comes from settings.json."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fake_brain_dir = os.path.join(tmp, "antigravity-cli", "brain")
            os.makedirs(fake_brain_dir, exist_ok=True)
            settings_file = os.path.join(tmp, "antigravity-cli", "settings.json")
            with open(settings_file, "w") as f:
                json.dump({"model": "Claude Opus 4.6"}, f)
            log_dir = os.path.join(fake_brain_dir, "sess-a", ".system_generated", "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "transcript_full.jsonl")
            steps = [
                {"step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE",
                 "status": "DONE", "created_at": "2026-08-01T10:00:00Z",
                 "content": "Hello", "tool_calls": []},
            ]
            with open(log_path, "w") as f:
                for s in steps:
                    f.write(json.dumps(s) + "\n")

            with patch.object(config, "GEMINI_BRAIN_DIRS", [fake_brain_dir]):
                events, _ = GeminiAntigravityCollector().poll({})

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["model_raw"], "claude-opus-4.6")
        self.assertEqual(events[0]["provider_id"], "anthropic")

    # --- Bug 2: regex must capture full version like '4.6' not just '4' ---
    def test_dynamic_model_switch_and_provider_attribution(self):
        brain = self._make_brain("sess-claude")
        lines = [
            {"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT",
             "status": "DONE", "created_at": "2026-08-01T12:00:00Z",
             "content": "<USER_SETTINGS_CHANGE>\nThe user changed setting `Model Selection` from None to Claude Sonnet 4.6 (Thinking).\n</USER_SETTINGS_CHANGE>"},
            {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE",
             "status": "DONE", "created_at": "2026-08-01T12:00:05Z",
             "content": "Thinking about the task", "tool_calls": []},
            {"step_index": 2, "source": "USER_EXPLICIT", "type": "USER_INPUT",
             "status": "DONE", "created_at": "2026-08-01T12:05:00Z",
             "content": "<USER_SETTINGS_CHANGE>\nThe user changed setting `Model Selection` from Claude Sonnet 4.6 (Thinking) to Gemini 3.6 Flash (High).\n</USER_SETTINGS_CHANGE>"},
            {"step_index": 3, "source": "MODEL", "type": "PLANNER_RESPONSE",
             "status": "DONE", "created_at": "2026-08-01T12:05:05Z",
             "content": "Switching to Flash", "tool_calls": []},
        ]
        self._write_transcript(brain, lines)

        with patch.object(config, "GEMINI_BRAIN_DIRS", [brain]):
            events, _ = GeminiAntigravityCollector().poll({})

        self.assertEqual(len(events), 2)
        # Turn 1: must capture full '4.6', not just '4'
        self.assertEqual(events[0]["model_raw"], "claude-sonnet-4.6")
        self.assertEqual(events[0]["provider_id"], "anthropic")
        # Turn 2: Gemini 3.6 Flash
        self.assertEqual(events[1]["model_raw"], "gemini-3.6-flash")
        self.assertEqual(events[1]["provider_id"], "google")

    # --- Bug 3 (agent_name) + Bug 4 (global seen_sessions) ---
    def test_agent_name_cli_vs_ide_and_no_double_count(self):
        """CLI brain → gemini_cli, IDE brain → gemini_ide. Shared session ID counted once."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cli_brain = os.path.join(tmp, "antigravity-cli", "brain")
            ide_brain = os.path.join(tmp, "antigravity", "brain")
            shared_session = "shared-uuid-1234"
            for brain_dir, suffix in [(cli_brain, "antigravity-cli"), (ide_brain, "antigravity")]:
                log_dir = os.path.join(brain_dir, shared_session, ".system_generated", "logs")
                os.makedirs(log_dir, exist_ok=True)
                settings_file = os.path.join(tmp, suffix, "settings.json")
                with open(settings_file, "w") as f:
                    json.dump({"model": "Gemini 3.6 Flash"}, f)
                with open(os.path.join(log_dir, "transcript_full.jsonl"), "w") as f:
                    f.write(json.dumps({
                        "step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE",
                        "status": "DONE", "created_at": "2026-08-01T08:00:00Z",
                        "content": "hi", "tool_calls": [],
                    }) + "\n")

            with patch.object(config, "GEMINI_BRAIN_DIRS", [cli_brain, ide_brain]):
                events, _ = GeminiAntigravityCollector().poll({})

        # Same session UUID in both brain dirs → only ONE event emitted
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["agent_name"], "gemini_cli")  # CLI wins (first)

    def test_distinct_sessions_both_brain_dirs_counted(self):
        """Different session IDs in CLI and IDE are both counted."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cli_brain = os.path.join(tmp, "antigravity-cli", "brain")
            ide_brain = os.path.join(tmp, "antigravity", "brain")
            for brain_dir, suffix, sess, agent in [
                (cli_brain, "antigravity-cli", "cli-sess-001", "gemini_cli"),
                (ide_brain, "antigravity", "ide-sess-002", "gemini_ide"),
            ]:
                log_dir = os.path.join(brain_dir, sess, ".system_generated", "logs")
                os.makedirs(log_dir, exist_ok=True)
                with open(os.path.join(tmp, suffix, "settings.json"), "w") as f:
                    json.dump({"model": "Gemini 3.6 Flash"}, f)
                with open(os.path.join(log_dir, "transcript_full.jsonl"), "w") as f:
                    f.write(json.dumps({
                        "step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE",
                        "status": "DONE", "created_at": "2026-08-01T09:00:00Z",
                        "content": "hi", "tool_calls": [],
                    }) + "\n")

            with patch.object(config, "GEMINI_BRAIN_DIRS", [cli_brain, ide_brain]):
                events, _ = GeminiAntigravityCollector().poll({})

        self.assertEqual(len(events), 2)
        agent_names = {e["agent_name"] for e in events}
        self.assertIn("gemini_cli", agent_names)
        self.assertIn("gemini_ide", agent_names)

    # --- Bug 6: session restart resets accumulator ---
    def test_session_restart_resets_context_accumulator(self):
        brain = self._make_brain("sess-restart")
        lines = [
            {"step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE",
             "status": "DONE", "created_at": "2026-08-01T10:00:00Z",
             "content": "A" * 4000, "tool_calls": []},   # 1000 tokens
            {"step_index": 5, "source": "MODEL", "type": "PLANNER_RESPONSE",
             "status": "DONE", "created_at": "2026-08-01T10:05:00Z",
             "content": "B" * 4000, "tool_calls": []},   # accumulated: 2000+
            # step_index rolls back → session restart
            {"step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE",
             "status": "DONE", "created_at": "2026-08-01T11:00:00Z",
             "content": "C" * 400, "tool_calls": []},    # fresh session: only 100
        ]
        self._write_transcript(brain, lines)

        with patch.object(config, "GEMINI_BRAIN_DIRS", [brain]):
            events, _ = GeminiAntigravityCollector().poll({})

        self.assertEqual(len(events), 3)
        # Third event should have a much smaller input_tokens than second
        self.assertLess(events[2]["input_tokens"], events[1]["input_tokens"])


class TestAiderCollector(unittest.TestCase):
    def test_parses_model_stats(self):
        proj = os.path.join(config.TOKSTAT_DIR, "aider-project")
        os.makedirs(proj, exist_ok=True)
        with open(os.path.join(proj, ".aider.model.stats.json"), "w") as f:
            json.dump({"gpt-4o": {"cost": 0.0123, "tokens_in": 1000, "tokens_out": 500}}, f)

        old_cwd = os.getcwd()
        os.chdir(proj)
        try:
            events, _ = AiderCollector().poll({})
        finally:
            os.chdir(old_cwd)

        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["agent_name"], "aider")
        self.assertEqual(ev["status"], "ok")
        self.assertEqual(ev["model_raw"], "gpt-4o")
        self.assertEqual(ev["input_tokens"], 1000)
        self.assertEqual(ev["output_tokens"], 500)
        self.assertEqual(ev["total_tokens"], 1500)


class TestOptionalCollectors(unittest.TestCase):
    def test_copilot_missing_db_is_noop(self):
        with patch.object(config, "COPILOT_DB", "/nonexistent/copilot.db"):
            events, _ = CopilotCollector().poll({})
        self.assertEqual(events, [])

    def test_cursor_missing_db_is_noop(self):
        with patch.object(config, "CURSOR_STATE_DB", "/nonexistent/state.vscdb"):
            events, _ = VSCodeCursorCollector().poll({})
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
