# RALPLAN P5: Exchange-Calendar Report Guard

Status: approved_for_p5_implementation
Mode: consensus_planning
Scope: report cron calendar guard

## Source Review And Explorer Inputs

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Phase explorer inputs:

- Internal explorer: `docs/openclaw-runtime/scouts/marketday-report-calendar-p5-internal-explorer.md`
- External scout: `docs/openclaw-runtime/scouts/marketday-report-calendar-p5-external-scout.md`

## Task Statement

Prevent weekday market holidays and half-day post-close windows from triggering unnecessary user-visible report jobs. Add an exchange-calendar guard before the report chain in `finance_discord_report_job.py`.

## RALPLAN-DR

### Principles

1. Exchange calendar beats weekday cron.
2. Guard before heavy report chain.
3. Preserve existing safety/delivery path.
4. Write guard state for reviewer visibility.
5. No cron topology expansion.

### ADR

Decision: Add `marketday_report_calendar_guard` inside `finance_discord_report_job.py`, based on `offhours_session_clock.build_state`. All report modes skip non-trading days. `marketday-core-review` also skips if it is no longer RTH on an early-close day.

Rejected: Patch cron dates manually | brittle and incomplete.
Rejected: Let report chain run and return health-only | wastes runtime and can still produce noisy operator surfaces.

## Test Plan

- holiday weekday returns `NO_REPLY` without running chain.
- regular trading day premarket runs chain.
- half-day post-close `marketday-core-review` returns `NO_REPLY`.
- regular RTH `marketday-core-review` runs fast chain.
- snapshot exports guard state.

## No-Go Items

- No Discord delivery mutation.
- No safety bypass.
- No wake threshold mutation.
- No broker/execution authority.
