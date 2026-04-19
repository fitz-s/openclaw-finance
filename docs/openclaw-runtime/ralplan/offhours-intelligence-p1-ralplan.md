# RALPLAN P1: Session-Aware Offhours Source Router

Status: approved_for_p1_implementation
Mode: consensus_planning
Scope: P1 source-router wiring; no cron frequency mutation

## Source Review And Explorer Inputs

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Phase explorer inputs:

- Internal explorer: `docs/openclaw-runtime/scouts/offhours-intelligence-p1-internal-explorer.md`
- External scout: `docs/openclaw-runtime/scouts/offhours-intelligence-p1-external-scout.md`

All later phase plans in this program must also cite `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Task Statement

Wire P0's `SessionApertureState` and `BraveBudgetGuard` into the current offhours scan path so current offhours runs become calendar-aware and budget-aware before any cron cadence expansion. P1 must make offhours QueryPacks carry aperture/budget metadata and must make Brave Search/News activation respect budget decisions.

## Review Requirements Covered In P1

- Use calendar-aware offhours semantics before broadening offhours cadence.
- Treat Brave Web/News Search as discovery lanes and Brave Answers as sidecar-only.
- Prevent stale/repeated source acquisition by making source routing explicit and bounded.
- Keep operator/wake/delivery authority unchanged while adding source-router observability.

## RALPLAN-DR

### Principles

1. Current offhours path first: improve the active offhours scan chain before adding new all-days cron cadence.
2. Mode isolation: `market-hours-scan` must not consume stale offhours aperture state.
3. Budget before network: every offhours Brave Search/News activation must pass `BraveBudgetGuard`.
4. No Answers authority: Answers remains sidecar-only and is not activated in P1.
5. Observability before threshold changes: P1 may write router/source-health state but must not lower wake thresholds or alter Discord delivery.

### Decision Drivers

1. Current `finance_scanner_job.py --mode offhours-scan` does not branch behavior.
2. QueryPacks currently have no `session_aperture` or `budget_request` metadata despite the P0 contract.
3. `brave_source_activation.py` can make live calls without aperture-aware budget preflight.
4. The review's ROI thesis depends on long offhours gaps, but live all-days cadence is unsafe until the current path is bounded.

### Viable Options

#### Option A: Only add aperture metadata to QueryPacks

Pros:
- Minimal risk.
- Good for reviewer visibility.

Cons:
- Does not prevent Brave quota burn.
- Does not make activation budget-aware.

#### Option B: Add an offhours router plus QueryPack metadata plus Brave budget enforcement

Pros:
- Gives current offhours scans real calendar/budget semantics.
- Prevents live source calls when budget is exhausted.
- Leaves cron cadence and wake thresholds unchanged.
- Creates a safe base for all-days offhours cadence in a later phase.

Cons:
- More touchpoints than metadata-only.
- Requires tests across scanner job, QueryPack planner, activation, source health, and native offhours report.

#### Option C: Jump directly to all-days offhours cron

Pros:
- Faster visible coverage expansion.

Cons:
- Repeats the prior failure mode: wider source demand before budget/router proof.
- Harder to debug if quotas or report quality regress.

### Recommendation

Choose Option B.

## ADR

Decision: P1 wires a shadow-compatible but live-budget-enforcing offhours source router into the existing offhours scan path. It does not change cron frequency, wake thresholds, report delivery, or Answers authority.

Rejected: metadata-only wiring | insufficient because it does not bound Brave activation.
Rejected: all-days cron now | unsafe until router/budget telemetry exists.

Consequences:

- Current offhours scans generate `state/offhours-source-router-state.json`.
- Offhours QueryPacks include `session_aperture`, `budget_request`, and `activation_mode`.
- Brave Search/News activation blocks budget-denied packs explicitly.
- Market-hours scans remain unchanged.

## Implementation Plan

1. Add `scripts/offhours_source_router.py`.
   - Builds `SessionApertureState` and writes `state/session-aperture-state.json`.
   - Runs a dry-run budget preflight and writes `state/offhours-source-router-state.json`.
   - Emits max-pack guidance by session class.
   - Does not call Brave and does not mutate wake/delivery.

2. Modify `scripts/finance_scanner_job.py`.
   - `build_steps(mode)` prepends `offhours_source_router.py` only for `offhours-scan`.
   - Pass scanner mode into `query_pack_planner.py` and `finance_parent_market_ingest_cutover.py`.
   - Preserve single-line stdout.

3. Modify `scripts/query_pack_planner.py`.
   - Add `--scanner-mode`.
   - Attach compact `session_aperture` and `budget_request` only when `scanner-mode=offhours-scan` and router state is fresh.
   - Missing router/aperture state is nonfatal.

4. Modify `scripts/finance_parent_market_ingest_cutover.py`.
   - Add `--scanner-mode`.
   - Run offhours router when scanner mode is offhours and router state is missing/stale.
   - Pass scanner mode to `query_pack_planner.py`.
   - Let `brave_source_activation.py` enforce budget from pack metadata.

5. Modify `scripts/brave_source_activation.py`.
   - Read per-pack `budget_request` and `session_aperture`.
   - Check/reserve Search budget before each pack's fetch attempts.
   - In `--dry-run`, budget decisions must remain dry-run and not consume counters.
   - Budget-denied packs produce explicit blocked results.

6. Modify `scripts/source_health_monitor.py`.
   - Surface budget/aperture state as observability row/metric refs only.
   - Do not introduce wake/judgment authority.

7. Modify `scripts/native_scanner_offhours.py`.
   - Add aperture metadata to its report while retaining legacy `window` compatibility.

8. Update runtime snapshot export.
   - Export sanitized `offhours-source-router-state.json`.
   - Add P1 scout/ralplan/critic/closeout files to manifest.

## Test Plan

- `test_finance_scanner_job_offhours_inserts_router_and_preserves_market_hours`
- `test_query_pack_planner_attaches_aperture_budget_only_for_offhours`
- `test_query_pack_planner_missing_router_state_is_nonfatal`
- `test_brave_source_activation_blocks_budget_denied_pack_without_fetch`
- `test_brave_source_activation_dry_run_budget_does_not_consume`
- `test_source_health_monitor_surfaces_budget_guard_observability_only`
- `test_native_scanner_offhours_report_carries_aperture_metadata`
- `test_snapshot_exports_offhours_router_state`

## Pre-Mortem

1. Stale offhours state leaks into market-hours packs.
   - Mitigation: require `--scanner-mode offhours-scan` before attaching aperture metadata.

2. Budget check consumes units twice because planner and parent cutover both run.
   - Mitigation: only `brave_source_activation.py` reserves budget; router and planner use dry-run metadata.

3. Budget-denied packs silently disappear.
   - Mitigation: activation report must include blocked pack results and source health must expose budget state.

4. P1 accidentally turns Answers into authority.
   - Mitigation: no Answers activation in P1; contracts/tests continue to assert sidecar-only.

## Verification Commands

```bash
python3 -m pytest -q tests/test_finance_scanner_job_p1_offhours.py tests/test_query_pack_planner_p1_offhours.py tests/test_brave_source_activation_budget_p1.py tests/test_source_health_monitor_p1_budget.py tests/test_native_scanner_offhours_p1.py tests/test_offhours_snapshot_p1.py
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
python3 scripts/offhours_source_router.py --now 2026-04-18T16:00:00Z
python3 scripts/finance_scanner_job.py --mode offhours-scan
python3 tools/export_openclaw_runtime_snapshot.py
```

## No-Go Items For P1

- No cron cadence mutation.
- No Discord delivery mutation.
- No wake threshold lowering.
- No Brave Answers activation.
- No broker/execution authority.
