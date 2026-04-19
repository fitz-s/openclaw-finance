# Offhours Intelligence P1 Internal Explorer

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Explorer Notes

Spark `explore` was unavailable due usage limits, so a frontier `analyst` was used as the internal explorer fallback. No files were edited by the explorer.

## Current Active Flow

Active cron path via `scripts/finance_scanner_job.py` currently runs the same chain for `market-hours-scan` and `offhours-scan`:

```text
finance_llm_context_pack.py
-> query_pack_planner.py
-> finance_worker.py
-> finance_parent_market_ingest_cutover.py
-> gate_evaluator.py
```

The `--mode` flag is mostly metadata today. It does not make offhours scans calendar-aware.

## Key Touchpoints

- `scripts/finance_scanner_job.py`: insert offhours router only for `offhours-scan`, keep market-hours unchanged.
- `scripts/query_pack_planner.py`: attach `session_aperture` and `budget_request` to QueryPacks when scanner mode is offhours.
- `scripts/finance_parent_market_ingest_cutover.py`: pass scanner mode through to QueryPack planner and source activation.
- `scripts/brave_source_activation.py`: enforce budget decisions before live Brave fetches and emit blocked rows instead of silent skips.
- `scripts/source_health_monitor.py`: expose budget/aperture state as observability only; no wake authority.
- `scripts/native_scanner_offhours.py`: add aperture metadata to native offhours report while retaining legacy `window` compatibility.

## Hazards

- Do not let stale `state/session-aperture-state.json` affect market-hours QueryPacks.
- Avoid double-counting budget because `query_pack_planner.py` runs both directly and inside parent cutover.
- Keep Brave Answers sidecar-only.
- Do not lower wake thresholds or change Discord delivery in P1.
- Do not mutate cron cadence in P1; all-days cadence is later.
