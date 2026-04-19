# Exchange Calendar Provider P6 Closeout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Scope

P6 replaces the single-year calendar embedded in `offhours_session_clock.py` with a deterministic 2026-2028 XNYS calendar provider.

## Implemented

- Added `scripts/exchange_calendar_provider.py`.
- Provider contains committed 2026, 2027, and 2028 NYSE holiday and early-close tables.
- `offhours_session_clock.py` now consumes provider functions for:
  - trading-day detection
  - holiday names
  - early-close names
  - RTH close time
  - calendar confidence
- Existing `offhours-aperture-v1` output remains compatible.
- Snapshot export includes `exchange-calendar-provider-report.json`.

## Explicitly Not Changed

- No runtime network lookup.
- No new dependency.
- No cron mutation.
- No Discord delivery mutation.
- No wake threshold mutation.
- No broker/execution authority.

## Verification

```bash
python3 -m pytest -q tests/test_exchange_calendar_provider_p6.py tests/test_offhours_session_clock_p6.py tests/test_marketday_report_calendar_guard_p5.py
# 12 passed

python3 scripts/exchange_calendar_provider.py
# pass, supported_years=[2026, 2027, 2028]

python3 scripts/offhours_session_clock.py --now 2027-01-01T16:00:00Z
# holiday_aperture

python3 -m pytest -q tests
# 347 passed

python3 -m compileall -q scripts tools tests
# pass

python3 tools/audit_operating_model.py
# pass, error_count=0

python3 tools/audit_benchmark_boundary.py
# pass, blocking_reasons=[]
```

## Residual Risks

- Calendar still requires future-year table maintenance before 2029.
- Unscheduled exchange closures remain unsupported unless an override file/table is added in a later phase.
