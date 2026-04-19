# RALPLAN P3: All-Days Offhours Cadence Governor

Status: approved_for_p3_implementation
Mode: consensus_planning
Scope: cadence governor plus conservative all-days offhours cron patch

## Source Review And Explorer Inputs

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Phase explorer inputs:

- Internal explorer: `docs/openclaw-runtime/scouts/offhours-intelligence-p3-internal-explorer.md`
- External scout: `docs/openclaw-runtime/scouts/offhours-intelligence-p3-external-scout.md`

## Task Statement

Activate weekend/holiday visibility without creating message storms or quota burn. Add a deterministic offhours cadence governor, wire it into the offhours scanner entrypoint, and patch the active OpenClaw offhours cron from weekdays-only to all-days at the existing conservative five-window cadence.

## RALPLAN-DR

### Principles

1. Governor before broader cadence.
2. Increase coverage, not frequency: change `1-5` to `*`, do not add more run times.
3. Scanner delivery remains none; report delivery and wake thresholds are untouched.
4. Budget exhaustion must skip expensive source activation before it starts.
5. Parent cron changes must be mirrored into reviewer-visible docs.

### Decision Drivers

1. Weekends and holidays are currently modeled but not scheduled.
2. Existing offhours scanner can timeout or burn Brave budget if run blindly.
3. P1/P2 now expose router, budget, and compression guardrails.

### ADR

Decision: Add `offhours_cadence_governor.py`, wire it into `finance_scanner_job.py --mode offhours-scan`, and patch `finance-subagent-scanner-offhours` schedule from `0 0,4,7,17,20 * * 1-5` to `0 0,4,7,17,20 * * *`.

Rejected: hourly all-days cadence | too much blast radius while Brave is rate-limited.
Rejected: cron patch without governor | would repeat the old quota/message storm failure mode.

## Implementation Plan

1. Add `scripts/offhours_cadence_governor.py`.
2. Wire governor into `scripts/finance_scanner_job.py` for offhours only.
3. Add `tools/patch_finance_offhours_cron_p3.py`.
4. Patch active parent cron jobs.json.
5. Export parent runtime mirror and finance runtime snapshot.
6. Add tests and critic artifact.

## Test Plan

- `test_governor_skips_rth`
- `test_governor_allows_weekend_under_budget`
- `test_governor_blocks_budget_exhausted`
- `test_finance_scanner_job_offhours_skip_is_single_machine_line`
- `test_patch_finance_offhours_cron_p3_all_days_no_delivery`
- `test_snapshot_exports_offhours_cadence_governor_state`

## No-Go Items

- No Discord delivery mutation.
- No wake threshold lowering.
- No compression live default.
- No broker/execution authority.
