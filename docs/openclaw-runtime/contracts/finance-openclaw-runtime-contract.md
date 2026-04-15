# Finance OpenClaw Runtime Contract

Finance is an OpenClaw-embedded subsystem. OpenClaw cron/session surfaces own cognition, orchestration, and user-visible delivery. Deterministic Python scripts are feeders, transformers, compilers, validators, and audit tools; they are not independent report actors.

## Authority Order

Runtime authority is domain-specific:

1. Active OpenClaw cron payloads and machine truth surfaces define live entrypoints and user-visible delivery.
2. Stable contracts in `systems/` define wake, judgment, report, risk, and safety semantics.
3. Python scripts implement deterministic transformations and gates.
4. Finance repo docs explain the operating model and reviewer workflow.
5. Compatibility artifacts exist only as mirrors for old consumers.
6. Deprecated/manual-only jobs and old templates have no active delivery authority.
7. Prompt files are phrasing shells and cannot bypass validators or safety gates.

## Active Runtime Surfaces

### OpenClaw Cron

OpenClaw cron jobs are the authoritative runtime entrypoints for:

- market-hours LLM scanning
- off-hours LLM scanning
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
- Flex performance / cash / NAV / option-risk enrichment
- portfolio resolution
- watchlist resolution
- portfolio alerts
- deterministic maintenance such as calibration and hypothesis extraction

System crontab must not directly deliver user-visible finance reports.

### Python Scripts

Python scripts provide deterministic tools:

- collector / fetcher
- normalizer / enricher
- packet and compatibility-mirror compiler
- product renderer
- validator
- delivery audit
- replay / learning support

They may be invoked by OpenClaw cron, but they are not the subsystem's cognition surface.

## Active Finance Flow

```text
system crontab feeder
  -> prices.json
  -> portfolio-flex.json
  -> portfolio-performance.json
  -> portfolio-cash-nav.json
  -> portfolio-option-risk.json
  -> portfolio-resolved.json
  -> watchlist-resolved.json

OpenClaw LLM scanner cron
  -> bounded market / watchlist / unknown-discovery scan
  -> finance/buffer/*.json
  -> finance_worker.py
  -> gate_evaluator.py
  -> typed EvidenceRecord / ContextPacket / WakeDecision

OpenClaw report orchestrator cron
  -> read typed ContextPacket + WakeDecision
  -> create or validate JudgmentEnvelope
  -> finance_decision_report_render.py
  -> finance_report_product_validator.py
  -> finance_decision_log_compiler.py
  -> finance_report_delivery_safety.py
  -> final markdown from finance-decision-report-envelope.json
  -> OpenClaw announce delivery

OpenClaw learning cron
  -> signal / calibration / audit / replay review
  -> review-only optimization recommendations
```

## Compatibility Surfaces

`finance/state/report-input-packet.json` is a deprecated compatibility view. It is refreshed to avoid stale-state drift in old validators and audits, but it must not be treated as the active cognition substrate.

The compatibility view is allowed to exist only if:

- it declares `compatibility_view_only=true`
- it declares `must_not_be_used_as_cognition_source=true`
- active delivery continues through typed ContextPacket -> JudgmentEnvelope -> product report -> decision log -> safety gate

## Deprecated Surfaces

- `finance/REPORT_TEMPLATE.md` is not the active renderer contract.
- `finance-report-renderer` is disabled/manual-only and must not deliver user-visible reports.
- Direct `native_premarket_brief_live.py --deliver` from system crontab is deprecated.
- `finance_deterministic_report_render.py`, `finance_report_validator.py`, and `quality_gate.py` are compatibility/legacy surfaces, not active product gates.

## Review-Only Boundary

The subsystem is review-only. `JudgmentEnvelope` may express `watch`, `lean_long`, `lean_short`, `reduce`, or `exit` only as a review artifact under the active adjudication mode. It is never an execution command.

No finance script may place trades or call an execution adapter unless a separate approved execution-adapter packet changes `risk-gates.md`.

## Completion Standard

Do not claim the finance runtime is healthy from file edits alone. Embedded audits must pass:

```bash
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_openclaw_embedded_audit.py
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_native_runtime_status.py
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_report_delivery_audit.py
```

Runtime evidence must include OpenClaw cron visibility and either recent run history or a future scheduled run for active finance jobs.
