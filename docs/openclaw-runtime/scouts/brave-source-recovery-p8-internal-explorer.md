# Brave Source Recovery P8 Internal Explorer

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Internal findings:

- `brave_source_activation.py` currently skips exact repeated query packs via query registry before budget checks.
- It still lacks a global Brave source breaker for cross-query quota/rate-limit pressure.
- Rate-limited records are persisted in `state/brave-web-search-results.jsonl` and `state/brave-news-search-results.jsonl`.
- Source health already marks Brave quota/rate-limit as degraded.
- The safe P8 implementation is a read-only recovery policy that defers activation before budget/fetch when recent Brave source records indicate quota/rate-limit pressure.
