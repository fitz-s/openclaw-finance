# RALPLAN P4: Fixed Marketday Core Review

Status: approved_for_p4_implementation
Mode: consensus_planning
Scope: fixed second core report / timeliness policy

## Source Review And Explorer Inputs

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Phase explorer inputs:

- Internal explorer: `docs/openclaw-runtime/scouts/marketday-core-review-p4-internal-explorer.md`
- External scout: `docs/openclaw-runtime/scouts/marketday-core-review-p4-external-scout.md`

## Task Statement

Ensure each trading day has a fixed second proactive core review attempt before late afternoon, without relying solely on threshold wakes and without repeating the heavy live source-acquisition path that caused midday timeout.

## RALPLAN-DR

### Principles

1. Fixed report attempt complements thresholds; it does not replace wake policy.
2. The fixed second report must use existing validator/log/safety delivery chain.
3. Timeliness beats source re-crawling in the second core review; scanners already own source acquisition.
4. No Discord delivery topology change.
5. Parent runtime changes must be mirrored for reviewers.

### Decision Drivers

1. User observed a trading day with no timely proactive report until late afternoon.
2. `finance-midday-operator-review` has timeout history.
3. `finance_discord_report_job.py --mode marketday-review` currently runs heavy live parent ingest/source activation.

### ADR

Decision: Add `marketday-core-review` mode to `finance_discord_report_job.py`. It uses a fast deterministic report path that skips live parent ingest/source activation but preserves price/macro/options refresh, JudgmentEnvelope fallback, renderer, validator, decision log, delivery safety, reader bundle, cache, board package, and archive/cutover checks. Patch `finance-midday-operator-review` to run this mode at 13:15 CT weekdays.

Rejected: Add another threshold-only wake | does not guarantee a report attempt.
Rejected: Keep midday job on heavy marketday-review mode | repeats timeout failure mode.
Rejected: Add a new Discord delivery channel/job | unnecessary topology expansion.

## Implementation Plan

1. Add `marketday-core-review` mode to `finance_discord_report_job.py`.
2. Add fast-core path metadata in `state/marketday-core-review-policy.json`.
3. Patch existing `finance-midday-operator-review` cron to `15 13 * * 1-5` and `--mode marketday-core-review`.
4. Export parent runtime mirror and snapshot.
5. Add tests for fast path, mode parsing, patch behavior, prompt contract, and snapshot.

## No-Go Items

- No delivery channel changes.
- No safety bypass.
- No wake threshold lowering.
- No broker/execution authority.
