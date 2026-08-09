# daemon.py
"""Native background daemon: ingestion server + collector loop.

`tokstat daemon start|stop|status` manage a detached process that runs the
collectors on an interval and serves the /v1/events ingestion endpoint.
Graceful shutdown drains the ingestion queue before exiting.
"""
import datetime
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Optional

from . import config, server
from .collectors import get_collectors, run_collectors_once


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

_logger = logging.getLogger("tokstat.daemon")


def _setup_logging() -> None:
    config.ensure_tokstat_dir()
    logging.basicConfig(
        filename=config.DAEMON_LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def read_pid() -> Optional[int]:
    try:
        with open(config.DAEMON_PID_PATH, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def is_running() -> Optional[int]:
    pid = read_pid()
    if pid is None:
        return None
    try:
        os.kill(pid, 0)  # raises ProcessLookupError when dead
        return pid
    except OSError:
        return None


def _pid_uptime(pid: int) -> Optional[int]:
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            fields = f.read().split()
        start_ticks = int(fields[21])
        clock = os.sysconf("SC_CLK_TCK")
        boot_time = time.time() - (time.monotonic() - start_ticks / clock)
        return int(time.time() - boot_time)
    except (OSError, ValueError, IndexError):
        return None


def start_daemon() -> None:
    running = is_running()
    if running:
        print(f"[daemon] already running (pid {running})")
        return
    config.ensure_tokstat_dir()
    log = open(config.DAEMON_LOG_PATH, "ab")
    try:
        subprocess.Popen(
            [sys.executable, "-m", "tokstat.daemon", "run"],
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    finally:
        log.close()
    for _ in range(50):  # wait up to 5s for the pid file
        if is_running():
            print(f"[daemon] started (pid {is_running()})")
            return
        time.sleep(0.1)
    print("[daemon] failed to confirm startup; check ~/.tokstat/daemon.log", file=sys.stderr)


def stop_daemon() -> None:
    pid = is_running()
    if pid is None:
        print("[daemon] not running")
        return
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):  # wait up to 5s for clean shutdown
        if is_running() is None:
            print("[daemon] stopped")
            return
        time.sleep(0.1)
    print("[daemon] did not stop cleanly; pid file may be stale", file=sys.stderr)


def daemon_status() -> dict:
    pid = is_running()
    events_total = 0
    collectors = {}
    try:
        conn = config.connect_db()
        events_total = conn.execute("SELECT count(*) FROM usage_events").fetchone()[0]
        for row in conn.execute(
            "SELECT collector_id, updated_at FROM collector_state"
        ):
            collectors[row["collector_id"]] = {"last_run": row["updated_at"]}
        conn.close()
    except Exception:
        pass
    return {
        "running": pid is not None,
        "pid": pid,
        "uptime_sec": _pid_uptime(pid) if pid else None,
        "events_total": events_total,
        "collectors": collectors,
    }


def run_foreground() -> None:
    """Daemon main loop (invoked via `python -m tokstat.daemon run`)."""
    _setup_logging()
    config.ensure_tokstat_dir()
    with open(config.DAEMON_PID_PATH, "w") as f:
        f.write(str(os.getpid()))

    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())

    ingest = server.IngestionServer()
    # Show every collector (with pending status) immediately in /health.
    ingest.collector_status = {c.name: {"status": "pending"} for c in get_collectors()}
    ingest.start()
    _logger.info("daemon started pid=%s ingest_port=%s", os.getpid(), ingest.port)
    print(f"[daemon] foreground: ingestion server on {ingest.host}:{ingest.port}")

    # Optional local-model proxy: enabled via [proxy] enabled = true in
    # ~/.tokstat/config.toml. Shares the ingestion queue for zero-overhead
    # telemetry recording (single-writer DB pattern preserved).
    proxy_srv = None
    proxy_settings = config.proxy_settings()
    if proxy_settings["enabled"]:
        try:
            from . import proxy as proxy_mod

            proxy_srv = proxy_mod.ProxyServer(
                upstream=proxy_settings["upstream"],
                listen_port=proxy_settings["listen_port"],
                agent_name=proxy_settings["agent_name"],
                ingest_queue=ingest.ingestion_queue,
            )
            proxy_srv.start()
            _logger.info(
                "proxy started on port %s -> %s", proxy_srv.port, proxy_srv.upstream
            )
            print(f"[daemon] proxy listening on 127.0.0.1:{proxy_srv.port}")
        except Exception as exc:
            _logger.error("proxy failed to start: %s", exc)
            print(f"[daemon] proxy failed to start: {exc}", file=sys.stderr)

    backoff = config.COLLECTOR_BACKOFF_MIN_SEC
    try:
        while not stop_event.is_set():
            try:
                results = run_collectors_once()
                # Opt-in authoritative provider usage sync ([sync] enabled = true
                # in config.toml). Interval-guarded; never runs automatically for
                # the bare `tokstat` command.
                if config.sync_settings()["enabled"]:
                    try:
                        from . import sync as sync_mod

                        sync_result = sync_mod.maybe_sync()
                        if sync_result:
                            _logger.info("provider sync: %s", sync_result)
                    except Exception as sync_exc:
                        _logger.error("provider sync failed: %s", sync_exc)
                ingest.collector_status = {
                    r["collector"]: {
                        "events": r["events"],
                        "inserted": r["inserted"],
                        "skipped": r["skipped"],
                        "last_run": _now_iso(),
                    }
                    for r in results
                }
                wait_sec = config.COLLECTOR_POLL_INTERVAL_SEC
                backoff = config.COLLECTOR_BACKOFF_MIN_SEC
            except Exception as exc:  # keep the daemon alive on collector errors
                _logger.error("collector run failed: %s", exc)
                wait_sec = backoff
                backoff = min(backoff * 2, config.COLLECTOR_BACKOFF_MAX_SEC)
            stop_event.wait(wait_sec)
    finally:
        ingest.stop()  # drains the ingestion queue
        if proxy_srv:
            proxy_srv.stop()
        _logger.info("daemon stopped")
        try:
            os.remove(config.DAEMON_PID_PATH)
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        run_foreground()
    else:
        print("usage: python -m tokstat.daemon run", file=sys.stderr)
