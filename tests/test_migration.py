# test_migration.py
import os
import sqlite3
import unittest
from unittest.mock import patch

from tokstat import config, migration
from tokstat.collectors.legacy_sync import LegacySyncCollector


def _unique_db(prefix):
    import uuid
    return os.path.join(config.TOKSTAT_DIR, f"{prefix}-{uuid.uuid4().hex[:8]}.db")


def make_openusage_db(n=4, day="2026-08-01T10:00:0"):
    path = _unique_db("ou")
    conn = sqlite3.connect(path)
    try:
        for stmt in migration.SCHEMA_STATEMENTS:
            conn.execute(stmt)
        for i in range(n):
            conn.execute(
                "INSERT INTO usage_events (event_id, occurred_at, agent_name, "
                "event_type, model_raw, input_tokens, output_tokens, cache_read_tokens, "
                "total_tokens, cost_usd, requests, status, dedup_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"ou-{i}", f"{day}{i%10}Z", "codex", "message_usage", "gpt-5.3-codex",
                    1000 + i, 200 + i, 500, 1700 + 2 * i, 0.01, 1, "ok", f"ou-{i}",
                ),
            )
        conn.execute(
            "INSERT INTO balance_observations (provider_id, account_id, metric_key, "
            "observed_at, used, unit, semantics) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("anthropic", "local", "client_ide_total_tokens", "2026-08-01T10:00:00Z",
             5000000, "tokens", "cumulative"),
        )
        conn.commit()
    finally:
        conn.close()
    return path


def make_tokentop_db(n=3):
    path = _unique_db("tt")
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE usage_events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, "
            "source TEXT, provider TEXT, model TEXT, agent_id TEXT, session_id TEXT, "
            "project_path TEXT, input_tokens INTEGER, output_tokens INTEGER, "
            "cache_read_tokens INTEGER, cache_write_tokens INTEGER, cost_usd REAL, "
            "request_count INTEGER, pricing_source TEXT, created_at INTEGER)"
        )
        for i in range(n):
            conn.execute(
                "INSERT INTO usage_events (timestamp, source, provider, model, agent_id, "
                "session_id, project_path, input_tokens, output_tokens, cache_read_tokens, "
                "cache_write_tokens, cost_usd, request_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (1780000000 + i, "cli", "openai", "gpt-4o", "codex", f"s{i}",
                 "/home/user/alpha", 100, 50, 0, 0, 0.001, 1),
            )
        conn.commit()
    finally:
        conn.close()
    return path


class TestMigration(unittest.TestCase):
    def setUp(self):
        # Fresh native DB per test so tests never share state.
        import uuid
        self.db_path = os.path.join(config.TOKSTAT_DIR, f"mig-{uuid.uuid4().hex[:8]}.db")
        self.conn = config.connect_db(path=self.db_path)

    def tearDown(self):
        self.conn.close()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except OSError:
                pass

    def test_migrate_openusage_counts_and_rows(self):
        src = make_openusage_db(n=4)
        count = migration.migrate_openusage(src, self.conn)
        # 4 usage_events + 1 balance_observation (+ 0 raw events)
        self.assertEqual(count, 5)
        rows = self.conn.execute("SELECT count(*) FROM usage_events").fetchone()[0]
        self.assertEqual(rows, 4)
        bal = self.conn.execute("SELECT count(*) FROM balance_observations").fetchone()[0]
        self.assertEqual(bal, 1)
        os.remove(src)

    def test_migrate_is_idempotent(self):
        src = make_openusage_db(n=4)
        migration.migrate_openusage(src, self.conn)
        # second auto run: recorded migration -> no-op
        second = migration.migrate_openusage(src, self.conn)
        self.assertEqual(second, 0)
        # forced run: still no duplicates (INSERT OR IGNORE)
        forced = migration.migrate_openusage(src, self.conn, force=True)
        self.assertEqual(forced, 5)  # re-attempted rows (all ignored)
        rows = self.conn.execute("SELECT count(*) FROM usage_events").fetchone()[0]
        self.assertEqual(rows, 4)
        os.remove(src)

    def test_migration_record_persists_across_connections(self):
        """Regression: the _migrations record must be committed so a fresh CLI
        invocation (new connection) does not re-import everything."""
        src = make_openusage_db(n=2)
        conn1 = config.connect_db(path=self.db_path)
        migration.migrate_openusage(src, conn1)
        conn1.close()

        conn2 = config.connect_db(path=self.db_path)
        try:
            second = migration.migrate_openusage(src, conn2)
            self.assertEqual(second, 0)  # recorded -> skipped
            rows = conn2.execute("SELECT count(*) FROM usage_events").fetchone()[0]
            self.assertEqual(rows, 2)
        finally:
            conn2.close()
        os.remove(src)

    def test_migration_does_not_modify_source(self):
        src = make_openusage_db(n=4)
        before_stat = os.stat(src)
        migration.migrate_openusage(src, self.conn)
        after_stat = os.stat(src)
        self.assertEqual(before_stat.st_mtime_ns, after_stat.st_mtime_ns)
        self.assertEqual(before_stat.st_size, after_stat.st_size)
        os.remove(src)

    def test_tokentop_deduped_against_openusage_fingerprint(self):
        ou_src = make_openusage_db(n=1, day="2026-08-01T10:00:0")
        migration.migrate_openusage(ou_src, self.conn)

        tt_src = make_tokentop_db(n=3)
        inserted = migration.migrate_tokentop(tt_src, self.conn)
        self.assertEqual(inserted, 3)
        # total = 1 openusage + 3 tokentop
        rows = self.conn.execute("SELECT count(*) FROM usage_events").fetchone()[0]
        self.assertEqual(rows, 4)
        os.remove(ou_src)
        os.remove(tt_src)

    def test_check_and_run_migrations_auto_skips_when_sync_disabled(self):
        with patch.object(config, "LEGACY_OPENUSAGE_DB", "/nonexistent/a.db"), patch.object(
            config, "LEGACY_TOKENTOP_DB", "/nonexistent/b.db"
        ):
            result = migration.check_and_run_migrations()  # auto path
        self.assertEqual(result["migrated"], False)

    def test_check_and_run_migrations_explicit_imports(self):
        ou_src = make_openusage_db(n=3)
        with patch.object(config, "LEGACY_OPENUSAGE_DB", ou_src), patch.object(
            config, "LEGACY_TOKENTOP_DB", "/nonexistent/b.db"
        ):
            result = migration.check_and_run_migrations(explicit=True)
        self.assertEqual(result["migrated"], True)
        self.assertEqual(result["openusage_imported"], 4)  # 3 events + 1 balance row
        os.remove(ou_src)

    def test_legacy_sync_delta_and_balance_copy(self):
        ou_src = make_openusage_db(n=2)
        tt_src = make_tokentop_db(n=2)

        # run a first sync (patches only for this collector test)
        with patch.object(config, "SYNC_LEGACY", True), patch.object(
            config, "LEGACY_OPENUSAGE_DB", ou_src
        ), patch.object(config, "LEGACY_TOKENTOP_DB", tt_src):
            res = LegacySyncCollector().run_once(self.conn)

        self.assertGreaterEqual(res["events"], 2)  # openusage delta
        self.assertGreaterEqual(res["balance_observations_copied"], 1)
        bal = self.conn.execute(
            "SELECT used FROM balance_observations WHERE metric_key = 'client_ide_total_tokens'"
        ).fetchone()
        self.assertEqual(bal["used"], 5000000)

        # second run: >= boundary may re-read the final event, but nothing new
        # is INSERTED (event_id PK / dedup protects idempotency)
        with patch.object(config, "SYNC_LEGACY", True), patch.object(
            config, "LEGACY_OPENUSAGE_DB", ou_src
        ), patch.object(config, "LEGACY_TOKENTOP_DB", tt_src):
            res2 = LegacySyncCollector().run_once(self.conn)
        self.assertEqual(res2["inserted"], 0)
        rows = self.conn.execute("SELECT count(*) FROM usage_events").fetchone()[0]
        self.assertEqual(rows, 4)  # 2 openusage + 2 tokentop, no growth on 2nd run
        os.remove(ou_src)
        os.remove(tt_src)


if __name__ == "__main__":
    unittest.main()
