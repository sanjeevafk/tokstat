# proxy.py
"""Transparent local-model proxy with telemetry capture (stdlib only).

Listens on 127.0.0.1:<port> (default 11435) and forwards OpenAI-compatible
(/v1/chat/completions, /v1/completions) and Ollama-native (/api/chat,
/api/generate) requests to a configurable upstream (default Ollama on 11434),
extracting real token usage and recording it as usage_events.

Events are delivered to a shared ingestion queue when the daemon runs the
proxy in-process, or POSTed to the local ingestion server when the proxy runs
standalone (`tokstat proxy start`).

Streaming (SSE) responses are relayed chunk-by-chunk to the client while the
final chunk's `usage` (OpenAI-compat) or `prompt_eval_count`/`eval_count`
(Ollama-native) is captured for telemetry. When a server omits counts, tokens
are estimated deterministically (content chars / 4) - never fabricated.
"""
import hashlib
import http.client
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import urlparse

from . import config
from .collectors.base import now_iso

OPENAI_CHAT_PATH = "/v1/chat/completions"
OPENAI_COMPLETIONS_PATH = "/v1/completions"
OPENAI_RESPONSES_PATH = "/v1/responses"  # Codex CLI / Responses API
OLLAMA_CHAT_PATH = "/api/chat"
OLLAMA_GENERATE_PATH = "/api/generate"

_TELEMETRY_PATHS = {
    OPENAI_CHAT_PATH,
    OPENAI_COMPLETIONS_PATH,
    OPENAI_RESPONSES_PATH,
    OLLAMA_CHAT_PATH,
    OLLAMA_GENERATE_PATH,
}
_PASSTHROUGH_PATHS = {
    "/v1/models",
    "/api/tags",
    "/api/version",
    "/api/ps",
    "/health",
    "/",
}

_UPSTREAM_TIMEOUT_SEC = 10.0


def _make_emitter(ingest_queue: Optional[object]) -> Callable[[dict], None]:
    """Return an event sink: in-process queue push or POST to the ingestion server."""
    if ingest_queue is not None:
        def emit(event):
            ingest_queue.put(event)
        return emit

    def emit(event):
        try:
            conn = http.client.HTTPConnection(
                config.SERVER_HOST, config.SERVER_PORT, timeout=3
            )
            try:
                conn.request(
                    "POST", "/v1/events",
                    body=json.dumps([event]).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                conn.getresponse().read()
            finally:
                conn.close()
        except Exception:
            # Telemetry must never break inference; drop the event.
            pass

    return emit


class ProxyHandler(BaseHTTPRequestHandler):
    server: "ProxyServer"  # ProxyServer.start() binds itself to the httpd

    def log_message(self, format, *args):
        return  # keep output clean

    # -- plumbing ------------------------------------------------------------
    def _connect(self):
        upstream = self.server.upstream
        parsed = urlparse(upstream)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        cls = (
            http.client.HTTPSConnection
            if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        return cls(host, port, timeout=_UPSTREAM_TIMEOUT_SEC)

    def _forward_headers(self):
        headers = {
            "Content-Type": self.headers.get("Content-Type") or "application/json"
        }
        for name in ("Accept", "Authorization", "OpenAI-Organization"):
            val = self.headers.get(name)
            if val:
                headers[name] = val
        return headers

    def _reply_raw(self, status, content_type, body):
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, payload):
        self._reply_raw(code, "application/json", json.dumps(payload).encode("utf-8"))

    def _safe_reply_error(self, code, message):
        try:
            self._send_json(code, {"error": message})
        except Exception:
            pass

    # -- usage extraction ----------------------------------------------------
    @staticmethod
    def _usage_from_payload(payload: Optional[dict], path: str) -> dict:
        """Map an upstream JSON payload to (input, output) token counts."""
        if not isinstance(payload, dict):
            return {"input": 0, "output": 0}
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            # Responses API SSE final chunk nests usage under "response".
            resp = payload.get("response")
            if isinstance(resp, dict):
                usage = resp.get("usage")
        if isinstance(usage, dict):
            return {
                "input": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
                "output": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            }
        if path in (OLLAMA_CHAT_PATH, OLLAMA_GENERATE_PATH):
            return {
                "input": int(payload.get("prompt_eval_count") or 0),
                "output": int(payload.get("eval_count") or 0),
            }
        return {"input": 0, "output": 0}

    @staticmethod
    def _content_length(payload: Optional[dict], path: str) -> int:
        """Characters of generated content in a (stream) payload."""
        if not isinstance(payload, dict):
            return 0
        total = 0
        choices = payload.get("choices")
        if isinstance(choices, list):
            for c in choices:
                delta = c.get("delta") or c.get("message") or {}
                content = delta.get("content")
                if isinstance(content, str):
                    total += len(content)
        msg = payload.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            total += len(msg["content"])
        response = payload.get("response")  # Ollama /api/generate
        if isinstance(response, str):
            total += len(response)
        if isinstance(payload.get("output_text"), str):  # Responses API
            total += len(payload["output_text"])
        delta = payload.get("delta")  # Responses API streamed text chunks
        if isinstance(delta, str):
            total += len(delta)
        return total

    @staticmethod
    def _estimate_input_tokens(body: dict) -> int:
        """Fallback input estimate from the request body (content chars / 4)."""
        total = 0
        messages = body.get("messages")
        if isinstance(messages, list):
            for m in messages:
                content = m.get("content")
                if isinstance(content, str):
                    total += len(content) // 4
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            total += len(part["text"]) // 4
        prompt = body.get("prompt")
        if isinstance(prompt, str):
            total += len(prompt) // 4
        return total

    @staticmethod
    def _estimate_output_tokens(payload: Optional[dict], path: str) -> int:
        return ProxyHandler._content_length(payload, path) // 4

    def _emit_event(self, model, input_tokens, output_tokens):
        if not model or (input_tokens <= 0 and output_tokens <= 0):
            return  # nothing measurable -> never fabricate an event
        occurred_at = now_iso()
        # Stable dedup key: identical retries of the same request (same model,
        # same second, same token counts) collide so INSERT OR IGNORE dedupes
        # them; two distinct same-second requests with identical counts can
        # still collide (documented second-resolution granularity).
        dedup = hashlib.sha1(
            f"{model}|{occurred_at}|{input_tokens}|{output_tokens}".encode("utf-8")
        ).hexdigest()[:16]
        event = {
            "event_id": None,
            "occurred_at": occurred_at,
            "provider_id": self.server.provider_id,
            "agent_name": self.server.agent_name,
            "account_id": None,
            "workspace_id": "Global/No Project",
            "session_id": "Global/No Session",
            "turn_id": str(self.server.next_seq()),
            "message_id": None,
            "tool_call_id": None,
            "event_type": "message_usage",
            "model_raw": model,
            "model_canonical": model,
            "model_lineage_id": None,
            "input_tokens": max(1, input_tokens),
            "output_tokens": max(1, output_tokens),
            "reasoning_tokens": None,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "total_tokens": max(1, input_tokens) + max(1, output_tokens),
            "cost_usd": 0.0,
            "requests": 1,
            "tool_name": None,
            "status": "ok",
            "dedup_key": "proxy-" + dedup,
            "raw_event_id": None,
            "normalization_version": None,
        }
        try:
            self.server.emit(event)
        except Exception:
            pass  # telemetry must never break inference

    # -- forwarding ----------------------------------------------------------
    def _forward_non_streaming(self, path, raw_body) -> Optional[dict]:
        """Forward and reply; returns usage dict or None (already replied, no telemetry)."""
        try:
            conn = self._connect()
        except Exception as exc:
            self._safe_reply_error(502, f"upstream unavailable: {exc}")
            return None
        try:
            conn.request("POST", path, body=raw_body, headers=self._forward_headers())
            resp = conn.getresponse()
            raw = resp.read()
            if resp.status >= 400:
                self._reply_raw(
                    resp.status, resp.getheader("Content-Type") or "application/json", raw
                )
                return None  # upstream error: forward, no telemetry
            content_type = resp.getheader("Content-Type") or "application/json"
            self._reply_raw(resp.status, content_type, raw)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                payload = None
            return self._usage_from_payload(payload, path)
        except (http.client.HTTPException, OSError) as exc:
            self._safe_reply_error(502, f"upstream request failed: {exc}")
            return None
        finally:
            conn.close()

    def _forward_streaming(self, path, raw_body) -> Optional[dict]:
        """Relay an SSE stream chunk-by-chunk; returns usage dict or None."""
        try:
            conn = self._connect()
        except Exception as exc:
            self._safe_reply_error(502, f"upstream unavailable: {exc}")
            return None
        try:
            conn.request("POST", path, body=raw_body, headers=self._forward_headers())
            resp = conn.getresponse()
            if resp.status >= 400:
                self._reply_raw(
                    resp.status, resp.getheader("Content-Type") or "application/json",
                    resp.read(),
                )
                return None
            started = False
            self.send_response(resp.status)
            # Headers are now started; any failure below must NOT emit a second
            # HTTP response on this connection (close-delimited relay).
            started = True
            # NOTE: only Content-Type is forwarded. Transfer-Encoding must NOT
            # be relayed: http.client de-chunks the upstream body, and the
            # client connection is close-delimited (HTTP/1.0, no Content-Length),
            # so advertising chunked framing would corrupt the stream.
            if resp.getheader("Content-Type"):
                self.send_header("Content-Type", resp.getheader("Content-Type"))
            self.end_headers()

            content_chars = 0
            last_payload = None
            while True:
                line = resp.readline()
                if not line:
                    break
                try:
                    self.wfile.write(line)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass  # client gone; keep draining upstream for telemetry
                stripped = line.decode("utf-8", errors="ignore").strip()
                if stripped.startswith("data:"):
                    data = stripped[len("data:"):].strip()
                    if data and data != "[DONE]":
                        try:
                            payload = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        last_payload = payload
                        content_chars += self._content_length(payload, path)

            if last_payload is None:
                return {"input": 0, "output": 0}
            usage = self._usage_from_payload(last_payload, path)
            out_tok = usage["output"] or (content_chars // 4)
            return {"input": usage["input"], "output": out_tok}
        except (http.client.HTTPException, OSError) as exc:
            if started:
                # Headers + partial body already sent: never emit a second HTTP
                # response mid-stream; just close the connection.
                return None
            self._safe_reply_error(502, f"upstream stream failed: {exc}")
            return None
        finally:
            conn.close()

    # -- handlers ------------------------------------------------------------
    def _forward_passthrough(self, path):
        """Forward an arbitrary upstream POST verbatim, no telemetry.

        Used for paths outside the telemetry set (e.g. Codex CLI pointed at the
        proxy via OPENAI_BASE_URL hitting non-completion endpoints): the
        request and response pass through untouched and nothing is recorded.
        """
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            # Chunked (Transfer-Encoding) request bodies cannot be re-read
            # safely with the stdlib handler; reject rather than forward an
            # empty body upstream.
            self._safe_reply_error(411, "Content-Length required")
            return
        try:
            raw_body = self.rfile.read(int(length_header))
        except (ValueError, OSError):
            self._safe_reply_error(400, "bad request body")
            return
        try:
            conn = self._connect()
        except Exception as exc:
            self._safe_reply_error(502, f"upstream unavailable: {exc}")
            return
        try:
            conn.request("POST", path, body=raw_body, headers=self._forward_headers())
            resp = conn.getresponse()
            self._reply_raw(
                resp.status,
                resp.getheader("Content-Type") or "application/json",
                resp.read(),
            )
        except (http.client.HTTPException, OSError) as exc:
            self._safe_reply_error(502, f"upstream request failed: {exc}")
        finally:
            conn.close()

    def do_POST(self):
        if self.path not in _TELEMETRY_PATHS:
            self._forward_passthrough(self.path)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw_body = self.rfile.read(length)
            body = json.loads(raw_body.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid JSON body"})
            return

        model = str(body.get("model") or "").strip() or "local/unknown"
        if body.get("stream"):
            usage = self._forward_streaming(self.path, raw_body)
        else:
            usage = self._forward_non_streaming(self.path, raw_body)
        if usage is None:
            return  # already replied (upstream error / failure), no telemetry
        if not isinstance(usage, dict):
            return
        in_tok = usage.get("input") or 0
        out_tok = usage.get("output") or 0
        if in_tok <= 0:
            in_tok = self._estimate_input_tokens(body)
        self._emit_event(model, in_tok, out_tok)

    def do_GET(self):
        # Any GET path is forwarded verbatim (mirrors do_POST passthrough), so
        # base-URL tools probing routes beyond the classic /v1/models still work.
        try:
            conn = self._connect()
        except Exception as exc:
            self._safe_reply_error(502, f"upstream unavailable: {exc}")
            return
        try:
            conn.request("GET", self.path)
            resp = conn.getresponse()
            self._reply_raw(
                resp.status, resp.getheader("Content-Type") or "application/json", resp.read()
            )
        except (http.client.HTTPException, OSError) as exc:
            self._safe_reply_error(502, f"upstream request failed: {exc}")
        finally:
            conn.close()


class ProxyServer:
    """Runs the transparent proxy; shares an ingestion queue when available."""

    def __init__(
        self,
        upstream: Optional[str] = None,
        listen_port: Optional[int] = None,
        agent_name: Optional[str] = None,
        provider_id: Optional[str] = None,
        ingest_queue: Optional[object] = None,
        host: str = "127.0.0.1",
    ):
        settings = config.proxy_settings()
        self.upstream = upstream or settings["upstream"]
        self.host = host
        self.port = listen_port if listen_port is not None else settings["listen_port"]
        self.agent_name = agent_name or settings["agent_name"]
        self.provider_id = provider_id or settings["provider_id"]
        self.emit = _make_emitter(ingest_queue)
        self._httpd = None
        self._thread = None
        self._seq = 0
        self._seq_lock = threading.Lock()

    def next_seq(self) -> int:
        with self._seq_lock:
            self._seq += 1
            return self._seq

    def start(self) -> None:
        self._httpd = ThreadingHTTPServer((self.host, self.port), ProxyHandler)
        # Expose shared state on the httpd so handlers see it via self.server.
        self._httpd.upstream = self.upstream
        self._httpd.agent_name = self.agent_name
        self._httpd.provider_id = self.provider_id
        self._httpd.emit = self.emit
        self._httpd.next_seq = self.next_seq
        self.port = self._httpd.server_address[1]  # reflect actual port (0 => ephemeral)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        self._httpd = None
        self._thread = None


# --- standalone lifecycle (`tokstat proxy start|stop|status`) ---------------
def read_proxy_pid() -> Optional[int]:
    try:
        with open(config.PROXY_PID_PATH, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def is_proxy_running() -> Optional[int]:
    pid = read_proxy_pid()
    if pid is None:
        return None
    try:
        os.kill(pid, 0)  # raises ProcessLookupError when dead
        return pid
    except OSError:
        return None


def _proxy_responds(port: int) -> bool:
    """True if a proxy answers /v1/models on 127.0.0.1:<port> (1s timeout).

    Unlike a bare TCP connect this proves the listener is actually the proxy
    (passthrough GET handler), not an unrelated process squatting on the port.
    """
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            conn.request("GET", "/v1/models")
            return conn.getresponse().status == 200
        finally:
            conn.close()
    except (http.client.HTTPException, OSError):
        return False


def proxy_daemon_status() -> dict:
    """Report proxy state across both hosting modes.

    - Standalone (`tokstat proxy start`): a pid file exists -> mode
      "standalone" with the proxy's own pid.
    - Daemon-hosted ([proxy] enabled = true in config.toml): no pid file is
      written, so detect via daemon liveness + the configured listen port
      actually answering as the proxy -> mode "daemon". If the daemon is up
      but the port is not answering (e.g. the in-process proxy failed to
      bind), running is False but mode stays "daemon" so the operator knows
      where to look.

    Both modes return the same keys: running, mode, pid, listen_port,
    upstream.
    """
    settings = config.proxy_settings()
    base = {
        "running": False,
        "mode": None,
        "pid": None,
        "listen_port": settings["listen_port"],
        "upstream": settings["upstream"],
    }
    pid = is_proxy_running()
    if pid is not None:
        base.update({"running": True, "mode": "standalone", "pid": pid})
        return base

    if not settings["enabled"]:
        return base
    try:
        from . import daemon

        daemon_pid = daemon.is_running()
    except ImportError:
        daemon_pid = None
    base.update({"mode": "daemon", "pid": daemon_pid})
    base["running"] = daemon_pid is not None and _proxy_responds(settings["listen_port"])
    return base


def start_proxy_daemon(
    upstream: Optional[str] = None,
    port: Optional[int] = None,
    agent_name: Optional[str] = None,
) -> None:
    running = is_proxy_running()
    if running:
        print(f"[proxy] already running (pid {running})")
        return
    status = proxy_daemon_status()
    if status.get("mode") == "daemon" and status.get("running"):
        print(
            "[proxy] already hosted by the daemon; stop it with `tokstat daemon stop` "
            "or set [proxy] enabled = false in config.toml",
            file=sys.stderr,
        )
        return
    config.ensure_tokstat_dir()
    cmd = [sys.executable, "-m", "tokstat.proxy", "run"]
    if upstream:
        cmd += ["--upstream", upstream]
    if port:
        cmd += ["--port", str(port)]
    if agent_name:
        cmd += ["--agent-name", agent_name]
    log = open(config.DAEMON_LOG_PATH, "ab")
    try:
        subprocess.Popen(
            cmd,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    finally:
        log.close()
    for _ in range(50):  # wait up to 5s for the pid file
        if is_proxy_running():
            print(f"[proxy] started (pid {is_proxy_running()})")
            return
        time.sleep(0.1)
    print("[proxy] failed to confirm startup; check ~/.tokstat/daemon.log", file=sys.stderr)

def stop_proxy_daemon() -> None:
    pid = is_proxy_running()
    if pid is None:
        status = proxy_daemon_status()
        if status.get("mode") == "daemon":
            print(
                "[proxy] hosted by the daemon; stop it with `tokstat daemon stop` "
                "or set [proxy] enabled = false in config.toml",
                file=sys.stderr,
            )
            return
        print("[proxy] not running")
        return
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):  # wait up to 5s for clean shutdown
        if is_proxy_running() is None:
            print("[proxy] stopped")
            return
        time.sleep(0.1)
    print("[proxy] did not stop cleanly; pid file may be stale", file=sys.stderr)

def run_foreground(
    upstream: Optional[str] = None,
    port: Optional[int] = None,
    agent_name: Optional[str] = None,
) -> None:
    settings = config.proxy_settings()
    srv = ProxyServer(
        upstream=upstream or settings["upstream"],
        listen_port=port if port is not None else settings["listen_port"],
        agent_name=agent_name or settings["agent_name"],
    )
    srv.start()
    with open(config.PROXY_PID_PATH, "w") as f:
        f.write(str(os.getpid()))
    print(
        f"[proxy] listening on http://127.0.0.1:{srv.port} -> {srv.upstream} "
        f"(agent={srv.agent_name})"
    )

    def _shutdown(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
        try:
            os.remove(config.PROXY_PID_PATH)
        except OSError:
            pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tokstat.proxy")
    parser.add_argument("run")
    parser.add_argument("--upstream", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--agent-name", default=None)
    args = parser.parse_args()
    run_foreground(upstream=args.upstream, port=args.port, agent_name=args.agent_name)
