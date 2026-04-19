# RALPLAN P7: Observed Delivery Audit And Watchdog Suppression

Status: approved_for_p7_implementation
Mode: consensus_planning
Scope: delivery observed-success audit and morning watchdog suppression

## Source Review And Explorer Inputs

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Phase explorer inputs:

- Internal explorer: `docs/openclaw-runtime/scouts/delivery-observed-audit-p7-internal-explorer.md`
- External scout: `docs/openclaw-runtime/scouts/delivery-observed-audit-p7-external-scout.md`

## Task Statement

Make finance distinguish report generation from observed Discord delivery. The morning delivery watchdog should suppress itself only when a real delivered report is observed or thread registry proves delivery, not merely because a report job ran.

## RALPLAN-DR

### Principles

1. Observed delivery beats scheduled intent.
2. Finance remains read-only; OpenClaw parent still owns Discord send.
3. Watchdog should retry when delivery did not happen, but avoid spam when delivery is observed.
4. Reviewer snapshots must expose delivery evidence.

### ADR

Decision: Add `finance_delivery_observed_audit.py` to read parent cron run JSONL files and classify recent delivered/not-delivered/error runs. Integrate it into `finance_discord_report_job.py` for `morning-watchdog` duplicate suppression.

Rejected: Treat any successful report job as delivered | current run history shows `status=ok` can still be `deliveryStatus=not-delivered`.
Rejected: Send directly from finance repo | violates parent OpenClaw delivery boundary.

## Test Plan

- audit detects delivered runs after cutoff.
- audit detects ok-but-not-delivered as missing observed delivery.
- morning watchdog returns `NO_REPLY` when observed delivery exists.
- morning watchdog runs when no observed delivery exists and thread registry is empty.
- snapshot exports delivery observed audit.

## No-Go Items

- No Discord direct send.
- No delivery topology mutation.
- No wake threshold mutation.
- No broker/execution authority.
