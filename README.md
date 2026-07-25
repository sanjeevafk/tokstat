# TokStat - AI Engineering Observatory and Token Tracker

TokStat is a local, modular telemetry dashboard and analytics utility for monitoring AI developer token usage across different developer environments, models, and tools. It integrates inputs from OpenUsage database records, tokentop databases, and GitHub Copilot to build a unified view of your developer token economy.

## Features

- Unified Telemetry Merger: Automatically merges and de-duplicates telemetry events from OpenUsage and tokentop database streams using a time-window fingerprint comparison.
- Interactive Web Dashboard: Generates a self-contained HTML visualizer containing detailed analytics for model distribution, token consumption trends, and tool usage.
- Git Integration: Correlates your local repository commit logs with token usage windows to calculate the token cost and context utilization of individual commits.
- Real-Time Watcher: Includes an active polling server mode that watches local telemetry databases for modifications and updates the browser view dynamically.
- Multiple Export Formats: Exporters generate structured reports in PDF, JSON, Markdown, and CSV format.

## Structure

- visualize_usage.py: The main executable and CLI interface.
- db_access.py: Database connection layer that handles querying, sanitizing, and merging database logs.
- queries.py: Standard SQL queries optimized for token telemetry.
- analytics.py: Analytical calculations for session gaps, timelines, heatmaps, and Git commit alignments.
- renderer.py: Generates the HTML and CSS template for the interactive visualizer.
- exporter.py: Formats and prints telemetry reports.
- utils.py: Estimates token costs/savings and resolves local Git repository metadata.

## Getting Started

### CLI Options

Generate the dashboard report:
```bash
python3 visualize_usage.py
```

Start the interactive watcher for live dashboard updates:
```bash
python3 visualize_usage.py --watch
```

Export structured reports to a directory:
```bash
python3 visualize_usage.py --export /path/to/export_dir
```

## System Requirements

- Python 3.x
- SQLite3
