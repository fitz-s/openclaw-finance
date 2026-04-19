# Marketday Report Calendar P5 Closeout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Scope

P5 adds an exchange-calendar guard to user-visible finance report jobs. Weekday is no longer sufficient: report jobs now consult the XNYS session aperture before running the heavy report chain.

## Implemented

- Added `report_calendar_guard()` to `scripts/finance_discord_report_job.py`.
- Guard writes `state/marketday-report-calendar-guard.json` on every report job invocation.
- All report modes return `NO_REPLY` on `weekend_aperture` and `holiday_aperture`.
- `marketday-core-review` also returns `NO_REPLY` after early-close half-day RTH ends.
- Real trading-day premarket `marketday-review` still runs during `pre_open_gap`.
- Regular-session `marketday-core-review` still runs fast core path.
- Updated `tools/patch_finance_cron_p4.py` so rerunning the generic finance cron patcher preserves `marketday-core-review` for `finance-midday-operator-review`.
- Snapshot export includes `marketday-report-calendar-guard.json` and P5 plan/scout/critic/closeout docs.

## Explicitly Not Changed

- No Discord delivery topology change.
- No delivery safety bypass.
- No wake threshold mutation.
- No broker/execution authority.
- No cron schedule mutation in P5.

## Verification

```bash
python3 -m pytest -q tests/test_marketday_report_calendar_guard_p5.py tests/test_marketday_report_calendar_snapshot_p5.py tests/test_finance_discord_report_job_p4_core.py
# 7 passed

python3 -m pytest -q tests
# 338 passed

python3 -m compileall -q scripts tools tests
# pass

python3 tools/audit_operating_model.py
# pass, error_count=0

python3 tools/audit_benchmark_boundary.py
# pass, blocking_reasons=[]
```

## Residual Risks

- The exchange calendar table is still explicit for 2026 only. Future phases should replace or extend it before 2027.
- If a future report cron is added after a half-day close with a different mode, the guard policy must be expanded for that mode.
