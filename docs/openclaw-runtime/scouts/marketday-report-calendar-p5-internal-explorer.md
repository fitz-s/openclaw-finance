# Marketday Report Calendar P5 Internal Explorer

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Internal finding:

- `finance_discord_report_job.py` currently returns `NO_REPLY` only on weekends.
- Active report crons are weekday-based:
  - `finance-premarket-brief`: `10 8 * * 1-5`
  - `finance-premarket-delivery-watchdog`: `25 8 * * 1-5`
  - `finance-midday-operator-review`: `15 13 * * 1-5`
- Weekday market holidays can still enter report chain.
- Half-day fixed second core review can run after early close if schedule stays 13:15 CT.
- Existing `offhours_session_clock.py` already exposes holiday / early-close / session-class state.

Recommended P5:

- Add report-calendar guard inside `finance_discord_report_job.py` before `run_chain`.
- Write `state/marketday-report-calendar-guard.json` for audit.
- Skip non-trading days for all report modes.
- Skip `marketday-core-review` when the exchange is no longer in RTH on an early-close day.
- Do not alter Discord delivery, safety, or cron topology.
