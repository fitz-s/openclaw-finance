# TradingAgents Bridge Contract

TradingAgents may participate in OpenClaw finance only as review-only advisory cognition.

It has two permitted lanes:

- a sidecar artifact lane for non-authoritative research context
- a TradingAgents-primary review lane where TradingAgents owns the advisory cognition and finance is intentionally downgraded to an output/safety shell: packet binding, deterministic downgrade, product validation, decision log, delivery safety, and review-only boundary

## Allowed Role

- compile bounded research requests
- run a validator-gated sidecar wrapper
- replace the upstream Trader/order node and final Portfolio Manager/action node with review-only passthroughs when `disable_order_agent` is not explicitly false
- write local sidecar artifacts
- publish non-authoritative context digests
- publish reader-bundle augmentation
- publish validator-gated primary advisory artifacts
- feed `primary_advisory_cognition` into finance context packs only when explicit primary runtime switches are present
- shape the user-visible primary report through TradingAgents bull/bear/risk/confirmation/source-gap content only; finance content must not become a second market narrative on the primary Discord surface
- shape report output only through `finance_discord_report_job.py` and the existing finance renderer/validator/safety chain

## Forbidden Role

- wake authority
- canonical JudgmentEnvelope authority
- canonical evidence
- canonical report markdown source
- direct announce delivery source
- threshold mutation source
- execution adapter
- broker order path

## Parent Runtime Rule

The parent runtime may expose a manual sidecar job or an enabled TradingAgents-primary review job.

For sidecar jobs:

- delivery must remain `none`
- the job must not send Discord messages directly
- the job must not write canonical finance report state
- the job must not promote evidence directly
- the job must not enable execution

For the TradingAgents-primary review job:

- delivery must remain OpenClaw-managed announce delivery through the finance report job
- the job must invoke `finance_discord_report_job.py --mode marketday-review`
- `OPENCLAW_TRADINGAGENTS_PRIMARY_RUNTIME_ENABLED=1`, `OPENCLAW_TRADINGAGENTS_PRIMARY_RENDER_ENABLED=1`, and `OPENCLAW_TRADINGAGENTS_PRIMARY_REQUIRED=1` must stay together
- missing, stale, invalid, or packet-unbound TradingAgents primary artifacts must produce health-only output, not a finance-only authoritative report
- direct TradingAgents text may reach the primary surface only after the upstream Trader/order node plus final Portfolio Manager/action node are disabled and the validator removes broker/order/action language and secrets
- rollback is disabling the parent job or removing the three primary environment switches
- the job must not enable execution, threshold mutation, wake mutation, broker access, or direct TradingAgents delivery

Order-agent control:

- `ops/tradingagents-sidecar.defaults.json.config.disable_order_agent` defaults to `true`
- `tradingagents_request_packet.py` must emit `config.disable_order_agent=true` unless explicitly overridden for local diagnostics
- `tradingagents_runner.py` must patch TradingAgents graph setup so the upstream `Trader` node emits `ORDER_AGENT_DISABLED_REVIEW_HYPOTHESIS` and the final `Portfolio Manager` node emits `ORDER_AGENT_DISABLED_FINAL_REVIEW`, with no LLM order proposal or final action plan
- the only supported runtime override is `OPENCLAW_TRADINGAGENTS_DISABLE_ORDER_AGENT=0`; production/scheduled jobs must not set it
- downstream risk nodes may evaluate review-only cognition, but no wrapper-approved node may emit broker instructions, position-sizing instructions, or portfolio actions

## Required Artifacts

- `state/tradingagents/runs/**`
- `state/tradingagents/status.json`
- `state/tradingagents/latest-context-digest.json`
- `state/tradingagents/latest-reader-augmentation.json`
- `state/tradingagents/latest-primary-decision.json`
- `state/tradingagents/primary-validation.json`
- `state/tradingagents/primary-runtime-status.json`

## Integration Rule

`finance_llm_context_pack.py` may consume the latest context digest only as non-authoritative sidecar context.

When `OPENCLAW_TRADINGAGENTS_PRIMARY_RUNTIME_ENABLED=1`, `finance_llm_context_pack.py` may mark a validated, current-packet-bound TradingAgents primary decision as `primary_advisory_cognition`.

When `OPENCLAW_TRADINGAGENTS_PRIMARY_RENDER_ENABLED=1`, `finance_decision_report_render.py` may render TradingAgents primary review as the primary Discord/output artifact. Finance may state only binding/safety status; it must not append scanner, capital, thesis, macro-triad, or old finance agenda content to the primary surface.

TradingAgents-primary report surfaces should expose the validated advisory trace:

- analyst readout
- research debate readout
- advisor summary
- bull case
- bear / invalidator case
- risk debate
- required confirmations
- source gaps
- final review boundary before any human action path

Finance prose should identify itself as an output/safety shell, not a secondary cognition layer.

`finance_report_reader_bundle.py` may consume the latest reader augmentation only as exploration-layer augmentation.

Neither integration may alter:

- `allowed_evidence_refs`
- `candidate_contract`
- `WakeDecision`
- delivery safety
- review-only/no-execution boundaries

## Failure Rule

If TradingAgents fails:

- record failure in sidecar state
- do not update latest validated pointers
- do not block the active finance report path unless the caller is an explicitly TradingAgents-required mode

TradingAgents-required mode exception:

- Required modes: `immediate-alert` and any parent runtime job with `OPENCLAW_TRADINGAGENTS_PRIMARY_REQUIRED=1`
- Required-mode failure must fail closed and must not emit finance-only market analysis as if TradingAgents context were fresh
- Required-mode stdout behavior: `immediate-alert` emits `NO_REPLY` through the cron-facing script after writing the failure reason to `state/finance-immediate-alert-state.json`
- Required-mode stdout behavior: primary review jobs emit health-only output when the primary decision is missing, invalid, stale, or not rendered
- Report-job refresh state must be written to `state/tradingagents/report-refresh-status.json`
- Required-mode refresh `status=pass` requires parsed `run_id` and `job_id` from the sidecar job stdout; zero exit codes alone are not sufficient
- Required-mode freshness means same-run binding: `report-refresh-status.run_id` must match `llm-job-context/report-orchestrator.json.tradingagents_sidecar.run_id`
- Required-mode source binding means `latest-primary-decision.json.source_bindings.context_packet.packet_hash` must match the current parent market-ingest packet hash
