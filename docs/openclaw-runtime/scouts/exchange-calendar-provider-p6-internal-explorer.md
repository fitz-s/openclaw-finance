# Exchange Calendar Provider P6 Internal Explorer

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Internal finding:

- `offhours_session_clock.py` used `HOLIDAYS_2026` and `EARLY_CLOSES_2026` directly.
- Calendar mistakes propagate into offhours scanner governor, offhours source router, native offhours scanner, report calendar guard, QueryPack metadata, source-health observability, and snapshots.
- `calendar_confidence=degraded` was only metadata. For unsupported years, weekday holidays could be treated as trading days.

P6 touchpoints:

- Add `scripts/exchange_calendar_provider.py` with committed NYSE/XNYS 2026-2028 holiday and early-close tables.
- Update `scripts/offhours_session_clock.py` to consume provider functions.
- Export `exchange-calendar-provider-report.json` for reviewers.
- Add tests for 2027 holiday, 2027 early close, 2028 no-New-Year-observed behavior, and 2027 report guard behavior.
