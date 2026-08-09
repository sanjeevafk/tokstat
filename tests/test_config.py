# test_config.py
import os
import tempfile
import unittest
from unittest.mock import patch

from tokstat import config


class TestConfigFile(unittest.TestCase):
    def _with_config(self, toml_text):
        """Point TOKSTAT_CONFIG at a temp file with the given contents."""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False, encoding="utf-8"
        )
        try:
            tmp.write(toml_text)
        finally:
            tmp.close()
        patcher = patch.object(config, "CONFIG_FILE", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))

    def test_load_config_missing_file_returns_empty(self):
        with patch.object(config, "CONFIG_FILE", "/nonexistent/config.toml"):
            self.assertEqual(config.load_config(), {})

    def test_proxy_settings_defaults_when_no_file(self):
        with patch.object(config, "CONFIG_FILE", "/nonexistent/config.toml"):
            s = config.proxy_settings()
        self.assertEqual(s["upstream"], "http://localhost:11434")
        self.assertEqual(s["listen_port"], 11435)
        self.assertEqual(s["agent_name"], "ollama_proxy")
        self.assertEqual(s["provider_id"], "local")
        self.assertFalse(s["enabled"])

    def test_proxy_settings_from_toml_mini_parser(self):
        self._with_config(
            """
# TokStat config
[proxy]
enabled = true
upstream = "http://127.0.0.1:8080"
listen_port = 11999
agent_name = "llamacpp_proxy"
provider_id = "local"

[proxy.gpu_cost]
enabled = false
usd_per_hour = 0.35

[pricing.overrides]
"llama*" = [0.0, 0.0]
"qwen*" = [0.1, 0.4]
"""
        )
        s = config.proxy_settings()
        self.assertTrue(s["enabled"])
        self.assertEqual(s["upstream"], "http://127.0.0.1:8080")
        self.assertEqual(s["listen_port"], 11999)
        self.assertEqual(s["agent_name"], "llamacpp_proxy")

        self.assertEqual(config.gpu_cost_settings()["usd_per_hour"], 0.35)
        overrides = config.pricing_overrides()
        self.assertEqual(overrides["llama*"], [0.0, 0.0])
        self.assertEqual(overrides["qwen*"], [0.1, 0.4])

    def test_env_overrides_beat_config_file(self):
        self._with_config(
            """
[proxy]
upstream = "http://localhost:11434"
listen_port = 11435
"""
        )
        with patch.dict(
            os.environ,
            {
                "TOKSTAT_PROXY_UPSTREAM": "http://127.0.0.1:9999",
                "TOKSTAT_PROXY_PORT": "12222",
            },
        ):
            s = config.proxy_settings()
        self.assertEqual(s["upstream"], "http://127.0.0.1:9999")
        self.assertEqual(s["listen_port"], 12222)

    def test_invalid_toml_falls_back_to_defaults(self):
        self._with_config("this is not [ valid toml at all = = =")  # noqa: E501
        self.assertEqual(config.proxy_settings()["upstream"], "http://localhost:11434")


class TestConfig(unittest.TestCase):
    def test_paths_under_tokstat_dir(self):
        self.assertEqual(config.DB_PATH, os.path.join(config.TOKSTAT_DIR, "telemetry.db"))
        self.assertEqual(config.DAEMON_PID_PATH, os.path.join(config.TOKSTAT_DIR, "daemon.pid"))

    def test_sync_legacy_defaults_disabled_in_tests(self):
        # conftest forces TOKSTAT_SYNC_LEGACY=0 so tests never touch real DBs
        self.assertFalse(config.SYNC_LEGACY)

    def test_connect_db_creates_schema_with_wal(self):
        conn = config.connect_db()
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertIn("usage_events", tables)
            self.assertIn("usage_raw_events", tables)
            self.assertIn("balance_observations", tables)
            self.assertIn("collector_state", tables)
            self.assertIn("_migrations", tables)
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode, "wal")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
