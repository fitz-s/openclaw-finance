# RALPLAN Source-to-Campaign Phase 13: Final Active Cutover Gate

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Add a deterministic source-to-campaign cutover readiness gate. The gate says whether the stack is ready for future active consumption; it does not itself change wake priority, delivery, thresholds, or execution authority.

## Principles

1. Active cutover requires a gate, not a leap.
2. Fail closed: missing replay/source/follow-up/ROI/lifecycle artifacts produce hold.
3. Readiness is review evidence, not authority.
4. No wake priority mutation in this phase.

## Decision Drivers

1. Phases 00-12 now emit the required artifacts.
2. The review requires rollout/rollback and monitoring before active influence.
3. Direct wake integration is risky without a deterministic gate.

## Selected Plan

- Add `scripts/finance_source_to_campaign_cutover_gate.py`.
- Output `state/source-to-campaign-cutover-gate.json`.
- Gate checks report archive exact replay, reviewer packets, campaign board evidence, follow-up route coverage, thread lifecycle metadata, source ROI, and options IV surface.
- Integrate optional report-job run after archive/cache generation.

## Acceptance Criteria

- Gate returns `hold` with blocking reasons when required artifacts are missing.
- Gate returns `ready` in complete fixture.
- Gate output is review-only and no-execution.
- Report job runs gate optionally without changing delivery.

## Test Plan

- `test_cutover_gate_holds_when_replay_missing`
- `test_cutover_gate_ready_with_complete_artifacts`
- `test_report_job_runs_cutover_gate_optionally`

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-13-implementation-critic.md` after implementation.
