# Marketday Core Review P4 Internal Explorer

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Internal finding:

- `finance-midday-operator-review` exists and announces to Discord, but its recent runtime state shows timeout.
- Current report job mode is the same heavy `marketday-review` path as premarket.
- `finance_discord_report_job.py` runs live parent ingest/source activation before rendering, which is unnecessary for a fixed second core report because scanners already collect state.
- The safe fix is a fast deterministic second-core mode that refreshes price/macro/options shadow context, then renders through the same validator/log/safety path.

P4 touchpoints:

- `scripts/finance_discord_report_job.py`
- active `/Users/leofitz/.openclaw/cron/jobs.json` job `finance-midday-operator-review`
- `tools/export_parent_runtime_mirror.py`
- `tools/export_openclaw_runtime_snapshot.py`
- tests for prompt contract and patch behavior.
