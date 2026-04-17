# RALPLAN Source-to-Campaign Phase 14: Monitoring, Rollback Hardening, And Closeout

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Close the Source-to-Campaign campaign by exporting a reviewer-visible monitoring and closeout report with key metrics, gate status, rollback posture, and remaining blockers.

## Principles

1. Closeout is evidence, not celebration.
2. Monitoring must include source, evidence, campaign, follow-up, IV, thread lifecycle, reviewer export, and cutover readiness metrics.
3. Rollback must remain explicit.
4. No active runtime behavior changes.

## Selected Plan

Add `tools/export_source_to_campaign_closeout.py` producing `docs/openclaw-runtime/source-to-campaign-closeout.json` and tests.

## Acceptance Criteria

- Closeout JSON includes requested metrics and phase completion summary.
- Closeout reads current gate and reports hold/ready status.
- Raw snippet export count is measured from reviewer packets.
- Manifest references closeout.

## Test Plan

- `test_closeout_report_computes_monitoring_metrics`
- full tests

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-14-implementation-critic.md` after implementation.
