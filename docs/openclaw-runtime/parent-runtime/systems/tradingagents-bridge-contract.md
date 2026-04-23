# TradingAgents Bridge Contract

TradingAgents may participate in OpenClaw finance only as a review-only research sidecar.

## Allowed Role

- compile bounded research requests
- run a validator-gated sidecar wrapper
- write local sidecar artifacts
- publish non-authoritative context digests
- publish reader-bundle augmentation

## Forbidden Role

- wake authority
- judgment authority
- canonical evidence
- canonical report markdown source
- announce delivery source
- threshold mutation source
- execution adapter
- broker order path

## Parent Runtime Rule

The parent runtime may expose a manual or disabled job for TradingAgents, but:

- delivery must remain `none`
- the job must not send Discord messages directly
- the job must not write canonical finance report state
- the job must not promote evidence directly
- the job must not enable execution

## Required Artifacts

- `state/tradingagents/runs/**`
- `state/tradingagents/status.json`
- `state/tradingagents/latest-context-digest.json`
- `state/tradingagents/latest-reader-augmentation.json`

## Integration Rule

`finance_llm_context_pack.py` may consume the latest context digest only as non-authoritative context.

`finance_report_reader_bundle.py` may consume the latest reader augmentation only as exploration-layer augmentation.

Neither integration may alter:

- `allowed_evidence_refs`
- `candidate_contract`
- `WakeDecision`
- `JudgmentEnvelope`
- delivery safety

## Failure Rule

If TradingAgents fails:

- record failure in sidecar state
- do not update latest validated pointers
- do not block the active finance report path
