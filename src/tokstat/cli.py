# cli.py
"""TokStat CLI - AI Engineering Telemetry Observatory & Token Tracker.

Commands:
  tokstat                       gather usage from all sources, generate
                                tokstat_dashboard.html and open it
  tokstat --no-collect          render the dashboard only (skip gathering)
  tokstat --no-open             do not auto-open the browser
  tokstat --watch [--port N]    live-sync watch mode
  tokstat --export <dir>        multi-format exports
  tokstat migrate [--force]     import legacy OpenUsage/Tokentop DBs
  tokstat collect --once        run all collectors once
  tokstat daemon start|stop|status
  tokstat sync [--lookback-days N]
                                opt-in authoritative usage sync from
                                Anthropic/OpenAI usage APIs (never automatic)
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import time
import webbrowser
from datetime import datetime

from . import analytics, config, exporter, migration, renderer
from .collectors import run_collectors_once


class TelemetryHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging to keep watch mode output clean
        return

    def end_headers(self):
        # Enable CORS so the browser viewing file:// can query the local server
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_GET(self):
        if self.path == '/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            try:
                fresh_data = analytics.compute_analytics()
                self.wfile.write(json.dumps(fresh_data).encode('utf-8'))
            except Exception as e:
                err_response = {"error": str(e)}
                self.wfile.write(json.dumps(err_response).encode('utf-8'))
        else:
            self.send_error(404, "Not Found")


def run_server(port):
    socketserver.TCPServer.allow_reuse_address = True
    server_address = (config.SERVER_HOST, port)  # localhost only (security)
    try:
        with socketserver.TCPServer(server_address, TelemetryHandler) as httpd:
            print(f"[*] Live sync API server started at http://{config.SERVER_HOST}:{port}/data")
            httpd.serve_forever()
    except Exception as e:
        print(f"Error starting API server on port {port}: {e}", file=sys.stderr)


def find_free_port(start_port):
    import socket
    port = start_port
    while port < 6000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((config.SERVER_HOST, port))
                return port
            except OSError:
                port += 1
    return start_port


def generate_dashboard(watch_mode=False, server_port=5000):
    # Bootstrap the native DB (schema + optional legacy migration).
    migration.check_and_run_migrations()
    if not os.path.exists(config.DB_PATH):
        print(f"Error: TokStat database not found at {config.DB_PATH}")
        sys.exit(1)

    print(f"Reading TokStat telemetry database from {config.DB_PATH}...")
    report_data = analytics.compute_analytics()

    if not report_data:
        print("Warning: Database was successfully queried but returned 0 events.")
        # Create minimal empty report structure so dashboard doesn't crash
        report_data = {
            "global_overview": {
                "total_tokens": 0, "total_input": 0, "total_output": 0, "cached_tokens": 0,
                "cache_hit_pct": 0, "requests_count": 0, "sessions_count": 0,
                "active_repositories_count": 0, "active_models_count": 0, "active_tools_count": 0,
                "avg_context_size": 0, "avg_tokens_per_request": 0, "largest_request": None,
                "largest_session": None, "longest_session_duration": 0, "longest_session_id": "N/A",
                "peak_usage_day": "N/A", "peak_usage_tokens": 0, "estimated_cost": 0.0, "estimated_savings": 0.0
            },
            "repositories": [], "sessions": [], "events": [], "models": [], "tools": [],
            "time_analytics": {
                "daily_timeline": [], "weekday_heatmap": {}, "hourly_heatmap": {}, "weekday_totals": {},
                "monthly_trends": [], "busiest_coding_day": "N/A", "longest_uninterrupted_coding_session_sec": 0
            },
            "productivity_metrics": {
                "tokens_per_repository": {}, "tokens_per_request": 0, "tokens_per_session": 0,
                "output_input_ratio": 0, "cache_savings": 0, "context_utilisation": 0,
                "requests_per_hour": 0, "sessions_per_day": 0, "average_coding_session_length": 0
            },
            "git_integration": {"correlated_commits": [], "active_branches": {}, "repos_git_info": {}}
        }

    # Generate HTML in the primary + backwards-compatible paths
    output_paths = [config.DASHBOARD_PATH]
    if config.COMPAT_DASHBOARD_PATH != config.DASHBOARD_PATH:
        output_paths.append(config.COMPAT_DASHBOARD_PATH)

    for path in output_paths:
        try:
            renderer.generate_html_report(report_data, path, watch_mode=watch_mode)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace("__SERVER_PORT__", str(server_port))
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"Warning: Failed to process dashboard HTML at {path}: {e}")

    print(f"Success! Beautiful HTML dashboard generated at {config.DASHBOARD_PATH}")
    print("You can double-click this file or open it in your browser to view your local token statistics.")


def start_watch_mode(start_port):
    # 1. Determine a free port for the live sync API
    port = find_free_port(start_port)
    print(f"[*] Starting watch mode. Selected port {port} for live updates.")

    # 2. Write initial dashboard file
    generate_dashboard(watch_mode=True, server_port=port)

    # 3. Spin up API server in a background thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    # 4. Monitor the native database for updates in main thread
    last_mtime = 0
    if os.path.exists(config.DB_PATH):
        last_mtime = os.path.getmtime(config.DB_PATH)

    print("[*] Observatory is watching telemetry.db for updates... (Press Ctrl+C to quit)")
    try:
        while True:
            time.sleep(config.WATCH_POLL_INTERVAL_SEC)
            if os.path.exists(config.DB_PATH):
                current_mtime = os.path.getmtime(config.DB_PATH)
                if current_mtime != last_mtime:
                    print(f"\n[+] Telemetry database updated at {datetime.now().strftime('%H:%M:%S')}. Regenerating dashboard...")
                    try:
                        generate_dashboard(watch_mode=True, server_port=port)
                        last_mtime = current_mtime
                    except Exception as e:
                        print(f"Error during update regeneration: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\n[*] Exiting watch mode. Goodbye!")


def run_exports(export_dir):
    migration.check_and_run_migrations()
    if not os.path.exists(config.DB_PATH):
        print(f"Error: TokStat database not found at {config.DB_PATH}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(export_dir):
        try:
            os.makedirs(export_dir)
        except Exception as e:
            print(f"Error: Could not create export directory {export_dir}: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"[*] Running data exports to directory: {export_dir}")
    report_data = analytics.compute_analytics()

    if not report_data:
        print("Error: No data available to export.", file=sys.stderr)
        sys.exit(1)

    # Export formats
    exporter.export_json(report_data, os.path.join(export_dir, "observatory_report.json"))
    exporter.export_csv(report_data, export_dir)
    exporter.export_markdown(report_data, os.path.join(export_dir, "observatory_report.md"))
    exporter.export_pdf(report_data, os.path.join(export_dir, "observatory_report.pdf"))

    # Export copy of the dashboard HTML
    renderer.generate_html_report(
        report_data, os.path.join(export_dir, config.EXPORT_DASHBOARD_NAME), watch_mode=False
    )
    print(f"[+] All exports completed successfully in {export_dir}!")


# --- subcommands -----------------------------------------------------------
def cmd_daemon(action):
    from . import daemon
    if action == "start":
        daemon.start_daemon()
    elif action == "stop":
        daemon.stop_daemon()
    elif action == "status":
        print(json.dumps(daemon.daemon_status(), indent=2))


def cmd_migrate(force):
    result = migration.check_and_run_migrations(force=force, explicit=True)
    print(json.dumps(result, indent=2))


def cmd_collect(once):
    if not once:
        print("Only `tokstat collect --once` is supported for now.", file=sys.stderr)
        sys.exit(2)
    run_collectors_once()


def cmd_proxy(action, upstream=None, port=None, agent_name=None):
    from . import proxy

    if action == "start":
        proxy.start_proxy_daemon(upstream=upstream, port=port, agent_name=agent_name)
    elif action == "stop":
        proxy.stop_proxy_daemon()
    elif action == "status":
        print(json.dumps(proxy.proxy_daemon_status(), indent=2))


def cmd_sync(lookback_days=None):
    """One-shot authoritative provider usage sync (opt-in; never automatic)."""
    from . import sync

    result = sync.run_sync_once(lookback_days=lookback_days)
    print(json.dumps(result, indent=2))
    sys.exit(result.get("exit_code", 0))


def _open_dashboard(path):
    """Best-effort open of the generated dashboard in the default browser."""
    url = "file://" + os.path.abspath(path)
    try:
        opened = webbrowser.open(url)
        if opened:
            print(f"[*] Opened dashboard in your browser: {url}")
        else:
            print(f"[*] Dashboard ready at {url} - open it in your browser.")
    except Exception as e:
        print(f"[*] Dashboard ready at {url} (auto-open failed: {e})")


def cmd_full_pipeline(no_collect=False, no_open=False):
    """The default `tokstat` experience: migrate -> gather -> render -> open.

    Idempotent end to end: legacy import runs once, collectors dedupe via
    fingerprints, and the dashboard reflects the freshest data available.
    """
    # 1. Bootstrap the native DB (schema + optional read-only legacy import).
    #    Explicit here because the collectors below need the schema to exist;
    #    the render step re-checks it, which is idempotent and cheap.
    migration.check_and_run_migrations()

    # 2. Gather usage from every local source (Claude Code, Gemini, Aider,
    #    Copilot, Cursor, legacy OpenUsage/tokentop sync, ...). Collectors are
    #    individually fault-tolerant; the whole step is also guarded so a
    #    catastrophic failure can never block dashboard generation.
    if not no_collect:
        try:
            run_collectors_once()
        except Exception as e:
            print(f"Warning: usage gathering failed ({e}); rendering with existing data.", file=sys.stderr)

    # 3. Render the dashboard.
    generate_dashboard()

    # 4. Open it (unless suppressed).
    if not no_open:
        _open_dashboard(config.DASHBOARD_PATH)


def main():
    argv = sys.argv[1:]

    if argv and argv[0] == "daemon":
        parser = argparse.ArgumentParser(prog="tokstat daemon")
        parser.add_argument("action", choices=["start", "stop", "status"])
        args = parser.parse_args(argv[1:])
        cmd_daemon(args.action)
        return

    if argv and argv[0] == "migrate":
        parser = argparse.ArgumentParser(prog="tokstat migrate")
        parser.add_argument("--force", action="store_true", help="Re-run legacy import")
        args = parser.parse_args(argv[1:])
        cmd_migrate(args.force)
        return

    if argv and argv[0] == "collect":
        parser = argparse.ArgumentParser(prog="tokstat collect")
        parser.add_argument("--once", action="store_true", help="Run all collectors once")
        args = parser.parse_args(argv[1:])
        cmd_collect(args.once)
        return

    if argv and argv[0] == "proxy":
        parser = argparse.ArgumentParser(prog="tokstat proxy")
        parser.add_argument("action", choices=["start", "stop", "status"])
        parser.add_argument("--upstream", default=None, help="Upstream LLM server URL")
        parser.add_argument("--port", type=int, default=None, help="Proxy listen port")
        parser.add_argument("--agent-name", default=None, help="Telemetry agent_name")
        args = parser.parse_args(argv[1:])
        cmd_proxy(args.action, upstream=args.upstream, port=args.port, agent_name=args.agent_name)
        return

    if argv and argv[0] == "sync":
        parser = argparse.ArgumentParser(prog="tokstat sync")
        parser.add_argument(
            "--lookback-days", type=int, default=None,
            help="Provider history window in days (default: [sync] lookback_days, 365)",
        )
        args = parser.parse_args(argv[1:])
        cmd_sync(lookback_days=args.lookback_days)
        return

    parser = argparse.ArgumentParser(description="AI Engineering Observatory - Developer Token Tracker")
    parser.add_argument("--watch", action="store_true", help="Start watch mode with live updates")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the live update server on (default: 5000)")
    parser.add_argument("--export", type=str, help="Export CSV, JSON, Markdown, HTML and PDF reports to the specified folder path")
    parser.add_argument("--no-collect", action="store_true", help="Render the dashboard only, skipping the usage-gathering step")
    parser.add_argument("--no-open", action="store_true", help="Do not auto-open the dashboard in a browser")

    args = parser.parse_args(argv)

    if args.export:
        run_exports(args.export)
    elif args.watch:
        start_watch_mode(args.port)
    else:
        cmd_full_pipeline(no_collect=args.no_collect, no_open=args.no_open)


if __name__ == "__main__":
    main()
