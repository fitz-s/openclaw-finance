# TradingAgents Bridge Contract

TradingAgents in this repository is a review-only, advisory-only sidecar.

It is not:

- wake authority
- judgment authority
- canonical evidence
- canonical report input
- announce-card input
- threshold mutation input
- execution authority

## Active Boundary

The active finance user-visible path remains:

```text
ContextPacket
  -> WakeDecision
  -> JudgmentEnvelope
  -> finance_decision_report_render.py
  -> finance_report_product_validator.py
  -> finance_decision_log_compiler.py
  -> finance_report_delivery_safety.py
```

TradingAgents may only publish:

- raw sidecar artifacts under `state/tradingagents/runs/**`
- normalized advisory artifacts under `state/tradingagents/runs/<run_id>/normalized/**`
- validated reader augmentation under `state/tradingagents/latest-reader-augmentation.json`
- validated non-authoritative context digest under `state/tradingagents/latest-context-digest.json`

## Raw / Machine / Surface Split

### Raw

Raw run artifacts may contain trading language and upstream research text.
They are local runtime state only.

Allowed paths:

- `state/tradingagents/runs/<run_id>/raw/run-artifact.json`
- `state/tradingagents/runs/<run_id>/raw/redacted-final-state.json`
- `state/tradingagents/runs/<run_id>/raw/redaction-report.json`

### Machine-Only

Machine-only normalized fields may contain extracted ratings such as:

- `BUY`
- `OVERWEIGHT`
- `HOLD`
- `UNDERWEIGHT`
- `SELL`

These fields must not be copied into user-facing text.

### Surface-Eligible

Surface-eligible fields must remain advisory-only and free of:

- buy/sell/order language
- sizing/allocation language
- entry/exit/stop language
- `live_authority`
- `execution_adapter`
- Chinese execution/trading command language

## Reader Bundle Use

`finance_report_reader_bundle.py` may merge TradingAgents cards only when:

- `review_only=true`
- `no_execution=true`
- the augmentation `report_hash` matches the current report
- the augmentation is not stale

TradingAgents handles must remain derived exploration handles such as `TA1`.

## Context Pack Use

`finance_llm_context_pack.py` may include a compact TradingAgents digest only when:

- `review_only=true`
- `no_execution=true`
- `candidate_contract_exclusion=true`
- the digest is not stale

The digest must not:

- appear in `allowed_evidence_refs`
- alter `candidate_contract`
- alter `scheduled_context_allowed_thesis_states`
- alter `event_wake_allowed_thesis_states`

## Forbidden Promotions

TradingAgents generated prose must not be promoted directly into:

- `JudgmentEnvelope.evidence_refs`
- report markdown
- delivery safety decision
- capital agenda priority

Only later deterministic source-fetch work may promote citations into fetch candidates.

## Required Top-Level Flags

Every public-facing TradingAgents bridge artifact must carry:

- `review_only=true`
- `no_execution=true`

The advisory decision must also carry:

- `execution_readiness="disabled"`

## Failure Rule

If the runner, translator, validator, or surface compiler fails:

- write failure/status artifacts
- do not update latest validated reader/context pointers
- do not affect the active finance report chain
