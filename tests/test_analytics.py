import unittest
from unittest.mock import patch

from tokstat import analytics, db_access, utils


class TestAnalyticsUnit(unittest.TestCase):

    def test_cost_estimation(self):
        # Test default fallback model
        cost, savings = utils.estimate_token_cost_and_savings("unknown-model", 1000000, 1000000, 500000)
        self.assertGreater(cost, 0.0)
        self.assertGreater(savings, 0.0)

        # Test specific models
        cost_flash, _ = utils.estimate_token_cost_and_savings("gemini-3.5-flash", 1000000, 1000000, 0)
        cost_opus, _ = utils.estimate_token_cost_and_savings("claude-3-opus", 1000000, 1000000, 0)
        self.assertLess(cost_flash, cost_opus)

        # Test None safety
        cost_none, savings_none = utils.estimate_token_cost_and_savings(None, None, None, None)
        self.assertEqual(cost_none, 0.0)
        self.assertEqual(savings_none, 0.0)

    def test_uninterrupted_sessions(self):
        events = [
            {"occurred_at": "2026-07-26 10:00:00"},
            {"occurred_at": "2026-07-26 10:15:00"},
            {"occurred_at": "2026-07-26 10:30:00"},
            {"occurred_at": "2026-07-26 12:00:00"}, # 90 min gap > 30 min threshold
        ]
        duration_sec = analytics.compute_uninterrupted_sessions(events, gap_minutes=30)
        # First session: 10:00 to 10:30 = 30 mins = 1800 sec
        self.assertEqual(duration_sec, 1800)

    def test_empty_database_fallback(self):
        with patch.object(db_access, "fetch_all_events", return_value=[]):
            data = analytics.compute_analytics()
            self.assertEqual(data, {})

    def test_analytics_computation_with_mock_events(self):
        mock_events = [
            {
                "event_id": "ev-1",
                "occurred_at": "2026-07-26T10:00:00Z",
                "workspace_id": "test-repo",
                "session_id": "sess-1",
                "turn_id": "1",
                "model_raw": "gpt-4o",
                "agent_name": "claude_code",
                "input_tokens": 1000,
                "output_tokens": 200,
                "cache_read_tokens": 500,
                "total_tokens": 1700,
                "requests": 1,
                "status": "ok",
            },
            {
                "event_id": "ev-2",
                "occurred_at": "2026-07-26T10:05:00Z",
                "workspace_id": "test-repo",
                "session_id": "sess-1",
                "turn_id": "2",
                "model_raw": "gpt-4o",
                "agent_name": "claude_code",
                "input_tokens": 2000,
                "output_tokens": 400,
                "cache_read_tokens": 1000,
                "total_tokens": 3400,
                "requests": 1,
                "status": "ok",
            },
        ]
        with patch.object(db_access, "fetch_all_events", return_value=mock_events), \
             patch.object(db_access, "query_copilot_db", return_value=(0, 0, 0, 0)), \
             patch.object(db_access, "fetch_balance_observations", return_value={}):
            
            report = analytics.compute_analytics()
            go = report.get("global_overview", {})
            self.assertEqual(go.get("total_tokens"), 5100)
            self.assertEqual(go.get("total_input"), 3000)
            self.assertEqual(go.get("total_output"), 600)
            self.assertEqual(go.get("cached_tokens"), 1500)
            self.assertEqual(len(report.get("repositories", [])), 1)
            self.assertEqual(len(report.get("sessions", [])), 1)


if __name__ == "__main__":
    unittest.main()
