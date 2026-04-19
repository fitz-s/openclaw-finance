# Offhours Intelligence P0 Closeout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Scope

P0 establishes the deterministic substrate for the Calendar-Aware Offhours Intelligence Fabric. It does not change active Discord delivery, cron cadence, wake thresholds, or Brave API routing.

## Implemented

- Added `SessionApertureState` contract so `offhours` means any time outside XNYS regular cash session, including nights, weekends, holidays, and half-day post-close periods.
- Added `BraveBudgetGuard` contract so Search, Answers, and LLM-context usage can be budgeted separately before expanding offhours source acquisition.
- Added deterministic `scripts/offhours_session_clock.py` with 2026 XNYS-compatible weekend, holiday, half-day, pre-open, post-close, overnight, and RTH classification.
- Added deterministic `scripts/brave_budget_guard.py` with monthly, daily, and aperture caps plus dry-run reservation semantics.
- Extended `query-pack-contract.md` with future `session_aperture` and `budget_request` metadata fields.
- Extended runtime snapshot export with sanitized `session-aperture-state.json` and `brave-budget-state.json` for reviewer visibility.
- Added focused tests for calendar semantics and Brave budget separation/exhaustion/dry-run behavior.

## Explicitly Not Activated

- No all-days offhours cron/governor mutation.
- No Brave Answers calls.
- No Brave Search expansion.
- No Discord report delivery change.
- No wake threshold mutation.
- No judgment, execution, or broker authority.

## Reviewer Surfaces

- `docs/openclaw-runtime/ralplan/offhours-intelligence-p0-ralplan.md`
- `docs/openclaw-runtime/contracts/offhours-aperture-contract.md`
- `docs/openclaw-runtime/contracts/brave-budget-guard-contract.md`
- `docs/openclaw-runtime/session-aperture-state.json`
- `docs/openclaw-runtime/brave-budget-state.json`

## Verification

Completed before closeout:

```bash
python3 -m pytest -q tests/test_offhours_session_clock_p0.py tests/test_brave_budget_guard_p0.py
python3 -m compileall -q scripts/offhours_session_clock.py scripts/brave_budget_guard.py tools/export_openclaw_runtime_snapshot.py
python3 scripts/offhours_session_clock.py --now 2026-04-18T16:00:00Z
python3 scripts/brave_budget_guard.py --kind search --units 1 --dry-run --session-class weekend_aperture --aperture-id p0-weekend-demo
python3 tools/export_openclaw_runtime_snapshot.py
```

Broader pre-commit verification:

```bash
python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
```

Result:

- `python3 -m pytest -q tests` -> 304 passed
- `python3 -m compileall -q scripts tools tests` -> pass
- `python3 tools/audit_operating_model.py` -> pass, error_count=0
- `python3 tools/audit_benchmark_boundary.py` -> pass, blocking_reasons=[]

## Next Phase

P1 should have its own ralplan referencing `/Users/leofitz/Downloads/review 2026-04-18.md` and should wire the session aperture into the offhours source router in shadow-first mode. P1 should still avoid active all-days cron mutation until budget telemetry proves the router is bounded.
