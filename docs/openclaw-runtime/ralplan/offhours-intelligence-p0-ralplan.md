# RALPLAN P0: Calendar-Aware Offhours Intelligence Fabric

Status: approved_for_p0_implementation
Mode: consensus_planning
Scope: P0 foundation only; no broad cron behavior change in this phase

## Source Review

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

This P0 plan is derived from that review and must not implement less than the review's P0-relevant requirements. Later phases must also cite the same review file explicitly in their plan files.

## Task Statement

Start the Calendar-Aware Offhours Intelligence Fabric by replacing the loose concept of `offhours` with a first-class session aperture model and budget guard skeleton. P0 must establish contracts, deterministic scripts, tests, and reviewer-visible snapshots so later phases can safely implement source routing, Answers compression, aperture-aware query memory, undercurrent scoring, deep-dive cache, and cron/governor changes.

## Review Requirements Covered in P0

From `/Users/leofitz/Downloads/review 2026-04-18.md`, P0 covers:

- `offhours` must mean any non-XNYS regular cash session, not weekday-only non-market-hours.
- Session classes must include `rth`, `post_close_gap`, `overnight_session`, `pre_open_gap`, `weekend_aperture`, `holiday_aperture`, and `halfday_postclose_aperture`.
- Session aperture must expose `global_liquidity_band`, `is_offhours`, `is_long_gap`, previous/next RTH boundaries, `gap_hours`, `discovery_multiplier`, `answers_budget_class`, and `monday_open_risk`.
- Offhours activation budgets must differ by session class.
- Brave Answers is not authority; it is a later compression primitive gated by seed evidence, selected handle, citation rules, and budget health.
- Snapshots/reviewer exports must include aperture state and budget state before active behavior changes.

P0 intentionally does not implement the later review sections for active Answers routing, deep-dive cache, undercurrent scoring, follow-up cache, or cron mutation. Those are separate phase plans that must refer back to the same review file.

## RALPLAN-DR

### Principles

1. Calendar authority before behavior: do not mutate offhours cron/alerts until the exchange-calendar aperture state is deterministic and tested.
2. Offhours is a first-class session state, not a string mode or weekday-only cron bucket.
3. Budget guard before source expansion: Search/Answers calls must be bounded before any all-days heartbeat can be safely activated.
4. Answers stays sidecar-only and citation-gated; P0 may model budgets but must not route Answers into hot path.
5. Reviewer visibility is mandatory: aperture and budget snapshots must be exported into `docs/openclaw-runtime`.

### Decision Drivers

1. Current offhours cron excludes weekends/holidays, wasting the highest-ROI long-gap windows.
2. Current fixed windows in `finance_worker.py` / `gate_evaluator.py` are compatibility views and cannot model holidays/half-days/long gaps.
3. Brave Search already hits quota/rate-limit; expanding offhours without budget guard would make quality worse, not better.

### Viable Options

#### Option A: Add weekend cron now

Pros:
- Fastest visible change.
- Minimal code.

Cons:
- Repeats the same coarse offhours semantics.
- No holiday/half-day awareness.
- No budget guard.
- High risk of Brave quota burn and alert spam.

#### Option B: P0 foundation: aperture contract + clock + budget guard + snapshots

Pros:
- Establishes correct offhours definition before behavior changes.
- Creates testable calendar/budget primitives.
- Enables later Answers/source routing without quota runaway.
- Low runtime risk; no alert behavior mutation yet.

Cons:
- Does not immediately turn on weekend undercurrent heartbeat.
- Requires one additional implementation phase for active routing.

#### Option C: Full offhours system in one package

Pros:
- Fastest path to end-state.

Cons:
- Too much blast radius: calendar, budget, Answers, query memory, undercurrents, deep-dive cache, and cron all change at once.
- Hard to debug if reports or budgets regress.

### Recommendation

Choose Option B for P0.

Implement the deterministic substrate now, then run P1/P2/P3 as separate ralplan-backed phases:

- P1: session-aware offhours source router + budgeted Brave Search/News.
- P2: Answers activation gate + Answers usage reporting.
- P3: undercurrent/deep-dive cache/follow-up slice upgrades.
- P4: active all-days offhours heartbeat cron/governor.

## ADR

Decision: P0 implements calendar-aware `SessionApertureState` and `BraveBudgetGuard` as shadow/reviewer-visible primitives before changing active offhours behavior.

Alternatives rejected:
- Weekend-only cron patch: too coarse and fails the review requirement that offhours include holidays, half-days, and long gaps.
- Full implementation now: too much runtime blast radius and likely to burn Brave quota before budget controls are tested.

Consequences:
- Offhours runtime remains mostly unchanged after P0.
- Later phases gain a deterministic calendar/budget contract and tests.
- Reviewer packets/snapshots can begin showing aperture state even before active cron mutation.

## P0 Implementation Plan

### Phase P0.1 Contracts

Add:

- `docs/openclaw-runtime/contracts/offhours-aperture-contract.md`
- `docs/openclaw-runtime/contracts/brave-budget-guard-contract.md`

Update:

- `docs/openclaw-runtime/contracts/query-pack-contract.md` with aperture/budget metadata fields as planned future use, not authority.

Acceptance:

- Contracts cite `/Users/leofitz/Downloads/review 2026-04-18.md`.
- Contracts state no wake/judgment/delivery/execution authority.
- Contracts define `SessionApertureState` and `OffhoursActivationBudget` fields from the review.

### Phase P0.2 Session Clock

Add:

- `scripts/offhours_session_clock.py`

Behavior:

- Use deterministic XNYS-compatible calendar rules with weekend/holiday/half-day support.
- No new external dependency.
- Output `state/session-aperture-state.json`.
- Include fallback rule for years beyond explicit holiday table: weekends still offhours, regular weekday RTH still works, unknown holidays marked `calendar_confidence=degraded`.

Minimum holidays/half-days for 2026 should include common NYSE closures and early close cases sufficient for tests.

Acceptance:

- Saturday -> `weekend_aperture`, `is_offhours=true`, `is_long_gap=true`.
- Known holiday -> `holiday_aperture`.
- Half-day after early close -> `halfday_postclose_aperture`.
- Weekday RTH -> `rth`, `is_offhours=false`.
- Weekday 20:00 ET -> `overnight_session`.
- Pre-open gap -> `pre_open_gap`.
- Post-close gap -> `post_close_gap`.

### Phase P0.3 Budget Guard Skeleton

Add:

- `scripts/brave_budget_guard.py`

Behavior:

- Read/write `state/brave-budget-state.json`.
- Track Search and Answers separately.
- Support monthly/daily/aperture caps.
- Provide dry-run check/reserve API via CLI.
- Do not make Brave calls.
- Do not mutate existing query registry yet.

Default P0 caps:

- Search monthly cap: `3000`
- Answers monthly cap: `300`
- Search daily base cap: `100`
- Weekend/holiday search daily cap: `150`
- Answers per run cap comes from aperture budget.

Acceptance:

- Budget check allows usage under cap.
- Budget check blocks when monthly cap exhausted.
- Search and Answers counters are separate.
- Weekend/holiday cap differs from default daily cap.
- State is deterministic and reviewer-safe.

### Phase P0.4 Snapshot Export

Update:

- `tools/export_openclaw_runtime_snapshot.py`

Add reviewer-visible exports:

- `docs/openclaw-runtime/session-aperture-state.json`
- `docs/openclaw-runtime/brave-budget-state.json`

Acceptance:

- Snapshot manifest includes both files.
- Export does not include credentials or raw Brave payloads.

### Phase P0.5 Documentation / Closeout

Add:

- `docs/openclaw-runtime/cleanup/offhours-intelligence-p0-20260419.md`

Acceptance:

- Documents what P0 did and did not activate.
- Explicitly points to later phases and the source review file.

## Expanded Test Plan

Unit tests:

- `test_offhours_includes_weekend_holiday_halfday_not_just_weekday_non_rth`
- `test_session_clock_uses_exchange_calendar_not_manual_weekday_clock`
- `test_weekend_aperture_receives_higher_discovery_and_answers_budget`
- `test_postclose_gap_does_not_run_broad_macro_discovery`
- `test_brave_budget_guard_separates_search_and_answers`
- `test_brave_budget_guard_blocks_monthly_exhaustion`
- `test_snapshot_exports_aperture_and_budget_state`

Integration smoke:

- Run `offhours_session_clock.py --now <fixed timestamp>` for weekend, holiday, half-day, RTH.
- Run `brave_budget_guard.py --kind search --units 1 --dry-run`.
- Run `export_openclaw_runtime_snapshot.py` and verify exported docs.

## Pre-Mortem

1. Calendar bugs cause market-hours job to think it is offhours.
   - Mitigation: explicit RTH, pre-open, post-close, weekend, holiday, half-day tests with fixed timestamps.

2. Budget guard blocks all source usage due to stale or corrupt state.
   - Mitigation: state schema is simple, default missing state to zero usage, and write clear degraded status.

3. P0 accidentally implies Answers can be used as evidence authority.
   - Mitigation: contracts and tests must state Answers remains sidecar-only and not evidence authority.

## Verification Commands

```bash
python3 -m pytest -q tests/test_offhours_session_clock_p0.py tests/test_brave_budget_guard_p0.py tests/test_prompt_snapshot_contract.py
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
python3 scripts/offhours_session_clock.py
python3 scripts/brave_budget_guard.py --kind search --units 1 --dry-run
python3 tools/export_openclaw_runtime_snapshot.py
```

## No-Go Items For P0

- No active cron schedule mutation.
- No Brave Answers hot-path calls.
- No offhours report delivery changes.
- No wake/threshold mutation.
- No deep-dive cache routing yet.

## Staffing Guidance

P0 can be implemented by one executor with focused tests. Later phases should use ralplan + critic before implementation because they will touch active source routing and cron behavior.
