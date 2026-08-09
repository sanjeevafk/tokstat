import unittest
from datetime import datetime
from unittest.mock import patch

from tokstat import analytics, config, db_access, utils


class TestAnalyticsUnit(unittest.TestCase):

    def test_git_correlations_include_commits_without_telemetry(self):
        commit_time = int(datetime(2026, 7, 26, 12, 0, 0).timestamp())
        git_metadata = {
            "branch": "main",
            "commits": [{
                "hash": "abcdef123456",
                "timestamp": commit_time,
                "message": "commit without matching telemetry",
                "author": "Test Author",
            }],
        }

        with patch.object(utils, "find_git_repo_path", return_value="/tmp/project"), patch.object(
            utils, "get_git_metadata", return_value=git_metadata
        ):
            commits, branches, repos = analytics.compute_git_correlations({"project": []})

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["tokens"], 0)
        self.assertEqual(commits[0]["requests"], 0)
        self.assertFalse(commits[0]["has_telemetry"])
        self.assertEqual(branches, {"project": "main"})
        self.assertEqual(repos["project"]["commits_count"], 1)

    def test_analytics_normalizes_models_in_client_events(self):
        mock_event = {
            "event_id": "ev-1",
            "occurred_at": "2026-07-26T10:00:00Z",
            "workspace_id": "test-repo",
            "session_id": "sess-1",
            "turn_id": "1",
            "model_raw": "gpt_5_3_codex",
            "agent_name": "codex",
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_read_tokens": 500,
            "total_tokens": 1700,
            "requests": 1,
            "status": "ok",
        }

        with patch.object(db_access, "fetch_all_events", return_value=[mock_event]), patch.object(
            db_access, "query_copilot_db", return_value=(0, 0, 0, 0)
        ), patch.object(db_access, "fetch_balance_observations", return_value={}):
            report = analytics.compute_analytics()

        self.assertEqual(report["events"][0]["model"], "gpt-5.3-codex")
        self.assertEqual(report["models"][0]["model_name"], "gpt-5.3-codex")

    def test_cost_estimation(self):
        # Test default fallback model
        cost, savings = utils.estimate_token_cost_and_savings("unknown-model", 1000000, 1000000, 500000)
        self.assertGreater(cost, 0.0)
        self.assertGreater(savings, 0.0)

    def test_local_provider_is_zero_cost(self):
        cost, savings = utils.estimate_token_cost_and_savings(
            "llama3.1:8b", 1_000_000, 1_000_000, 500_000, provider_id="local"
        )
        self.assertEqual(cost, 0.0)
        self.assertEqual(savings, 0.0)

    def test_cloud_equivalent_cost_maps_local_models(self):
        cloud, cost = utils.estimate_cloud_equivalent_cost("llama3.1:70b", 1_000_000, 500_000)
        self.assertEqual(cloud, "gpt-4o")
        self.assertGreater(cost, 0.0)
        # 1M in @ $5 + 0.5M out @ $15 = $5 + $7.5 = $12.5
        self.assertAlmostEqual(cost, 12.5, places=4)

        cloud_none, cost_none = utils.estimate_cloud_equivalent_cost("some-unknown-model", 10, 10)
        self.assertIsNone(cloud_none)
        self.assertEqual(cost_none, 0.0)

    def test_codellama_not_matched_as_llama(self):
        # "codellama" must match the specific entry before the generic "llama"
        # fragment, otherwise it would be priced as gpt-4o instead of gpt-3.5.
        cloud, cost = utils.estimate_cloud_equivalent_cost("codellama:34b", 1_000_000, 1_000_000)
        self.assertEqual(cloud, "gpt-3.5")
        # 1M in @ $0.50 + 1M out @ $1.50 = $2.0
        self.assertAlmostEqual(cost, 2.0, places=4)
        # Plain llama still maps to gpt-4o
        cloud_llama, _ = utils.estimate_cloud_equivalent_cost("llama3.1:70b", 100, 100)
        self.assertEqual(cloud_llama, "gpt-4o")

    def test_pricing_overrides_beat_builtin_map(self):
        with patch.object(config, "pricing_overrides", return_value={"llama*": [0.0, 0.0]}):
            _cloud, cost = utils.estimate_cloud_equivalent_cost("llama3.1:8b", 1_000_000, 1_000_000)
        self.assertEqual(cost, 0.0)

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

    def test_local_inference_summary_in_global_overview(self):
        mock_events = [
            {
                "event_id": "ev-1", "occurred_at": "2026-07-26T10:00:00Z",
                "workspace_id": "test-repo", "session_id": "sess-1", "turn_id": "1",
                "model_raw": "llama3.1:8b", "agent_name": "ollama_proxy",
                "provider_id": "local",
                "input_tokens": 1000, "output_tokens": 500, "cache_read_tokens": 0,
                "total_tokens": 1500, "requests": 1, "status": "ok",
            },
            {
                "event_id": "ev-2", "occurred_at": "2026-07-26T10:05:00Z",
                "workspace_id": "test-repo", "session_id": "sess-1", "turn_id": "2",
                "model_raw": "qwen2.5-coder", "agent_name": "ollama_proxy",
                "provider_id": "local",
                "input_tokens": 2000, "output_tokens": 1000, "cache_read_tokens": 0,
                "total_tokens": 3000, "requests": 1, "status": "ok",
            },
            {
                "event_id": "ev-3", "occurred_at": "2026-07-26T10:10:00Z",
                "workspace_id": "test-repo", "session_id": "sess-1", "turn_id": "3",
                "model_raw": "gpt-4o", "agent_name": "claude_code",
                "provider_id": "anthropic",
                "input_tokens": 1000, "output_tokens": 200, "cache_read_tokens": 500,
                "total_tokens": 1700, "requests": 1, "status": "ok",
            },
        ]
        with patch.object(db_access, "fetch_all_events", return_value=mock_events), \
             patch.object(db_access, "query_copilot_db", return_value=(0, 0, 0, 0)), \
             patch.object(db_access, "fetch_balance_observations", return_value={}):
            report = analytics.compute_analytics()

        li = report["global_overview"]["local_inference"]
        self.assertEqual(li["total_tokens"], 4500)
        self.assertEqual(li["total_events"], 2)
        self.assertEqual(li["requests"], 2)
        self.assertGreater(li["cloud_cost_avoidance"], 0.0)
        self.assertIn("llama3.1:8b", li["models_used"])
        # Cloud events are excluded from local inference and keep their cost
        self.assertGreater(report["global_overview"]["estimated_cost"], 0.0)
        # Client events carry provider + cloud_avoidance for the dashboard filter
        local_client = [e for e in report["events"] if e["provider"] == "local"]
        self.assertEqual(len(local_client), 2)
        self.assertTrue(all(e["cloud_avoidance"] > 0.0 for e in local_client))
        self.assertEqual(
            [e for e in report["events"] if e["provider"] != "local"][0]["cloud_avoidance"],
            0.0,
        )

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
    def test_client_events_savings_match_estimated_savings(self):
        # The dashboard KPI/table savings must equal the exported estimate so the
        # two never silently diverge (regression for the cache-savings fix).
        mock_events = [
            {
                "event_id": "ev-1", "occurred_at": "2026-07-26T10:00:00Z",
                "workspace_id": "test-repo", "session_id": "sess-1", "turn_id": "1",
                "model_raw": "gpt-4o", "agent_name": "claude_code",
                "input_tokens": 1000, "output_tokens": 200, "cache_read_tokens": 500,
                "total_tokens": 1700, "requests": 1, "status": "ok",
            },
            {
                "event_id": "ev-2", "occurred_at": "2026-07-26T10:05:00Z",
                "workspace_id": "test-repo", "session_id": "sess-1", "turn_id": "2",
                "model_raw": "gpt-4o", "agent_name": "claude_code",
                "input_tokens": 2000, "output_tokens": 400, "cache_read_tokens": 1000,
                "total_tokens": 3400, "requests": 1, "status": "ok",
            },
        ]
        with patch.object(db_access, "fetch_all_events", return_value=mock_events), \
             patch.object(db_access, "query_copilot_db", return_value=(0, 0, 0, 0)), \
             patch.object(db_access, "fetch_balance_observations", return_value={}):
            report = analytics.compute_analytics()

        go = report["global_overview"]
        for ev in report["events"]:
            self.assertIn("savings", ev)
            self.assertAlmostEqual(
                ev["savings"],
                utils.estimate_token_cost_and_savings(
                    ev["model"], ev["input"], ev["output"], ev["cache_read"]
                )[1],
                places=9,
            )
        self.assertAlmostEqual(
            sum(ev["savings"] for ev in report["events"]), go["estimated_savings"], places=9
        )


if __name__ == "__main__":
    unittest.main()
