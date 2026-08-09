# TokStat — AI Engineering Observatory & Token Tracker

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**TokStat is a local-first, self-contained observatory that tracks your AI developer token usage — calculated on your machine, by your machine.**

It collects telemetry directly from the AI tools you run (Claude Code, Gemini
Antigravity, Aider, Copilot, Cursor/VS Code via the ingestion endpoint), stores
it in its own database (`~/.tokstat/telemetry.db`, WAL mode), and renders a
rich interactive dashboard. **No external daemons required.** Legacy
[OpenUsage](https://github.com/janekbaraniewski/openusage) and
[tokentop](https://github.com/tokentopapp/tokentop) databases are optional
augmentary sources that TokStat imports read-only — never a dependency.

## Dashboard Preview

![TokStat Overview Dashboard](docs/assets/dashboard_overview.png)
![TokStat Time & Heatmaps](docs/assets/dashboard_heatmaps.png)

## Features

- **Autonomous collection** — embedded scrapers poll local tool data
  (Claude Code JSONL transcripts, Aider model stats, Gemini brain logs,
  Copilot session store) and an HTTP ingestion server (`/v1/events`) accepts
  events from IDE extensions, shell wrappers and proxies.
- **Provider reconciliation** — opt-in `tokstat sync` pulls authoritative
  all-time usage/cost totals from Anthropic and OpenAI (Codex), reconciles
  them with the local event log, and surfaces the coverage gap in the
  dashboard and exports. **Never runs automatically.**
- **Native storage** — `~/.tokstat/telemetry.db` (SQLite, WAL mode) with an
  OpenUsage-compatible schema; time-window fingerprint dedup keeps events
  merge-safe across sources.
- **Zero-loss migration** — `tokstat migrate` imports existing OpenUsage and
  tokentop history read-only (originals untouched).
- **Honest numbers** — events are flagged `ok` (real usage) or `estimated`
  (deterministic estimates from content length — never fabricated).
- **Interactive dashboard** — self-contained HTML with Chart.js, model/tool
  filtering, git-commit correlation, heatmaps and keyboard shortcuts.
- **Native daemon** — `tokstat daemon start|stop|status` runs collectors +
  ingestion server in the background; `--watch` gives live browser updates.
- **Exports** — PDF, JSON, Markdown and CSV reports.
- **Local model support** — a stdlib-only transparent proxy
  (`tokstat proxy start`) sits in front of Ollama / llama.cpp / vLLM / LM
  Studio and records **real token usage** from their responses, with
  `cost_usd = 0.0` and a **Cloud Cost Avoidance** estimate of what those
  tokens would have cost via an API. Point any OpenAI-compatible or
  Ollama-native client at `http://127.0.0.1:11435` and telemetry is captured
  automatically.

## Installation

The PyPI distribution is named **`tokstat-observatory`** (the console command
remains `tokstat`).

```bash
pip install tokstat-observatory        # or: uv tool install tokstat-observatory
```

From source:

```bash
git clone https://github.com/sanjeevafk/tokstat.git
cd tokstat
uv pip install -e ".[dev]"   # or: make dev
```

## Quick Start

**One command does everything.** Running `tokstat` (or `make run`) gathers
fresh usage from every local source, generates the dashboard and opens it in
your browser:

```bash
tokstat
```

Under the hood the bare command runs an idempotent pipeline:

1. **Migrate** — optional read-only import of existing OpenUsage/tokentop
   history (skipped once already imported).
2. **Collect** — gather telemetry from all local sources (Claude Code JSONL,
   Gemini Antigravity brain logs, Aider stats, Copilot store, Cursor,
   legacy OpenUsage/tokentop sync).
3. **Render** — write `tokstat_dashboard.html` and open it.

Flags for fine control:

```bash
tokstat --no-collect   # render only, skip the gathering step
tokstat --no-open     # don't auto-open the browser
```

More granular commands:

```bash
# Collect telemetry once from all local sources.
tokstat collect --once

# (Optional) Import existing OpenUsage / tokentop history - read-only.
tokstat migrate

# Run the background daemon: collectors + ingestion server.
tokstat daemon start
tokstat daemon status
tokstat daemon stop

# Local model proxy: capture usage from Ollama / llama.cpp / vLLM / LM Studio.
tokstat proxy start                # default upstream http://localhost:11434
tokstat proxy start --upstream http://localhost:8080 --port 11435
# Point your OpenAI-compatible client (or OLLAMA_HOST) at http://127.0.0.1:11435
# and real token usage flows into the dashboard automatically.
tokstat proxy status
tokstat proxy stop

# Or run the proxy inside the daemon: enable `[proxy]` in ~/.tokstat/config.toml
# (see the config example below), then `tokstat daemon start` runs both.

# Point Codex CLI at the proxy too: it honors a custom base URL.
export OPENAI_BASE_URL=http://127.0.0.1:11435   # real per-turn usage, recorded

# Opt-in authoritative provider totals (never automatic):
tokstat sync                 # pull all-time usage/cost from Anthropic + OpenAI
tokstat sync --lookback-days 90

# Live watch mode with browser updates:
tokstat --watch --port 5000

# Structured exports:
tokstat --export ./reports
```

Common workflows via `make` (`make help` lists all targets):

```bash
make run             # same as `tokstat` - gather + render + open
make test            # run the test suite
make lint            # ruff check
make check           # lint + test (CI gate)
make build           # sdist + wheel into dist/
make release-check   # build + twine check
```

### Supported data sources

| Source | Token data | Flags |
| :--- | :--- | :--- |
| Claude Code (`~/.claude/projects/*.jsonl`) | Real (`message.usage`) | `ok` |
| Aider (`.aider.model.stats.json`) | Real | `ok` |
| Gemini Antigravity (brain `overview.txt`) | Estimated (content length) | `estimated` |
| GitHub Copilot (`~/.copilot/session-store.db`) | Estimated (char-length heuristic) | `estimated` |
| Cursor / VS Code (`state.vscdb`) | Usually none exposed | — use ingestion endpoint |
| Custom hooks / proxies | Real | `POST /v1/events` |
| Ollama / llama.cpp / vLLM / LM Studio (via proxy) | Real (`usage` / `prompt_eval_count`) | `ok` |
| Remote GPU (SSH tunnel or direct https + proxy) | Real | `ok` |
| OpenUsage / tokentop DBs (optional) | Imported history + balance snapshots | read-only |

The dashboard marks estimated events so you always know which numbers are
measurements and which are approximations.

### Local model configuration (`~/.tokstat/config.toml`)

Optional; TokStat works with zero configuration. When present, it is merged
over defaults (environment variables still win):

```toml
[proxy]
enabled = false            # set true to run the proxy inside `tokstat daemon`
upstream = "http://localhost:11434"   # Ollama default; any OpenAI-compat / Ollama server
listen_port = 11435
agent_name = "ollama_proxy"
provider_id = "local"

# Optional: approximate cloud-equivalent pricing overrides (per 1M tokens).
# Glob patterns override the built-in LOCAL_TO_CLOUD_MAP for the
# Cloud Cost Avoidance estimate.
[pricing.overrides]
"llama*" = [0.0, 0.0]
"qwen*" = [0.10, 0.40]
```

### Self-reliant vs. augmentary mode

By default TokStat syncs OpenUsage/tokentop databases **if they exist**
(augmentary: richer data, including all-time provider totals). Set
`TOKSTAT_SYNC_LEGACY=0` for pure self-reliant mode:

```bash
TOKSTAT_SYNC_LEGACY=0 tokstat
```

`tokstat migrate` is an explicit command and always imports, regardless of the
flag.

### Authoritative provider sync (optional, opt-in)

TokStat stays **local-first by default: the bare `tokstat` command and the
daemon never make outbound calls.** `tokstat sync` is an explicit, opt-in way
to close the accuracy gap for tools whose local logs TokStat can only estimate
(Gemini, Copilot): it pulls **authoritative all-time totals** from the
providers' usage APIs and reconciles them against the local event log
(visible as the Provider Reported / Local Event Log / Not in Event Log scope
card, plus a Provider Reconciliation section in exports).

- Credentials are **discovered from existing local config only** —
  `ANTHROPIC_ADMIN_KEY`/`ANTHROPIC_API_KEY` (env or `~/.claude/settings.json`)
  and `OPENAI_API_KEY` / `~/.codex/auth.json` (OAuth tokens are refreshed
  automatically when expired). Nothing is stored outside `~/.tokstat`.
- A provider failure is isolated and reported; other providers still sync.
- **Google Gemini** has no API-key usage endpoint (usage is exposed only via
  Google Cloud Billing / Vertex), so it is skipped with a documented reason.
- To run it on an interval inside the daemon, set `[sync] enabled = true`
  below; the daemon then syncs at most every `interval_hours`.

```toml
[sync]
enabled = false        # true => the daemon runs `tokstat sync` on an interval
lookback_days = 365    # provider history window
interval_hours = 6.0   # minimum time between daemon-triggered syncs
```

## Privacy

- **Everything stays on your machine.** TokStat reads local tool data, stores
  it in `~/.tokstat/`, and serves dashboards on `127.0.0.1` only.
- Nothing is uploaded. The ingestion server binds localhost by design.
- Optional future provider polling would require *your* API keys and never
  happens implicitly.

## Python API

```python
from tokstat import analytics, exporter, renderer

data = analytics.compute_analytics()
renderer.generate_html_report(data, "dashboard.html")
exporter.export_json(data, "report.json")
```

## Project Structure

```
tokstat/
├── src/tokstat/
│   ├── cli.py             # CLI entrypoint (tokstat command)
│   ├── config.py          # Centralized paths, env switches, WAL connections
│   ├── migration.py       # Native schema + read-only legacy import
│   ├── server.py          # HTTP ingestion server (/v1/events, /health)
│   ├── daemon.py          # Background daemon (collectors + ingestion)
│   ├── collectors/        # Embedded scrapers (claude_code, aider, gemini,
│   │                      #  copilot, cursor, legacy_sync)
│   ├── db_access.py       # Native DB reads (queries, balance observations)
│   ├── queries.py         # Optimized SQL telemetry queries
│   ├── analytics.py       # Analytical calculations & git correlation
│   ├── renderer.py        # HTML dashboard generator
│   ├── exporter.py        # PDF / CSV / JSON / Markdown exporters
│   └── utils.py           # Cost estimation & git metadata utils
├── tests/                 # Unit and integration test suite
├── docs/                  # Architecture + implementation plan
├── pyproject.toml         # Hatchling build (dist: tokstat-observatory)
├── Makefile               # Dev/build/release workflows (make help)
├── ACKNOWLEDGEMENTS.md    # Schema/wire-format credits
└── LICENSE                # MIT License
```

## Documentation

- [Architecture & technical reference](docs/observatory_architecture.md)

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
