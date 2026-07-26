# TokStat - AI Engineering Observatory and Token Tracker

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

TokStat is a local, modular telemetry dashboard and analytics utility for monitoring AI developer token usage across different developer environments, models, and tools. It integrates inputs from OpenUsage database records, tokentop databases, and GitHub Copilot to build a unified view of your developer token economy.

## Features

- **Unified Telemetry Merger:** Automatically merges and de-duplicates telemetry events from OpenUsage and tokentop database streams using time-window fingerprint comparison.
- **Interactive Web Dashboard:** Generates a self-contained HTML visualizer containing detailed analytics for model distribution, token consumption trends, and tool usage.
- **Git Integration:** Correlates local repository commit logs with token usage windows to calculate the token cost and context utilization of individual commits.
- **Real-Time Watcher:** Includes an active polling server mode that watches local telemetry databases for modifications and updates the browser view dynamically.
- **Multiple Export Formats:** Generates structured reports in PDF, JSON, Markdown, and CSV format.

## Installation

### Using `uv` (Recommended)

Install globally as a CLI tool:
```bash
uv tool install tokstat
```

Or install in a Python environment:
```bash
uv pip install tokstat
```

### Using `pip`

```bash
pip install tokstat
```

### From Source (Development)

```bash
git clone https://github.com/sanjeevafk/tokstat.git
cd tokstat
uv pip install -e ".[dev]"
```

## Quick Start

### CLI Options

Generate the HTML dashboard report (`openusage_dashboard.html`):
```bash
tokstat
```

Start interactive watch mode with live browser updates:
```bash
tokstat --watch --port 5000
```

Export structured reports (CSV, JSON, Markdown, PDF) to a directory:
```bash
tokstat --export ./reports
```

### Python API Usage

```python
from tokstat import analytics, exporter, renderer

# Compute aggregated telemetry analytics
data = analytics.compute_analytics()

# Render HTML dashboard
renderer.generate_html_report(data, "dashboard.html")

# Export to JSON / Markdown / PDF
exporter.export_json(data, "report.json")
exporter.export_markdown(data, "report.md")
exporter.export_pdf(data, "report.pdf")
```

## Project Structure

```
tokstat/
├── src/tokstat/           # Core library package
│   ├── __init__.py
│   ├── cli.py             # CLI entrypoint (tokstat command)
│   ├── db_access.py       # Database connection & query sanitization
│   ├── queries.py          # Optimized SQL telemetry queries
│   ├── analytics.py       # Analytical calculations & Git alignments
│   ├── renderer.py        # HTML/CSS dashboard report generator
│   ├── exporter.py        # PDF, CSV, JSON, Markdown exporters
│   └── utils.py           # Cost estimation & git metadata utils
├── tests/                 # Unit and integration test suite
├── .github/workflows/    # GitHub Actions CI workflow
├── pyproject.toml         # Hatchling build specification & dependencies
├── LICENSE                # MIT License
└── README.md
```

## License

Distributed under the MIT License. See [LICENSE](file:///home/sanjeev/Downloads/token-tracker/LICENSE) for details.
