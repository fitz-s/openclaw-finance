# RALPLAN P6: Exchange Calendar Provider And Annual Rollover

Status: approved_for_p6_implementation
Mode: consensus_planning
Scope: deterministic 2026-2028 XNYS calendar provider

## Source Review And Explorer Inputs

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Phase explorer inputs:

- Internal explorer: `docs/openclaw-runtime/scouts/exchange-calendar-provider-p6-internal-explorer.md`
- External scout: `docs/openclaw-runtime/scouts/exchange-calendar-provider-p6-external-scout.md`

## Task Statement

Replace the single-year 2026 calendar embedded in `offhours_session_clock.py` with a deterministic exchange calendar provider covering 2026-2028, so scanner/report guards do not silently fail on 2027 market holidays or early closes.

## RALPLAN-DR

### Principles

1. Calendar authority must be deterministic and reviewable.
2. No runtime network lookup for core clock decisions.
3. No new dependency.
4. Existing `offhours-aperture-v1` contract must remain backward compatible.
5. Unsupported years should remain visibly degraded.

### ADR

Decision: Add `exchange_calendar_provider.py` with committed 2026-2028 XNYS holiday and early-close tables, then make `offhours_session_clock.py` consume the provider.

Rejected: Runtime fetch from NYSE | brittle and not safe in cron hot path.
Rejected: New calendar dependency | violates no-new-dependency default and increases install risk.
Rejected: Keep 2026-only table | allows 2027 weekday holidays to be misclassified.

## Test Plan

- 2026 existing behavior remains unchanged.
- 2027 New Year's Day is `holiday_aperture` with `calendar_confidence=ok`.
- 2027 day after Thanksgiving is early close and post-close becomes `halfday_postclose_aperture`.
- 2028 Jan 3 is normal RTH, covering no observed New Year's Day for Jan 1 Saturday.
- Report calendar guard returns `NO_REPLY` on 2027 weekday holiday and half-day post-close core review.
- Snapshot exports calendar provider report.

## No-Go Items

- No cron mutation.
- No delivery mutation.
- No wake threshold mutation.
- No broker/execution authority.
