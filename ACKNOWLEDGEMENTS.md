# Acknowledgements

TokStat is an independent, self-contained telemetry observatory. It is built on
the shoulders of several excellent open-source projects:

## Data format compatibility

- **[OpenUsage](https://github.com/janekbaraniewski/openusage) (MIT)** — TokStat's
  native `usage_events` / `usage_raw_events` / `balance_observations` schema and
  the `/v1/events` ingestion wire format are OpenUsage-compatible so that data
  from OpenUsage-based integrations can be imported or re-pointed at TokStat.
  OpenUsage remains an **optional, augmentary** source: when its local database
  is present, TokStat syncs it read-only; TokStat works fully without it.
- **[tokentop](https://github.com/tokentopapp/tokentop) (MIT)** — TokStat reads
  and migrates tokentop's `usage.db` (also optional / augmentary) and reuses its
  per-event shape for cross-source deduplication.

## Runtime dependencies

- **fpdf2 (LGPL-3.0)** — used only for PDF report export. It is declared as a
  normal dependency in `pyproject.toml` (dynamic linking) and is never vendored.

## Inspiration

- **GitHub Copilot** telemetry estimation heuristics (character-length based)
  follow widely-used community approaches; Copilot counts are estimates only.

If you believe an attribution is missing, please open an issue.
