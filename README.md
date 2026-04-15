# Finance Workspace (OpenClaw Embedded Runtime)

权威原则见 `WORKING_PRINCIPLES.md`。本目录是 Mars finance lane 的数据、扫描、门控、报告产物目录，但用户可见报告必须由 OpenClaw cron 驱动，不允许回到独立 Python direct-delivery 跑步机。

## Active User-Visible Path

```text
OpenClaw cron finance-subagent-scanner / finance-subagent-scanner-offhours
  -> finance/buffer/*.json
  -> finance_worker.py
  -> gate_evaluator.py
  -> services/market-ingest typed ContextPacket
  -> latest-wake-decision.json
  -> OpenClaw cron finance-premarket-brief when wake or threshold dispatches
  -> judgment_envelope_gate.py
  -> finance_decision_report_render.py
  -> finance_report_product_validator.py
  -> finance_decision_log_compiler.py
  -> finance_report_delivery_safety.py
  -> Discord announce delivery
```

The active final user-visible source is:

- `finance/state/finance-decision-report-envelope.json`

The active machine truth surfaces are:

- `services/market-ingest/state/latest-context-packet.json`
- `finance/state/watchlist-resolved.json`
- `finance/state/latest-wake-decision.json`
- `finance/state/judgment-envelope.json`
- `finance/state/judgment-validation.json`
- `finance/state/finance-report-product-validation.json`
- `finance/state/finance-decision-log-report.json`
- `finance/state/report-delivery-safety-check.json`

## Compatibility Artifacts

`finance/state/report-input-packet.json` is compatibility-only. It is refreshed by `gate_evaluator.py` so old validators and audits do not see stale `window` / `recommended_report_type`, but it is not a cognition source and must not drive new report logic.

`finance-report-renderer` is disabled/manual-only. It must not deliver user-visible reports.

Legacy Report v1 surfaces have been quarantined under `legacy/report-v1/`. They may exist for historical/regression evidence, but they are not the active delivery chain:

- `legacy/report-v1/REPORT_TEMPLATE.md`
- `legacy/report-v1/prompts/report-renderer.md`
- `legacy/report-v1/scripts/native_premarket_brief_live.py`
- `legacy/report-v1/scripts/finance_deterministic_report_render.py`
- `legacy/report-v1/scripts/finance_report_validator.py`
- `legacy/report-v1/scripts/quality_gate.py`

## Current Job Split

| Lane | Runtime surface | Purpose |
| --- | --- | --- |
| Market-hours scanner | OpenClaw cron `finance-subagent-scanner` | LLM-assisted bounded discovery, writes observations, runs worker/gate |
| Off-hours scanner | OpenClaw cron `finance-subagent-scanner-offhours` | Lower-volume off-hours discovery and gate evaluation |
| Report orchestrator | OpenClaw cron `finance-premarket-brief` | JudgmentEnvelope, product report, decision log, safety gate, final announce |
| Weekly learning | OpenClaw cron `finance-weekly-learning-review` | Replay/eval/learning review, not market advice |
| Deterministic feeders | system cron / local scripts | prices, Flex portfolio snapshots, enrichment, option risk, resolver |

## Data Sources

| Source | Role | Notes |
| --- | --- | --- |
| yfinance | Quote snapshots | Deterministic feeder; snapshot semantics, not tick truth |
| IBKR Flex | Portfolio / performance / NAV / options sections | Snapshot replacement for daily Client Portal login dependency |
| IBKR Client Portal watchlists | User-managed IBKR watchlists | Best-effort sync when logged in; cached/fallback when unavailable |
| OpenClaw scanner web search | Narrative/event discovery | Must write structured observations, not user prose |
| SEC / broad market / options flow proxies | Context evidence | Routed through typed evidence/packet surfaces |

## Verification Commands

```bash
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_runtime_blocker_audit.py
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_report_delivery_audit.py
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_openclaw_embedded_audit.py
```
