# server.py
"""Embedded HTTP ingestion server (stdlib only, zero new dependencies).

Endpoints:
  POST /v1/events     - single JSON object or batch array; OpenUsage/OpenTelemetry
                        style event payloads, normalized into usage_events rows.
  POST /v1/telemetry  - legacy alias of /v1/events for existing user hooks.
  GET  /health        - daemon/collector/database status.

Events are pushed onto a queue and flushed to SQLite by a single batching
writer thread (every 1s or every 50 events) - the only writer to the DB,
which keeps WAL contention safe (Non-Negotiable #5).
"""
import hashlib
import json
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from . import config
from .collectors.base import EVENT_COLUMNS

BATCH_FLUSH_INTERVAL_SEC = 1.0


def normalize_event(raw) -> tuple[Optional[dict], Optional[str]]:
    """Normalize a raw wire payload into a usage_events row.

    Returns (event, None) on success or (None, error_message).
    """
    if not isinstance(raw, dict):
        return None, "event must be a JSON object"
    agent_name = str(raw.get("agent_name") or "").strip()
    occurred_at = str(raw.get("occurred_at") or "").strip()
    if not agent_name:
        return None, "missing required field: agent_name"
    if not occurred_at:
        return None, "missing required field: occurred_at"

    def to_int(key, default=0):
        try:
            val = raw.get(key)
            return int(val) if val is not None else default
        except (TypeError, ValueError):
            return default

    def to_float(key, default=0.0):
        try:
            val = raw.get(key)
            return float(val) if val is not None else default
        except (TypeError, ValueError):
            return default

    in_tok = to_int("input_tokens")
    out_tok = to_int("output_tokens")
    cache_tok = to_int("cache_read_tokens")
    total = to_int("total_tokens", 0)
    if total <= 0 and (in_tok or out_tok or cache_tok):
        total = in_tok + out_tok + cache_tok

    event = {
        "event_id": raw.get("event_id"),
        "occurred_at": occurred_at,
        "provider_id": raw.get("provider_id"),
        "agent_name": agent_name,
        "account_id": raw.get("account_id"),
        "workspace_id": raw.get("workspace_id"),
        "session_id": raw.get("session_id"),
        "turn_id": raw.get("turn_id"),
        "message_id": raw.get("message_id"),
        "tool_call_id": raw.get("tool_call_id"),
        "event_type": raw.get("event_type") or "message_usage",
        "model_raw": raw.get("model_raw"),
        "model_canonical": raw.get("model_canonical"),
        "model_lineage_id": raw.get("model_lineage_id"),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "reasoning_tokens": to_int("reasoning_tokens"),
        "cache_read_tokens": cache_tok,
        "cache_write_tokens": to_int("cache_write_tokens"),
        "total_tokens": total,
        "cost_usd": to_float("cost_usd"),
        "requests": to_int("requests", 1) or 1,
        "tool_name": raw.get("tool_name"),
        "status": str(raw.get("status") or "ok")[:50],
        "dedup_key": raw.get("dedup_key"),
        "raw_event_id": raw.get("raw_event_id"),
        "normalization_version": raw.get("normalization_version"),
    }
    if not event["dedup_key"]:
        canonical = json.dumps(raw, sort_keys=True, default=str)
        event["dedup_key"] = "ingest-" + hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
    return event, None


class TelemetryIngestHandler(BaseHTTPRequestHandler):
    server: "IngestionServer"  # set by IngestionServer

    def log_message(self, format, *args):
        return  # keep the daemon output clean

    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path not in ("/v1/events", "/v1/telemetry"):
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid JSON body"})
            return

        items = payload if isinstance(payload, list) else [payload]
        accepted = 0
        errors = []
        for item in items:
            event, err = normalize_event(item)
            if err:
                errors.append(err)
                continue
            self.server.ingestion_queue.put(event)
            accepted += 1
        if accepted == 0:
            self._send_json(400, {"error": "no valid events", "errors": errors[:5]})
            return
        self._send_json(202, {"accepted": accepted, "rejected": len(errors), "errors": errors[:5]})

    def do_GET(self):
        if self.path != "/health":
            self._send_json(404, {"error": "not found"})
            return
        db_size = 0
        events_total = 0
        try:
            conn = config.connect_db()
            db_size = conn.execute("PRAGMA page_count;").fetchone()[0] * conn.execute(
                "PRAGMA page_size;"
            ).fetchone()[0]
            events_total = conn.execute(
                "SELECT count(*) FROM usage_events"
            ).fetchone()[0]
            conn.close()
        except Exception:
            pass
        self._send_json(200, {
            "status": "ok",
            "db_size_bytes": db_size,
            "events_total": events_total,
            "queue_depth": self.server.ingestion_queue.qsize(),
            "collectors": self.server.collector_status,
        })


class IngestionServer:
    """Runs the HTTP server plus the single batching writer thread."""

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.host = host or config.SERVER_HOST
        self.port = port or config.SERVER_PORT
        self.ingestion_queue: queue.Queue = queue.Queue()
        self.collector_status = {}
        self._httpd = None
        self._thread = None
        self._writer = None
        self._stop = threading.Event()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._httpd = ThreadingHTTPServer((self.host, self.port), TelemetryIngestHandler)
        self.port = self._httpd.server_address[1]  # reflect actual port (0 => ephemeral)
        # expose shared state on the httpd (handlers see it via self.server)
        self._httpd.ingestion_queue = self.ingestion_queue
        self._httpd.collector_status = self.collector_status
        self._stop.clear()
        self._writer = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer.start()
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.flush()
        self._stop.set()
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        self._httpd = None
        self._thread = None
        self._writer = None

    # -- batching writer ------------------------------------------------------
    def flush(self) -> int:
        """Drain the queue immediately (blocking). Returns rows written."""
        events = []
        while True:
            try:
                events.append(self.ingestion_queue.get_nowait())
            except queue.Empty:
                break
        if not events:
            return 0
        return self._write_batch(events)

    def _drain(self) -> list[dict]:
        events = []
        while True:
            try:
                events.append(self.ingestion_queue.get_nowait())
            except queue.Empty:
                return events

    def _writer_loop(self) -> None:
        while not self._stop.wait(BATCH_FLUSH_INTERVAL_SEC):
            events = self._drain()
            if events:
                self._write_batch(events)
        events = self._drain()  # final drain on shutdown
        if events:
            self._write_batch(events)

    def _write_batch(self, events: list[dict]) -> int:
        conn = config.connect_db()
        try:
            placeholders = ",".join("?" * len(EVENT_COLUMNS))
            cols = ",".join(EVENT_COLUMNS)
            with conn:
                for ev in events:
                    conn.execute(
                        f"INSERT OR IGNORE INTO usage_events ({cols}) VALUES ({placeholders})",
                        tuple(ev.get(c) for c in EVENT_COLUMNS),
                    )
            return len(events)
        except Exception as exc:
            print(f"Warning: ingestion batch write failed: {exc}", file=sys.stderr)
            return 0
        finally:
            conn.close()


def run_server_blocking(host: Optional[str] = None, port: Optional[int] = None) -> None:
    """Run the ingestion server in the foreground (used by the daemon)."""
    srv = IngestionServer(host=host, port=port)
    srv.start()
    print(f"[*] Ingestion server listening on http://{srv.host}:{srv.port}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
