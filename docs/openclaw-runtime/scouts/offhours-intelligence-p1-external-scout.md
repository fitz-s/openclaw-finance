# Offhours Intelligence P1 External Scout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## External Sources Checked

- NYSE official hours and calendars: https://www.nyse.com/markets/hours-calendars
- Brave Web Search API documentation: https://api-dashboard.search.brave.com/documentation/services/web-search
- Brave News Search API documentation: https://api-dashboard.search.brave.com/documentation/services/news-search
- Brave LLM Context API documentation: https://api-dashboard.search.brave.com/documentation/services/llm-context
- Brave Answers API documentation: https://api-dashboard.search.brave.com/documentation/services/answers
- Brave pricing/rate-limit documentation: https://api-dashboard.search.brave.com/documentation/pricing

The checked official endpoints were reachable during P1 scout. NYSE redirects `/markets/hours-calendars` to `/trade/hours-calendars`, which should remain the human-facing calendar anchor.

## Findings For P1

- Calendar semantics should be anchored to XNYS official holidays/early closes, not weekday-only local time windows.
- Brave Web and News Search are the correct P1 discovery endpoints for fresh source acquisition.
- Brave LLM Context is a reading/compression lane after source selection, not first-pass discovery.
- Brave Answers can cite sources, but it must remain sidecar-only and must not become canonical evidence or a wake/judgment authority.
- P1 should enforce budget before Brave activation because expanding offhours windows without caps will repeat the earlier quota-burn failure.

## P1 Design Consequence

P1 should not start by changing cron cadence. It should first make the current offhours scan path calendar-aware and budget-aware, then later phases can safely widen offhours cadence to nights/weekends/holidays.
