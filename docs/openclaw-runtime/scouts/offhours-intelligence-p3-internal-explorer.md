# Offhours Intelligence P3 Internal Explorer

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

The internal explorer mapped the active runtime:

- Live OpenClaw cron config is `/Users/leofitz/.openclaw/cron/jobs.json`.
- `finance-subagent-scanner-offhours` currently runs `0 0,4,7,17,20 * * 1-5` America/Chicago.
- The job has `delivery.mode=none` and calls `finance_scanner_job.py --mode offhours-scan`.
- `finance_scanner_job.py` already routes offhours through router, QueryPack, Brave activation, compression activation, parent ingest, and gate evaluator.
- P3 must not lower thresholds or change Discord delivery.

Recommended P3:

- Add `offhours_cadence_governor.py`.
- Wire it after `offhours_source_router.py` and before expensive scanner work.
- If governor skips, print one machine line and do not run source activation.
- Patch only the offhours cron day-of-week field from `1-5` to `*`.
- Mirror parent runtime snapshots after patching.
