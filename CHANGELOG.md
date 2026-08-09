# Changelog

All notable changes to **tokstat-observatory** (CLI: `tokstat`) are documented
here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-08-09

### Added

- **Local model support** — stdlib-only transparent proxy
  (`tokstat proxy start|stop|status`, or inside the daemon via `[proxy]
  enabled = true`) forwards OpenAI-compatible and Ollama-native requests to
  Ollama / llama.cpp / vLLM / LM Studio and captures **real token usage** from
  their responses, including SSE streaming (final-chunk `usage` or
  `prompt_eval_count`/`eval_count`).
- **Honest local cost model** — local events are recorded with
  `provider_id="local"` and `cost_usd = 0.0`; a **Cloud Cost Avoidance**
  estimate (via `utils.LOCAL_TO_CLOUD_MAP`, overridable with
  `[pricing.overrides]` in config.toml) shows what those tokens would have
  cost through an API.
- **Config file** — optional `~/.tokstat/config.toml` (stdlib `tomllib` on
  Python 3.11+, bundled mini-parser on 3.9/3.10) with proxy and pricing
  overrides; env vars still win.
- **Dashboard & exports** — Cloud Cost Avoidance card, Local vs Cloud donut,
  local model breakdown, Provider filter (All/Cloud/Local), Local Inference
  sections in Markdown/PDF and `local_models.csv`.
- **Provider-aware analytics** — `provider_id` is now used in aggregation
  (`global_overview.local_inference`) and displayed per event.

### Fixed

- Local events no longer get charged fabricated fallback cloud pricing
  (`$2/$6 per 1M tokens`).

## [0.2.0] - 2026-08-06

### Added

- **Self-contained telemetry** — TokStat now collects, stores and renders all
  usage data on its own: native SQLite database (`~/.tokstat/telemetry.db`,
  WAL mode) plus embedded collectors for Claude Code (real usage), Gemini
  Antigravity (deterministic content-length estimates, flagged `estimated`),
  Aider, GitHub Copilot and Cursor/VS Code. Works with **zero external
  daemons**.
- **One-command pipeline** — bare `tokstat` (or `make run`) bootstraps the DB,
  gathers usage from every source, renders `tokstat_dashboard.html` and opens
  it in the browser. New flags: `--no-collect`, `--no-open`.
- **HTTP ingestion server** — `POST /v1/events` (single/batch),
  `POST /v1/telemetry` and `GET /health` on `127.0.0.1`, with a single
  batching writer (1s / 50-event flush).
- **Background daemon** — `tokstat daemon start|stop|status` runs collectors +
  ingestion server with PID lifecycle and graceful shutdown.
- **CLI subcommands** — `tokstat migrate` (read-only OpenUsage/Tokentop import
  with cross-source fingerprint dedup) and `tokstat collect --once`.
- **Makefile** — `make run/test/lint/check/build/release-check/publish/...`
  developer and release workflows.
- `ACKNOWLEDGEMENTS.md`, `CHANGELOG.md`, rewritten README and architecture
  docs.

### Changed

- Distribution renamed to **`tokstat-observatory`** (v0.2.0; console command
  stays `tokstat`).
- Dashboard and exports rebranded to TokStat; per-event cache savings now use
  model-aware pricing consistently across KPI cards, tables and exports.
- Dashboard and watch/ingestion servers bind to `127.0.0.1` only.
- All paths centralized in `src/tokstat/config.py` with `TOKSTAT_DIR` and
  `TOKSTAT_SYNC_LEGACY` switches.

### Fixed

- Batching writer now flushes on the 1-second tick (rows were only persisted on
  daemon shutdown).
- Migration records are committed — previously a full 100K-row re-import ran on
  every CLI invocation.
- Ingestion handler returns a clean 400 for malformed payloads (e.g. invalid
  `cost_usd`) instead of crashing the request thread.
- Legacy DB paths resolved at call time (testable, patchable).

### Removed

- `backfill_ide_data.py` — fabricated random token counts with `random.*`;
  superseded by the deterministic `estimated` Gemini Antigravity collector.

[0.2.0]: https://github.com/sanjeevafk/tokstat/releases/tag/v0.2.0
