# Marketday Report Calendar P5 External Scout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

External anchor checked:

- NYSE official hours and calendars: https://www.nyse.com/markets/hours-calendars

P5 uses XNYS trading-day semantics from the existing session aperture clock. Weekday is not sufficient: market holidays must skip report jobs, and half-day post-close fixed core review should not run as if regular session time remains.
