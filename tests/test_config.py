# test_config.py
import os
import unittest

from tokstat import config


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
