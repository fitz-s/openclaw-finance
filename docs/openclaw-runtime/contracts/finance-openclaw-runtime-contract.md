# Finance OpenClaw Runtime Contract

Finance is an OpenClaw-embedded system. OpenClaw cron/session surfaces own cognition, orchestration, and user-visible delivery. Deterministic Python scripts are tools and state transformers, not independent reporting actors.

## Active Runtime Surfaces

### OpenClaw Cron

OpenClaw cron jobs are the authoritative runtime entrypoints for:

- market-hours LLM scanning
- offhours LLM scanning
- user-visible report orchestration and delivery
- weekly learning / optimization review

Inspect them with:

```bash
/Users/leofitz/.npm-global/bin/openclaw cron list --all --json
```

### System Crontab

System crontab is feeder-only. It may run deterministic scripts for:

- price fetching
- IBKR Flex fetching
- Flex performance/cash/NAV/option-risk enrichment
- portfolio resolution
- portfolio alerts
- watchlist sync
- deterministic maintenance such as calibration and hypothesis extraction

System crontab must not directly deliver user-visible finance reports.

### Python Scripts

Python scripts provide deterministic tools:

- collector / fetcher
- normalizer / enricher
- packet compiler
- envelope renderer fallback
- validator
- delivery audit
- replay / learning support

They may be invoked by OpenClaw cron, but they are not the system's cognition surface.

## Active Finance Flow

```text
system crontab feeder
  -> prices.json
  -> portfolio-flex.json
  -> portfolio-performance.json
  -> portfolio-cash-nav.json
  -> portfolio-option-risk.json
  -> portfolio-resolved.json

OpenClaw LLM scanner cron
  -> bounded search/research
  -> finance/buffer/*.json
  -> finance_worker.py
  -> report-gate-state.json

OpenClaw report orchestrator cron
  -> finance_report_packet.py
  -> finance_deterministic_report_render.py
  -> finance_report_validator.py
  -> validated ReportEnvelope markdown
  -> OpenClaw announce delivery

OpenClaw learning cron
  -> signal/calibration/audit/run-history review
  -> review-only optimization recommendations
```

## Deprecated Surfaces

- `finance/REPORT_TEMPLATE.md` is not the active renderer contract.
- Disabled/manual jobs that reference `finance-judgment-report-shadow*` are legacy surfaces and must not be enabled without contract migration.
- Direct `native_premarket_brief_live.py --deliver` from system crontab is deprecated. OpenClaw cron owns delivery.

## Completion Standard

Do not claim the finance runtime is healthy from file edits alone. The embedded audit must pass:

```bash
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_openclaw_embedded_audit.py
```

Runtime evidence must include OpenClaw cron visibility and either recent run history or a future scheduled run for active finance jobs.
