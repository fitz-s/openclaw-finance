# Offhours Intelligence P0 Implementation Critic

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Verdict

Safe to commit as P0 foundation after the RTH aperture semantics fix.

## Blocking Finding Resolved

Initial critic finding:

- `scripts/offhours_session_clock.py` returned the RTH close time through the `next_rth_open_at` field and allowed RTH `gap_hours` to reflect elapsed time since the prior close. That made the aperture surface semantically confusing even though offhours classification still worked.

Resolution:

- RTH now reports the active session open through `next_rth_open_at` and forces `gap_hours=0.0`.
- `tests/test_offhours_session_clock_p0.py` asserts both conditions.

## Boundary Review

- No active cron schedule mutation in P0.
- No Brave API calls in P0.
- Brave Answers remains sidecar-only and explicitly not evidence authority.
- `BraveBudgetGuard` separates Search, Answers, and LLM-context counters.
- Snapshot exports are sanitized runtime-control state only; no credentials, raw Brave payloads, account IDs, or broker data.
- All new P0 planning/contract/closeout surfaces explicitly reference `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Residual Risks

- The session clock currently uses a 2026 holiday/half-day table. Later phases should either add a generated exchange calendar table or a maintained annual calendar update path before relying on it for long-term production routing.
- P0 exports operational budget usage counters. They are reviewer-safe, but later phases should avoid committing high-frequency budget churn unless it materially helps review.
- P0 intentionally does not activate all-days offhours scheduling; P1/P2 must keep shadow-first routing until budget telemetry is stable.

## Verification Evidence

```bash
python3 -m pytest -q tests/test_offhours_session_clock_p0.py tests/test_brave_budget_guard_p0.py tests/test_offhours_snapshot_p0.py
# 9 passed

python3 -m pytest -q tests
# 304 passed

python3 -m compileall -q scripts tools tests
# pass

python3 tools/audit_operating_model.py
# pass, error_count=0

python3 tools/audit_benchmark_boundary.py
# pass, blocking_reasons=[]
```
