# Offhours Intelligence P3 External Scout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

External anchor checked:

- NYSE official hours and calendars: https://www.nyse.com/markets/hours-calendars

P3 depends on XNYS calendar semantics: weekends, exchange holidays, half-days, pre-open, post-close, and overnight gaps are all offhours apertures. The cron schedule itself should stay conservative; the deterministic governor should decide whether a scheduled all-days offhours run is allowed.
