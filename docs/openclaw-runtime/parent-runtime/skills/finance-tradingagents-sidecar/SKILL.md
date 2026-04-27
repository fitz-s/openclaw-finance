---
name: finance-tradingagents-sidecar
description: Manual operator surface for the review-only TradingAgents finance sidecar.
metadata:
  openclaw:
    emoji: "🧠"
---

# Finance TradingAgents Sidecar

This skill is manual-only. It does not deliver Discord messages and it does not mutate finance authority.

## Procedure

1. Run `python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_llm_context_pack.py`
2. Read `state/llm-job-context/tradingagents-sidecar.json`
3. Run `python3 /Users/leofitz/.openclaw/workspace/finance/scripts/thesis_research_packet.py`
4. Run `python3 /Users/leofitz/.openclaw/workspace/finance/scripts/tradingagents_sidecar_job.py --mode offhours`
5. Inspect:
   - `state/tradingagents/status.json`
   - `state/tradingagents/latest-context-digest.json`
   - `state/tradingagents/latest-reader-augmentation.json`
   - `state/tradingagents/latest-primary-decision.json`
   - `state/tradingagents/primary-validation.json`
   - `state/tradingagents/primary-runtime-status.json`

## Forbidden

- Do not send Discord messages directly
- Do not write canonical report markdown
- Do not promote evidence directly
- Do not mutate thresholds or wake
- Do not execute trades
