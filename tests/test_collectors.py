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
        brain = os.path.join(config.TOKSTAT_DIR, "brain", "sess-uuid", ".system_generated", "logs")
        os.makedirs(brain, exist_ok=True)
        path = os.path.join(brain, "overview.txt")
        with open(path, "w") as f:
            for line in GEMINI_LINES:
                f.write(json.dumps(line) + "\n")
        return brain, path

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
            self.assertEqual(ev["model_raw"], "gemini-3.5-flash")
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
        brain, path = self._fixture()
        session = GeminiAntigravityCollector._extract_session(path)
        self.assertEqual(session, "sess-uuid")


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
