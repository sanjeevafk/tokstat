# test_proxy.py
import json
import queue
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from tokstat import config, daemon
from tokstat.collectors.base import EVENT_COLUMNS
from tokstat.proxy import ProxyServer, proxy_daemon_status


class MockUpstreamHandler(BaseHTTPRequestHandler):
    """Tiny upstream that answers based on the requested model name."""

    def log_message(self, format, *args):
        return

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_POST(self):
        body = self._body()
        model = str(body.get("model") or "")
        if model == "test-ollama":
            payload = {
                "model": model, "done": True,
                "prompt_eval_count": 110, "eval_count": 55,
            }
            self._json(payload)
        elif model == "test-stream":
            self._stream(usage=True)
        elif model == "test-stream-nousage":
            self._stream(usage=False)
        elif model == "test-err":
            self._json({"error": "boom"}, status=500)
        else:  # OpenAI-compat with usage
            payload = {
                "id": "cmpl-1", "model": model, "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}],
                "usage": {"prompt_tokens": 110, "completion_tokens": 55, "total_tokens": 165},
            }
            self._json(payload)

    def do_GET(self):
        if self.path == "/v1/models":
            self._json({"object": "list", "data": [{"id": "llama3.1:8b"}]})
        else:
            self._json({"error": "not found"}, status=404)

    def _json(self, payload, status=200):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _stream(self, usage):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        chunks = [
            'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n',
            'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n',
            'data: {"choices":[{"delta":{"content":"world"}}]}\n\n',
        ]
        if usage:
            chunks.append(
                'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
                '"usage":{"prompt_tokens":111,"completion_tokens":10,"total_tokens":121}}\n\n'
            )
        else:
            chunks.append('data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n')
        chunks.append("data: [DONE]\n\n")
        for c in chunks:
            self.wfile.write(c.encode("utf-8"))
            self.wfile.flush()
            time.sleep(0.005)


class TestProxy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), MockUpstreamHandler)
        cls.upstream_thread = threading.Thread(
            target=cls.upstream.serve_forever, daemon=True
        )
        cls.upstream_thread.start()
        cls.upstream_url = f"http://127.0.0.1:{cls.upstream.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.upstream.shutdown()
        cls.upstream.server_close()

    def setUp(self):
        self.events = queue.Queue()
        self.proxy = ProxyServer(
            upstream=self.upstream_url,
            listen_port=0,
            agent_name="ollama_proxy",
            ingest_queue=self.events,
        )
        self.proxy.start()
        self.addCleanup(self.proxy.stop)
        self.base = f"http://127.0.0.1:{self.proxy.port}"

    def _post(self, path, payload, expect_status=200):
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", self.proxy.port, timeout=10)
        try:
            conn.request(
                "POST", path,
                body=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            raw = resp.read()
            return resp.status, resp.getheader("Content-Type"), raw
        finally:
            conn.close()

    def _get(self, path):
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", self.proxy.port, timeout=10)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def _drain(self):
        events = []
        while True:
            try:
                events.append(self.events.get_nowait())
            except queue.Empty:
                return events

    def test_openai_compat_non_streaming_real_usage(self):
        status, ctype, raw = self._post("/v1/chat/completions", {
            "model": "llama3.1:8b", "messages": [{"role": "user", "content": "hello"}]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "application/json")
        body = json.loads(raw)
        self.assertEqual(body["usage"]["prompt_tokens"], 110)  # verbatim passthrough

        events = self._drain()
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["input_tokens"], 110)
        self.assertEqual(ev["output_tokens"], 55)
        self.assertEqual(ev["provider_id"], "local")
        self.assertEqual(ev["agent_name"], "ollama_proxy")
        self.assertEqual(ev["model_raw"], "llama3.1:8b")
        self.assertEqual(ev["status"], "ok")
        self.assertEqual(ev["cost_usd"], 0.0)
        # Event shape matches the schema columns exactly
        self.assertEqual(set(ev.keys()), set(EVENT_COLUMNS))
        self.assertTrue(ev["dedup_key"].startswith("proxy-"))

    def test_ollama_native_counts_mapped(self):
        status, _ctype, _raw = self._post("/api/chat", {
            "model": "test-ollama", "messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertEqual(status, 200)
        events = self._drain()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["input_tokens"], 110)
        self.assertEqual(events[0]["output_tokens"], 55)

    def test_streaming_usage_from_final_chunk(self):
        status, ctype, raw = self._post("/v1/chat/completions", {
            "model": "test-stream", "stream": True,
            "messages": [{"role": "user", "content": "hello"}]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "text/event-stream")
        self.assertIn(b"data: [DONE]", raw)  # client received the full stream
        self.assertIn(b"Hello", raw)

        events = self._drain()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["input_tokens"], 111)
        self.assertEqual(events[0]["output_tokens"], 10)

    def test_streaming_without_usage_falls_back_to_estimates(self):
        status, _ctype, _raw = self._post("/v1/chat/completions", {
            "model": "test-stream-nousage", "stream": True,
            "messages": [{"role": "user", "content": "hi there"}]},
        )
        self.assertEqual(status, 200)
        events = self._drain()
        self.assertEqual(len(events), 1)
        # input estimated from messages ("hi there" = 8 chars // 4 = 2)
        self.assertEqual(events[0]["input_tokens"], 2)
        # output estimated from streamed content ("Hello world" = 11 chars // 4 = 2)
        self.assertEqual(events[0]["output_tokens"], 2)

    def test_upstream_error_forwarded_without_telemetry(self):
        status, _ctype, raw = self._post("/v1/chat/completions", {
            "model": "test-err", "messages": [{"role": "user", "content": "hi"}]},
            expect_status=500,
        )
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(raw)["error"], "boom")
        self.assertEqual(self._drain(), [])

    def test_upstream_down_returns_502_no_telemetry(self):
        down = ProxyServer(
            upstream="http://127.0.0.1:1",  # nothing listens here
            listen_port=0,
            ingest_queue=self.events,
        )
        down.start()
        self.addCleanup(down.stop)
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", down.port, timeout=10)
        try:
            conn.request("POST", "/v1/chat/completions",
                         body=json.dumps({"model": "x", "messages": []}).encode(),
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            status = resp.status
            resp.read()
        finally:
            conn.close()
        self.assertEqual(status, 502)
        self.assertEqual(self._drain(), [])

    def test_passthrough_get_no_telemetry(self):
        status, raw = self._get("/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["data"][0]["id"], "llama3.1:8b")
        self.assertEqual(self._drain(), [])

    def test_dedup_keys_unique_per_request(self):
        for model in ("llama3.1:8b", "qwen2.5-coder"):
            self._post("/v1/chat/completions", {
                "model": model, "messages": [{"role": "user", "content": "hi"}]},
            )
        events = self._drain()
        self.assertEqual(len(events), 2)
        self.assertEqual(
            len({e["dedup_key"] for e in events}), 2,
            "each request must produce a distinct dedup key",
        )


class TestProxyStatus(unittest.TestCase):
    """proxy_daemon_status() must cover both hosting modes."""

    def _settings(self, enabled=True, port=11435):
        return {
            "enabled": enabled,
            "upstream": "http://127.0.0.1:11434",
            "listen_port": port,
            "agent_name": "ollama_proxy",
            "provider_id": "local",
        }

    def test_status_standalone_mode(self):
        with patch("tokstat.proxy.is_proxy_running", return_value=4242):
            st = proxy_daemon_status()
        self.assertTrue(st["running"])
        self.assertEqual(st["mode"], "standalone")
        self.assertEqual(st["pid"], 4242)
        self.assertEqual(st["listen_port"], 11435)  # uniform shape across modes

    def test_status_daemon_hosted_running(self):
        with patch("tokstat.proxy.is_proxy_running", return_value=None), \
             patch.object(config, "proxy_settings", return_value=self._settings()), \
             patch("tokstat.proxy._proxy_responds", return_value=True), \
             patch.object(daemon, "is_running", return_value=999):
            st = proxy_daemon_status()
        self.assertTrue(st["running"])
        self.assertEqual(st["mode"], "daemon")
        self.assertEqual(st["pid"], 999)
        self.assertEqual(st["listen_port"], 11435)

    def test_status_daemon_hosted_not_listening(self):
        # Daemon up but proxy thread failed to bind -> running False, mode
        # stays "daemon" so the operator knows where to look.
        with patch("tokstat.proxy.is_proxy_running", return_value=None), \
             patch.object(config, "proxy_settings", return_value=self._settings()), \
             patch("tokstat.proxy._proxy_responds", return_value=False), \
             patch.object(daemon, "is_running", return_value=999):
            st = proxy_daemon_status()
        self.assertFalse(st["running"])
        self.assertEqual(st["mode"], "daemon")

    def test_status_daemon_dead(self):
        with patch("tokstat.proxy.is_proxy_running", return_value=None), \
             patch.object(config, "proxy_settings", return_value=self._settings()), \
             patch("tokstat.proxy._proxy_responds", return_value=True), \
             patch.object(daemon, "is_running", return_value=None):
            st = proxy_daemon_status()
        self.assertFalse(st["running"])
        self.assertEqual(st["mode"], "daemon")

    def test_status_disabled_returns_not_running(self):
        with patch("tokstat.proxy.is_proxy_running", return_value=None), \
             patch.object(
                 config, "proxy_settings", return_value=self._settings(enabled=False)
             ):
            st = proxy_daemon_status()
        self.assertFalse(st["running"])
        self.assertIsNone(st["mode"])
        self.assertIsNone(st["pid"])

    def test_status_daemon_import_failure_is_safe(self):
        # Even if the daemon module cannot be imported, status must not raise.
        with patch("tokstat.proxy.is_proxy_running", return_value=None), \
             patch.object(config, "proxy_settings", return_value=self._settings()), \
             patch("tokstat.proxy._proxy_responds", return_value=False), \
             patch("builtins.__import__", side_effect=ImportError("boom")):
            st = proxy_daemon_status()
        self.assertFalse(st["running"])
        self.assertEqual(st["mode"], "daemon")

    def test_stop_hints_when_daemon_hosted(self):
        import contextlib
        import io

        with patch("tokstat.proxy.is_proxy_running", return_value=None), \
             patch.object(config, "proxy_settings", return_value=self._settings()), \
             patch("tokstat.proxy._proxy_responds", return_value=True), \
             patch.object(daemon, "is_running", return_value=999):
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                from tokstat.proxy import stop_proxy_daemon

                stop_proxy_daemon()
        self.assertIn("hosted by the daemon", buf.getvalue())

    def test_start_refuses_when_daemon_hosted(self):
        import contextlib
        import io

        from tokstat.proxy import start_proxy_daemon

        with patch("tokstat.proxy.is_proxy_running", return_value=None), \
             patch.object(config, "proxy_settings", return_value=self._settings()), \
             patch("tokstat.proxy._proxy_responds", return_value=True), \
             patch.object(daemon, "is_running", return_value=999):
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                start_proxy_daemon()
        self.assertIn("hosted by the daemon", buf.getvalue())

    def test_proxy_responds_checks_http_not_just_tcp(self):
        # _proxy_responds must check the HTTP answer, not just the TCP port:
        # an unrelated process squatting on the port must not count as running.
        from tokstat.proxy import _proxy_responds

        with patch("tokstat.proxy.http.client.HTTPConnection") as mock_conn:
            mock_conn.return_value.getresponse.return_value.status = 200
            self.assertTrue(_proxy_responds(11435))
            mock_conn.return_value.getresponse.return_value.status = 500
            self.assertFalse(_proxy_responds(11435))


if __name__ == "__main__":
    unittest.main()
