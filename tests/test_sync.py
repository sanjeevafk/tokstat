# test_sync.py
"""Tests for the opt-in provider usage poller (src/tokstat/sync.py)."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from tokstat import analytics, config, db_access, sync
from tokstat.collectors.base import now_iso

_MOCK_EVENT = {
    "event_id": "ev-1",
    "occurred_at": "2026-07-26T10:00:00Z",
    "workspace_id": "test-repo",
    "session_id": "sess-1",
    "turn_id": "1",
    "model_raw": "claude-sonnet-4-5",
    "agent_name": "claude_code",
    "provider_id": "anthropic",
    "input_tokens": 100,
    "output_tokens": 50,
    "cache_read_tokens": 0,
    "total_tokens": 150,
    "requests": 1,
    "status": "ok",
}


class TestNormalizers(unittest.TestCase):
    def test_anthropic_usage_maps_to_client_ide_vocabulary(self):
        usage = {
            "data": [
                {
                    "start_time": "2026-08-01T00:00:00Z",
                    "end_time": "2026-08-02T00:00:00Z",
                    "results": [
                        {
                            "model": "claude-sonnet-4-5",
                            "uncached_input_tokens": 1000,
                            "cached_input_tokens": 500,
                            "cache_creation_input_tokens": 50,
                            "output_tokens": 300,
                            "total_cost_usd": "0.25",
                        },
                        {
                            "model": "claude-haiku-4-5",
                            "uncached_input_tokens": 200,
                            "cached_input_tokens": 100,
                            "cache_creation_input_tokens": 10,
                            "output_tokens": 80,
                            "total_cost_usd": "0.02",
                        },
                    ],
                }
            ]
        }
        norm = sync._normalize_anthropic(usage, {})
        self.assertEqual(norm["totals"]["input"], 1800)
        self.assertEqual(norm["totals"]["cached"], 660)  # (500+50)+(100+10)
        self.assertEqual(norm["totals"]["output"], 380)
        self.assertEqual(norm["totals"]["cost"], 0.27)

        metrics = sync._metrics_from_normalized(
            norm, sync.KEY_INPUT, sync.KEY_OUTPUT, sync.KEY_CACHED, sync.KEY_COST_ANTHROPIC
        )
        self.assertEqual(metrics["client_ide_input_tokens"], 1800)
        self.assertEqual(metrics["client_ide_output_tokens"], 380)
        self.assertEqual(metrics["client_ide_cached_tokens"], 660)
        self.assertEqual(metrics["all_time_api_cost"], 0.27)
        self.assertEqual(metrics["model_claude_sonnet_4_5_input_tokens"], 1500)
        self.assertEqual(metrics["model_claude_sonnet_4_5_cost_usd"], 0.25)

    def test_openai_usage_maps_to_codex_vocabulary(self):
        usage = {
            "data": [
                {
                    "start_time": 1754000000,
                    "end_time": 1754086400,
                    "results": [
                        {
                            "model": "gpt-5.1-codex",
                            "input_tokens": 4000,
                            "output_tokens": 900,
                            "input_cached_tokens": 300,
                        },
                    ],
                }
            ]
        }
        cost = {
            "data": [
                {
                    "start_time": 1754000000,
                    "end_time": 1754086400,
                    "results": [{"amount": {"value": 1.25, "currency": "usd"}}],
                }
            ]
        }
        norm = sync._normalize_openai(usage, cost)
        self.assertEqual(norm["totals"]["input"], 4000)
        self.assertEqual(norm["totals"]["output"], 900)
        self.assertEqual(norm["totals"]["cached"], 300)
        self.assertEqual(norm["totals"]["cost"], 1.25)

        metrics = sync._metrics_from_normalized(
            norm, sync.KEY_CODEX_INPUT, sync.KEY_CODEX_OUTPUT, sync.KEY_CODEX_CACHED, sync.KEY_COST_OPENAI
        )
        self.assertEqual(metrics["provider_codex_input_tokens"], 4000)
        self.assertEqual(metrics["provider_codex_cached_tokens"], 300)
        self.assertEqual(metrics["total_cost_usd"], 1.25)
        self.assertEqual(metrics["model_gpt_5_1_codex_output_tokens"], 900)

    def test_zero_rows_are_dropped(self):
        norm = {"totals": {"input": 0.0, "output": 0.0, "cached": 0.0, "cost": 0.0}, "models": {}}
        metrics = sync._metrics_from_normalized(
            norm, sync.KEY_INPUT, sync.KEY_OUTPUT, sync.KEY_CACHED, sync.KEY_COST_ANTHROPIC
        )
        self.assertEqual(metrics, {})

    def test_sanitize_model(self):
        self.assertEqual(sync._sanitize_model("gpt-5.1-codex"), "gpt_5_1_codex")
        self.assertEqual(sync._sanitize_model("Claude Sonnet 4.5"), "claude_sonnet_4_5")


class TestCredentialDiscovery(unittest.TestCase):
    def test_anthropic_key_from_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
            self.assertEqual(sync._discover_anthropic_key(), "sk-test")

    def test_anthropic_key_from_claude_settings(self):
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"env": {"ANTHROPIC_API_KEY": "sk-settings"}}, tmp)
        tmp.close()
        self.addCleanup(os.remove, tmp.name)
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(os.path, "expanduser", return_value=tmp.name):
            self.assertEqual(sync._discover_anthropic_key(), "sk-settings")

    def test_anthropic_no_credentials_returns_none(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(os.path, "expanduser", return_value="/nonexistent/settings.json"):
            self.assertIsNone(sync._discover_anthropic_key())

    def test_openai_env_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai"}, clear=True):
            creds = sync._discover_openai_credentials()
        self.assertEqual(creds["type"], "api_key")
        self.assertEqual(creds["key"], "sk-openai")

    def test_openai_codex_auth_oauth(self):
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(
            {
                "tokens": {
                    "access_token": "at-123",
                    "refresh_token": "rt-456",
                    "expires_at": 9999999999,
                }
            },
            tmp,
        )
        tmp.close()
        self.addCleanup(os.remove, tmp.name)
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(os.path, "expanduser", return_value=tmp.name):
            creds = sync._discover_openai_credentials()
        self.assertEqual(creds["type"], "oauth")
        self.assertEqual(creds["access_token"], "at-123")
        self.assertEqual(creds["refresh_token"], "rt-456")

    def test_openai_codex_auth_api_key_entry(self):
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"OPENAI_API_KEY": {"key": "sk-codex-key"}}, tmp)
        tmp.close()
        self.addCleanup(os.remove, tmp.name)
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(os.path, "expanduser", return_value=tmp.name):
            creds = sync._discover_openai_credentials()
        self.assertEqual(creds["type"], "api_key")
        self.assertEqual(creds["key"], "sk-codex-key")


class TestHttpAndPagination(unittest.TestCase):
    def test_http_get_json_maps_403_to_auth_error(self):
        import urllib.error

        err = urllib.error.HTTPError("url", 403, "Forbidden", None, None)
        with patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(sync.ProviderAuthError):
                sync._http_get_json("https://x", {})

    def test_http_get_json_maps_500_to_provider_error(self):
        import urllib.error

        err = urllib.error.HTTPError("url", 500, "Server Error", None, None)
        with patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(sync.ProviderError):
                sync._http_get_json("https://x", {})

    def test_fetch_paginated_follows_next_page(self):
        pages = iter(
            [
                {"data": [{"bucket": 1}], "next_page": "abc"},
                {"data": [{"bucket": 2}], "next_page": None},
            ]
        )
        with patch.object(sync, "_http_get_json", side_effect=lambda *a, **k: next(pages)):
            payload = sync._fetch_paginated("https://x/usage", {})
        self.assertEqual(payload["data"], [{"bucket": 1}, {"bucket": 2}])


class TestOAuthRefresh(unittest.TestCase):
    def test_openai_refresh_retries_once(self):
        creds = {
            "type": "oauth",
            "access_token": "expired",
            "refresh_token": "rt-456",
            "expires_at": None,
        }
        calls = {"n": 0}

        def fake_fetch(c, lookback):
            calls["n"] += 1
            if calls["n"] == 1:
                raise sync.ProviderAuthError("HTTP 401")
            return {"totals": {"input": 1.0, "output": 1.0, "cached": 0.0, "cost": 0.0}, "models": {}}

        with patch.object(sync, "_fetch_openai", side_effect=fake_fetch), \
             patch.object(sync, "_oauth_refresh", return_value="fresh") as refresh:
            norm = sync._fetch_openai_with_refresh(creds, 30)
        refresh.assert_called_once_with("rt-456")
        self.assertEqual(calls["n"], 2)
        self.assertEqual(norm["totals"]["input"], 1.0)

    def test_openai_without_refresh_token_does_not_refresh(self):
        creds = {"type": "oauth", "access_token": "x", "refresh_token": None, "expires_at": None}
        with patch.object(sync, "_oauth_refresh") as refresh:
            with self.assertRaises(sync.ProviderAuthError):
                sync._fetch_openai_with_refresh(creds, 30)
        refresh.assert_not_called()

    def test_oauth_refresh_parses_access_token(self):
        with patch(
            "urllib.request.urlopen"
        ) as urlopen:
            resp = urlopen.return_value.__enter__.return_value
            resp.read.return_value = json.dumps({"access_token": "fresh-token"}).encode()
            self.assertEqual(sync._oauth_refresh("rt"), "fresh-token")


class TestSyncWriteAndReconcile(unittest.TestCase):
    def setUp(self):
        # Isolate from anything other tests left in the shared session DB.
        conn = config.connect_db()
        try:
            conn.execute("DELETE FROM balance_observations")
            conn.execute("DELETE FROM collector_state")
            conn.execute("DELETE FROM usage_events")
            conn.commit()
        finally:
            conn.close()

    def test_write_observations_then_reader_is_idempotent(self):
        conn = config.connect_db()
        try:
            n1 = sync._write_observations(
                conn, "anthropic", "default",
                {"client_ide_input_tokens": 5000, "all_time_api_cost": 1.5},
            )
            n2 = sync._write_observations(
                conn, "anthropic", "default",
                {"client_ide_input_tokens": 5000, "all_time_api_cost": 1.5},
            )
        finally:
            conn.close()
        self.assertEqual(n1, 2)
        self.assertEqual(n2, 2)
        # The flat reader returns the latest value per key - never doubled.
        obs = db_access.fetch_balance_observations()
        self.assertEqual(obs["client_ide_input_tokens"], 5000)
        self.assertEqual(obs["all_time_api_cost"], 1.5)

    def test_sync_writes_observations_and_reconciles_into_analytics(self):
        with patch.object(sync, "_discover_anthropic_key", return_value="sk-test"), \
             patch.object(sync, "_discover_openai_credentials", return_value=None), \
             patch.object(sync, "_fetch_anthropic", return_value={
                 "totals": {"input": 9000.0, "output": 3000.0, "cached": 1000.0, "cost": 4.0},
                 "models": {},
             }):
            result = sync.run_sync_once()
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["providers"]["anthropic"]["status"], "ok")
        self.assertEqual(result["providers"]["openai"]["status"], "skipped")
        self.assertEqual(result["providers"]["google"]["status"], "skipped")

        # Local event log has fewer tokens than the provider reports.
        conn = config.connect_db()
        try:
            conn.execute(
                """
                INSERT INTO usage_events (
                    event_id, occurred_at, provider_id, agent_name, workspace_id,
                    session_id, event_type, model_raw, input_tokens, output_tokens,
                    total_tokens, requests, status, dedup_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ev-sync-1", now_iso(), "anthropic", "claude_code", "test-repo",
                    "sess-1", "message_usage", "claude-sonnet-4-5",
                    1000, 500, 1500, 1, "ok", "ev-sync-1",
                ),
            )
            conn.commit()
        finally:
            conn.close()

        with patch.object(db_access, "query_copilot_db", return_value=(0, 0, 0, 0)):
            go = analytics.compute_analytics()["global_overview"]
        self.assertEqual(go["provider_reported_input"], 9000)
        self.assertEqual(go["provider_reported_tokens"], 13000)
        self.assertEqual(go["local_event_tokens"], 1500)
        self.assertEqual(go["coverage_gap_tokens"], 11500)

    def test_analytics_sums_provider_categories(self):
        # Anthropic (client_ide_*) + OpenAI (provider_codex_*) are additive.
        with patch.object(db_access, "fetch_balance_observations", return_value={
            "client_ide_input_tokens": 5000,
            "client_ide_output_tokens": 2000,
            "provider_codex_input_tokens": 3000,
            "provider_codex_output_tokens": 1000,
            "all_time_api_cost": 2.5,
            "total_cost_usd": 1.5,
        }), patch.object(db_access, "fetch_all_events", return_value=[_MOCK_EVENT]), \
             patch.object(db_access, "query_copilot_db", return_value=(0, 0, 0, 0)):
            go = analytics.compute_analytics()["global_overview"]
        self.assertEqual(go["provider_reported_input"], 8000)
        self.assertEqual(go["provider_reported_output"], 3000)
        self.assertEqual(go["provider_reported_tokens"], 11000)
        self.assertEqual(go["estimated_cost"], 4.0)

    def test_single_provider_legacy_semantics_preserved(self):
        # A lone client_ide_* observation behaves exactly as before the sum change.
        with patch.object(db_access, "fetch_balance_observations", return_value={
            "client_ide_input_tokens": 5000,
            "client_ide_output_tokens": 2000,
            "client_ide_cached_tokens": 100,
        }), patch.object(db_access, "fetch_all_events", return_value=[_MOCK_EVENT]), \
             patch.object(db_access, "query_copilot_db", return_value=(0, 0, 0, 0)):
            go = analytics.compute_analytics()["global_overview"]
        self.assertEqual(go["provider_reported_input"], 5000)
        self.assertEqual(go["provider_reported_output"], 2000)
        self.assertEqual(go["provider_reported_tokens"], 7100)

    def test_provider_error_isolation(self):
        # A failing provider is reported without aborting the other providers;
        # the only attempted provider failed, so the exit code is non-zero.
        with patch.object(sync, "_discover_anthropic_key", return_value="sk-test"), \
             patch.object(sync, "_fetch_anthropic", side_effect=sync.ProviderError("boom")), \
             patch.object(sync, "_discover_openai_credentials", return_value=None):
            result = sync.run_sync_once()
        self.assertEqual(result["providers"]["anthropic"]["status"], "error")
        self.assertEqual(result["providers"]["openai"]["status"], "skipped")
        self.assertEqual(result["exit_code"], 1)

    def test_all_providers_fail_exits_nonzero(self):
        with patch.object(sync, "_discover_anthropic_key", return_value="sk-test"), \
             patch.object(sync, "_fetch_anthropic", side_effect=sync.ProviderError("boom")), \
             patch.object(sync, "_discover_openai_credentials",
                          return_value={"type": "api_key", "key": "k"}), \
             patch.object(sync, "_fetch_openai_with_refresh",
                          side_effect=sync.ProviderError("nope")):
            result = sync.run_sync_once()
        self.assertEqual(result["providers"]["openai"]["status"], "error")
        self.assertEqual(result["exit_code"], 1)

    def test_maybe_sync_respects_interval(self):
        conn = config.connect_db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO collector_state (collector_id, bookmark, updated_at) "
                "VALUES (?, ?, ?)",
                (sync._SYNC_STATE_ID, json.dumps({"last_sync_at": now_iso()}), now_iso()),
            )
            conn.commit()
        finally:
            conn.close()
        with patch.object(sync, "run_sync_once", return_value={"exit_code": 0}):
            self.assertIsNone(sync.maybe_sync())  # not due yet
            res = sync.maybe_sync(force=True)     # forced runs anyway
        self.assertEqual(res["exit_code"], 0)

    def test_maybe_sync_runs_when_due(self):
        with patch.object(sync, "run_sync_once", return_value={"exit_code": 0}):
            res = sync.maybe_sync()  # no state row -> due immediately
        self.assertEqual(res["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
