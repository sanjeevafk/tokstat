# visualize_usage.py
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import time
from datetime import datetime

# Import refactored modules
from . import analytics, exporter, renderer

# Default Paths
DB_PATH = os.path.expanduser("~/.local/state/openusage/telemetry.db")
# Write beside the command invocation so the reported path is the dashboard the
# user can actually open, rather than an implementation file inside the package.
OUTPUT_PATH = os.path.abspath("openusage_dashboard.html")

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
    server_address = ("", port)
    try:
        with socketserver.TCPServer(server_address, TelemetryHandler) as httpd:
            print(f"[*] Live sync API server started at http://localhost:{port}/data")
            httpd.serve_forever()
    except Exception as e:
        print(f"Error starting API server on port {port}: {e}", file=sys.stderr)

def find_free_port(start_port):
    import socket
    port = start_port
    while port < 6000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                port += 1
    return start_port

def generate_dashboard(watch_mode=False, server_port=5000):
    if not os.path.exists(DB_PATH):
        print(f"Error: OpenUsage database not found at {DB_PATH}")
        sys.exit(1)

    print(f"Reading OpenUsage telemetry database from {DB_PATH}...")
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

    # Generate HTML content in both directories
    renderer.generate_html_report(report_data, OUTPUT_PATH, watch_mode=watch_mode)
    alternate_path = os.path.expanduser("~/Downloads/openusage_dashboard.html")
    
    # Post-process generated HTML to inject selected port
    for path in {OUTPUT_PATH, alternate_path}:
        try:
            if path == alternate_path and path != OUTPUT_PATH:
                renderer.generate_html_report(report_data, path, watch_mode=watch_mode)
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace("__SERVER_PORT__", str(server_port))
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"Warning: Failed to process dashboard HTML at {path}: {e}")

    print(f"Success! Beautiful HTML dashboard generated at {OUTPUT_PATH}")
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

    # 4. Monitor database for updates in main thread
    last_mtime = 0
    if os.path.exists(DB_PATH):
        last_mtime = os.path.getmtime(DB_PATH)

    print("[*] Observatory is watching telemetry.db for updates... (Press Ctrl+C to quit)")
    try:
        while True:
            time.sleep(3)
            if os.path.exists(DB_PATH):
                current_mtime = os.path.getmtime(DB_PATH)
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
    if not os.path.exists(DB_PATH):
        print(f"Error: OpenUsage database not found at {DB_PATH}", file=sys.stderr)
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
    renderer.generate_html_report(report_data, os.path.join(export_dir, "observatory_dashboard.html"), watch_mode=False)
    print(f"[+] All exports completed successfully in {export_dir}!")

def main():
    parser = argparse.ArgumentParser(description="AI Engineering Observatory - Developer Token Tracker")
    parser.add_argument("--watch", action="store_true", help="Start watch mode with live updates")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the live update server on (default: 5000)")
    parser.add_argument("--export", type=str, help="Export CSV, JSON, Markdown, HTML and PDF reports to the specified folder path")
    
    args = parser.parse_args()

    if args.export:
        run_exports(args.export)
    elif args.watch:
        start_watch_mode(args.port)
    else:
        generate_dashboard()

if __name__ == "__main__":
    main()
