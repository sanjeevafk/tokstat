# test_server.py
import json
import os
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from tokstat import config
from tokstat.server import IngestionServer


class TestIngestionServer(unittest.TestCase):
    def setUp(self):
        import uuid
        # Isolate this test's writes to a fresh native DB (other tests may have
        # populated the default one via migration/analytics paths).
        self.db_path = os.path.join(config.TOKSTAT_DIR, f"srv-{uuid.uuid4().hex[:8]}.db")
        patcher = patch.object(config, "DB_PATH", self.db_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.server = IngestionServer(host="127.0.0.1", port=0)  # ephemeral port
        self.server.start()
        self.base = f"http://127.0.0.1:{self.server.port}"

    def tearDown(self):
        self.server.stop()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except OSError:
                pass

    def _post(self, path, payload):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def _get(self, path):
        with urllib.request.urlopen(self.base + path) as resp:
            return resp.status, json.loads(resp.read())

    def test_batch_ingestion_writes_rows_with_total_default(self):
        status, body = self._post("/v1/events", [
            {"agent_name": "test-cli", "event_type": "message_usage",
             "occurred_at": "2026-08-06T12:00:00Z", "model_raw": "gpt-4o-mini",
             "input_tokens": 10, "output_tokens": 5},
            {"agent_name": "test-cli", "event_type": "message_usage",
             "occurred_at": "2026-08-06T12:00:01Z", "model_raw": "gpt-4o-mini",
             "input_tokens": 20, "output_tokens": 10},
        ])
        self.assertEqual(status, 202)
        self.assertEqual(body["accepted"], 2)
        self.server.flush()
        conn = config.connect_db()
        try:
            n = conn.execute("SELECT count(*) FROM usage_events").fetchone()[0]
            self.assertEqual(n, 2)
            total = conn.execute(
                "SELECT total_tokens FROM usage_events WHERE occurred_at LIKE '2026-08-06T12:00:00Z%'"
            ).fetchone()[0]
            self.assertEqual(total, 15)  # 10 + 5 + 0 cache
        finally:
            conn.close()

    def test_single_event_via_telemetry_alias_and_cache_sum(self):
        status, body = self._post("/v1/telemetry", {
            "agent_name": "hook", "event_type": "message_usage",
            "occurred_at": "2026-08-06T12:00:02Z", "input_tokens": 3,
            "cache_read_tokens": 2,
        })
        self.assertEqual(status, 202)
        self.assertEqual(body["accepted"], 1)
        self.server.flush()
        conn = config.connect_db()
        try:
            row = conn.execute(
                "SELECT total_tokens, agent_name, status FROM usage_events "
                "WHERE occurred_at LIKE '2026-08-06T12:00:02Z%'"
            ).fetchone()
            self.assertEqual(row["total_tokens"], 5)  # 3 + 0 + 2
            self.assertEqual(row["agent_name"], "hook")
            self.assertEqual(row["status"], "ok")
        finally:
            conn.close()

    def test_missing_required_fields_rejected(self):
        status, body = self._post("/v1/events", {"agent_name": ""})
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_malformed_optional_fields_do_not_crash(self):
        # Regression: non-numeric cost_usd / weird status must not crash the
        # request handler - it should normalize safely and accept.
        status, body = self._post("/v1/events", {
            "agent_name": "x", "event_type": "message_usage",
            "occurred_at": "2026-08-06T12:00:30Z", "cost_usd": "abc",
            "status": {"nested": True}, "input_tokens": "not-a-number",
        })
        self.assertEqual(status, 202)
        self.assertEqual(body["accepted"], 1)
        self.server.flush()
        conn = config.connect_db()
        try:
            row = conn.execute(
                "SELECT cost_usd, status, input_tokens FROM usage_events "
                "WHERE occurred_at LIKE '2026-08-06T12:00:30Z%'"
            ).fetchone()
            self.assertEqual(row["cost_usd"], 0.0)
            self.assertEqual(row["input_tokens"], 0)
            self.assertEqual(row["status"], "{'nested': True}")
        finally:
            conn.close()

    def test_invalid_json_rejected(self):
        req = urllib.request.Request(
            self.base + "/v1/events", data=b"{not json",
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_dedup_key_prevents_duplicates(self):
        payload = {"agent_name": "x", "event_type": "message_usage",
                   "occurred_at": "2026-08-06T12:00:10Z", "dedup_key": "fixed-1"}
        self._post("/v1/events", payload)
        self._post("/v1/events", payload)
        self.server.flush()
        conn = config.connect_db()
        try:
            n = conn.execute(
                "SELECT count(*) FROM usage_events WHERE dedup_key = 'fixed-1'"
            ).fetchone()[0]
            self.assertEqual(n, 1)
        finally:
            conn.close()

    def test_health_endpoint(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertIn("events_total", body)
        self.assertIn("collectors", body)

    def test_writer_thread_flushes_periodically_without_explicit_flush(self):
        # Regression: the batching writer must persist events on its 1s tick,
        # not only at shutdown or at 50-event batch size.
        self._post("/v1/events", {
            "agent_name": "auto-flush", "event_type": "message_usage",
            "occurred_at": "2026-08-06T12:00:20Z", "input_tokens": 1,
        })
        conn = config.connect_db()
        try:
            deadline = time.time() + 5
            while time.time() < deadline:
                n = conn.execute("SELECT count(*) FROM usage_events").fetchone()[0]
                if n >= 1:
                    break
                time.sleep(0.2)
            n = conn.execute("SELECT count(*) FROM usage_events").fetchone()[0]
        finally:
            conn.close()
        self.assertGreaterEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
