# Benchmark Absorption Plan

Finance should learn from external finance/agent products without becoming one of them.

## Boundary

The active product is an OpenClaw-embedded, review-only finance lane. It is not:

- a standalone terminal
- a brokerage advisory app
- an execution system
- a multi-agent trading swarm
- a chat/code-execution app that owns runtime authority

## Absorbable Patterns

| Benchmark family | Absorbable pattern | Finance-compatible landing |
| --- | --- | --- |
| Magnifi / linked-account investing | account-aware personalization | `watchlist-resolved.json`, portfolio state, invalidators |
| OpenBB workspace | inspectable widgets/snapshots | GitHub runtime snapshots and optional local dashboards, never active delivery authority |
| FinRobot | bounded specialist research | isolated research-sidecar for source onboarding or deep packet conflicts, not hot path |
| Fiscal.ai | alerts, API, terminal-grade data hygiene | evidence feeders, rate-limited wakes, reviewer-visible audit snapshots |
| chat/code-exec finance assistants | reproducible analysis notebooks | replay/eval artifacts and offline investigations, not live report authority |

## Rejected Whole-Product Imports

- direct execution / buy buttons
- app workspace as the primary user surface
- model swarm on report hot path
- raw terminal output in user reports
- LLM-only data cleaning or alignment

## Next Packages

1. Add per-dispatch telemetry to decision logs so wake-vs-threshold bridge value can be measured.
2. Add report usefulness scoring over delivered reports: opportunity-first, suggestion clarity, noise tokens, holdings dominance.
3. Add Client Portal watchlist freshness drills after user login to prove IBKR watchlist sync.
4. Add parent market-ingest dependency diff checks to snapshot sync.
5. Evaluate a local reviewer dashboard only after the telemetry above is stable.
