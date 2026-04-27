# Watchdog delivery-proof hardening — P7 follow-up ralplan

Date: 2026-04-20
Status: reconstructed recovery package
Decision: narrow `morning-watchdog` duplicate suppression to authoritative observed delivery only.

## Source / review docs referenced

- `AGENTS.md`
- `docs/openclaw-runtime/contracts/finance-openclaw-runtime-contract.md`
- `docs/openclaw-runtime/contracts/finance-report-contract.md`
- `docs/openclaw-runtime/contracts/judgment-contract.md`
- review source noted by touched runtime files: `/Users/leofitz/Downloads/review 2026-04-18.md`

## Why this package

`morning-watchdog` was suppressing on either:

1. follow-up thread registry `updated_at`, or
2. observed delivered rows from parent cron history.

That over-credits the follow-up registry as delivery proof. Thread repair can mutate registry timestamps without any user-visible Discord delivery. The repo contract requires delivery safety to remain intact and disallows widening runtime authority or direct delivery retries from this finance repo.

## Decision

Use only parent-cron observed delivery evidence to suppress `morning-watchdog`.

Keep follow-up registry activity as warning-only metadata inside the audit artifact so operators can still see that thread state moved after cutoff, without treating that movement as proof of successful delivery.

## Alternatives rejected

### 1. Keep suppressing on any follow-up registry activity
Rejected because registry `updated_at` can move during thread repair and is not equivalent to delivered user-visible output.

### 2. Add a direct Discord retry path from finance
Rejected because it violates the delivery authority boundary owned by the parent OpenClaw runtime.

### 3. Broader cron/job rewrite
Rejected because the confirmed defect is narrower: proof of delivery was too permissive, and delivered recency could be trimmed in the wrong order.

## Invariants

- No direct Discord delivery authority added here.
- No validators, safety gates, or review-only boundaries are bypassed.
- No threshold mutation from LLM output.
- Market calendar/session behavior remains unchanged.
- Parent runtime remains the authority for observed delivery evidence.

## Failure modes addressed

- False watchdog suppression because follow-up registry activity is mistaken for delivery success.
- Same-day premarket delivered rows disappearing from `delivered_recent` when older delivered rows from later job buckets push them out before global time ordering.
- Confusing job/thread maintenance success with user-visible delivery success.

## Exact touch map

- `scripts/finance_discord_report_job.py`
  - record follow-up registry activity as warning-only metadata
  - suppress watchdog only on `observed_delivered_since(...)`
- `scripts/finance_delivery_observed_audit.py`
  - globally sort delivered rows by timestamp before trimming `delivered_recent`
- `tests/test_finance_discord_report_job_p7_delivery_audit.py`
  - cover registry-activity-without-delivery regression
- `tests/test_finance_delivery_observed_audit_p7.py`
  - cover multi-job delivered ordering regression
- `docs/openclaw-runtime/critics/watchdog-delivery-proof-hardening-p7-followup-critic.md`
  - critic pass result

## Test plan

Focused:

- `python3 -m pytest -q tests/test_finance_delivery_observed_audit_p7.py tests/test_finance_discord_report_job_p7_delivery_audit.py`

Broader repo validation expected by workspace when applied in the real repo:

- `python3 -m pytest -q tests`
- `python3 -m compileall -q scripts tools tests`
- `python3 tools/audit_operating_model.py`
- `python3 tools/audit_benchmark_boundary.py`

## No-go items

- No new product direction.
- No runtime authority changes.
- No direct broker execution.
- No hidden source quota failure handling changes.
- No calendar/session contract rewrite.
- No parent-runtime file edits in this package.

## Rollback path

Revert the touched files in one commit. No state migration is required. The package is small and reversible.
