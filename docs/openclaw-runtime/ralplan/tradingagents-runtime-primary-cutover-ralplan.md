# RALPLAN: TradingAgents Runtime Primary Cutover

Status: phase3_parent_cutover_lane_live_verified
Go for Phase 0 implementation: complete
Go for Phase 1 implementation: complete as disabled-by-default primary advisory artifacts
Go for Phase 2 implementation: complete behind explicit primary runtime/render switches
Go for Phase 3 implementation: complete as live parent runtime lane
Deliberate RALPLAN: true

## Task Statement

Promote TradingAgents from a validator-gated research sidecar into the primary finance runtime cognition lane, with the existing OpenClaw finance subsystem becoming the deterministic guardrail, portfolio context, delivery, audit, and review-only boundary layer.

This is not a bug-fix-only change. It reverses the current authority assumption:

- Current: finance canonical pipeline is primary; TradingAgents is non-authoritative context.
- Target: TradingAgents runtime assessment is primary review cognition; finance validates, bounds, sanitizes, logs, and delivers.

The review-only boundary remains unchanged: no broker execution, no threshold mutation by LLM output, no live authority change, no account identifiers, and no delivery bypass.

## Current Facts

Fact: `docs/openclaw-runtime/contracts/tradingagents-bridge-contract.md` currently restricts TradingAgents to sidecar status and explicitly forbids wake authority, judgment authority, canonical evidence, report markdown source, and announce delivery source.

Fact: `finance_discord_report_job.py` already tries to refresh TradingAgents before marketday/core/immediate-alert reports, but it calls the refresh through `run_optional`. A TradingAgents failure is swallowed and the finance report chain continues.

Fact: current local runtime readiness passes on this machine, with Google provider/auth available, but records a Python 3.14 LangChain compatibility warning.

Fact: latest stored scheduled job reports show prior failures caused by missing TradingAgents modules/auth in the cron/runtime environment. The failure mode is environment skew between the interactive/local environment and scheduled OpenClaw runtime.

Fact: targeted sidecar bridge tests currently pass, so the bridge shape is testable; the broken part is runtime authority/wiring, not the entire local Python surface.

## Primary Decision

Use TradingAgents as the primary runtime cognition engine, but do not let it become the execution or delivery authority.

Authority split:

- TradingAgents owns multi-agent market/thesis assessment, debate, risk discussion, and primary advisory decision text.
- Finance owns deterministic inputs, portfolio/watchlist context, freshness gates, sanitization, no-execution enforcement, delivery safety, audit logs, reader bundles, and Discord delivery.
- JudgmentEnvelope is either replaced by or wrapped around a new TradingAgentsPrimaryDecision envelope. It must no longer pretend TradingAgents is merely a context add-on when this lane is active.

## Required Contract Inversions

1. Replace the sidecar-only bridge contract with a runtime-primary bridge contract.
2. Change tests that currently assert `runtime_import_allowed_in_p1 is False`; the new assertion should distinguish allowed review-only runtime import from forbidden broker/order API surfaces.
3. Add a `tradingagents_primary_runtime_enabled` switch, default false.
4. Add a `tradingagents_primary_required` mode for selected jobs. In that mode, missing/failing TradingAgents must produce `NO_REPLY` or health-only output, not a finance-only report that looks authoritative.
5. Preserve `no_execution=True`, `review_only=True`, `no_threshold_mutation=True`, and `no_live_authority_change=True` on every promoted artifact.

## Target Runtime Shape

```text
price/source/context refresh
→ finance deterministic context packet
→ TradingAgents primary run
→ TradingAgentsPrimaryDecision envelope
→ finance primary-decision validator
→ finance report renderer / announce card / reader bundle
→ finance product validator
→ finance decision log
→ delivery safety
→ OpenClaw Discord delivery
```

Finance remains in the path after TradingAgents. It is the guardrail and product surface, not the main reasoning engine.

## Phase Plan

### Phase 0: Stabilize the Existing Crash

Goal: make failure explicit and diagnosable.

Scope:

- Phase 0 does not make TradingAgents canonical judgment authority.
- Phase 0 does not let TradingAgents send Discord messages directly.
- Phase 0 does not change wake, thresholds, broker paths, or execution authority.

TradingAgents-required modes:

- `immediate-alert` is required in Phase 0.
- `marketday-review` and `marketday-core-review` refresh TradingAgents opportunistically but are not required in Phase 0.
- `morning-watchdog` does not refresh TradingAgents.

Fail-closed stdout behavior:

- `immediate-alert`: if TradingAgents refresh fails, lacks a run id, or the context pack digest is not bound to the same run id, the cron-facing stdout is exactly `NO_REPLY`. The failure reason is written to `state/finance-immediate-alert-state.json`.
- `marketday-review`: if TradingAgents refresh fails, continue the finance report path, but write `state/tradingagents/report-refresh-status.json` and keep TradingAgents non-authoritative.
- `marketday-core-review`: same as `marketday-review`.
- `morning-watchdog`: unchanged duplicate-suppression behavior.

Fresh context definition:

- Digest presence is insufficient for required modes.
- Required-mode freshness means `state/tradingagents/report-refresh-status.json.status == pass`.
- Required-mode refresh success requires a parsed sidecar `run_id` and `job_id`; zero subprocess exit codes alone are insufficient.
- Required-mode freshness also requires same-run binding: `report-refresh-status.run_id` equals `state/llm-job-context/report-orchestrator.json.tradingagents_sidecar.run_id`.

Failure visibility artifacts:

- `state/tradingagents/report-refresh-status.json`: per report-job refresh result, mode, required flag, sidecar python path, steps, failed step, job id, run id.
- `state/tradingagents/status.json`: latest sidecar job status, including failure stage and latest job report path.
- `state/tradingagents/job-reports/*.json`: per-run sidecar report.
- `state/finance-immediate-alert-state.json`: required-mode delivery/suppression decision.

Changes:

- Make TradingAgents refresh return a structured status instead of being fully swallowed.
- Record refresh result into `state/tradingagents/status.json` and report job state.
- Add explicit fail-closed output policy when a TradingAgents-required mode fails.
- Pin or route the scheduled runtime to the same Python/dependency environment that passes readiness locally.
- Preserve the old non-blocking behavior only for non-required report modes.

Acceptance:

- Scheduled job and local readiness use the same module/auth resolution.
- A TradingAgents failure is visible in the report job state.
- `immediate-alert` cannot deliver without same-run TradingAgents context.
- Existing bridge contract explicitly documents the required-mode exception to the old non-blocking failure rule.
- Observability includes the exact failed step, stderr/stdout preview, run id when available, and runtime python path.
- E2E dry-run evidence shows `/opt/homebrew/bin/python3` no longer controls the TradingAgents sidecar runtime when the conda runtime is the only passing environment.

### Phase 1: Introduce Runtime-Primary Artifacts

Goal: add the new artifact layer without deleting sidecar compatibility.

Scope:

- TradingAgents primary artifacts are advisory candidates only in Phase 1.
- The finance report authority chain remains unchanged by default.
- Renderer consumption is behind `OPENCLAW_TRADINGAGENTS_PRIMARY_RENDER_ENABLED=1`.

New artifacts:

- `state/tradingagents/latest-primary-decision.json`
- `state/tradingagents/primary-runtime-status.json`
- `state/tradingagents/primary-validation.json`

Minimum fields:

- `run_id`
- `instrument`
- `analysis_date`
- `signal`
- `advisor_summary`
- `bull_case`
- `bear_case`
- `risk_discussion`
- `confidence`
- `source_bindings`
- `forbidden_actions`
- `review_only`
- `no_execution`
- `candidate_contract_exclusion`

Acceptance:

- Validator rejects execution language unless quarantined in raw/redacted machine fields.
- Validator rejects missing source bindings.
- Renderer can consume the primary decision behind a disabled feature flag.
- `latest-primary-decision.json` is published only when `primary-validation.json.status == pass`.

### Phase 2: Switch Report Cognition Order

Goal: finance report output should be shaped by TradingAgents primary decision when the switch is enabled.

Changes:

- `finance_llm_context_pack.py` marks TradingAgents primary decision as primary advisory cognition in enabled modes.
- `finance_decision_report_render.py` renders TradingAgents first, then finance deterministic corroboration/contradiction.
- `judgment_envelope_gate.py` either wraps the TradingAgents decision or becomes a deterministic safety gate for it.
- Finance fallback is explicit: `tradingagents_unavailable`, not silent reversion to old authority.

Acceptance:

- Report text makes clear that the review is TradingAgents-led and finance-validated.
- Finance deterministic facts can contradict or downgrade a TradingAgents conclusion.
- Delivery safety still passes only through the existing validator chain.

### Phase 3: Parent Runtime Cutover

Goal: schedule TradingAgents-primary jobs as first-class OpenClaw runtime lanes.

Changes:

- Add or migrate parent cron job payloads for TradingAgents-primary report modes.
- Keep Discord delivery through OpenClaw delivery, not direct TradingAgents output.
- Export parent runtime mirrors and snapshots in finance repo.

Acceptance:

- Parent runtime job has observed successful TradingAgents-primary artifact generation.
- Missing modules/auth in cron environment are eliminated or surfaced before delivery.
- Rollback switch restores finance-primary report behavior.

## Test Plan

Unit tests:

- runtime readiness uses the same provider/auth/module policy as scheduled jobs
- TradingAgents-required mode blocks delivery on missing primary decision
- primary validator rejects broker/order/execution language outside quarantined raw fields
- renderer prefers TradingAgents primary decision only when the feature flag is enabled
- finance deterministic contradiction is shown rather than suppressed

Integration tests:

- local full TradingAgents-primary dry run writes primary decision, validation, report envelope, decision log, reader bundle, and safety report
- scheduled-mode dry run fails closed when TradingAgents runtime is unavailable
- parent runtime mirror captures the new job/prompt/contract

## Risk Register

Risk: TradingAgents emits buy/sell/position language that finance currently quarantines.
Mitigation: translate into review-only thesis/risk language before report rendering; keep raw signal in sanitized machine fields only.

Risk: cron runtime uses a different Python environment from local readiness.
Mitigation: make readiness part of every scheduled run and fail closed for TradingAgents-required modes.

Risk: finance fallback hides TradingAgents outage.
Mitigation: introduce explicit required/optional policy by mode; primary modes must not silently fallback.

Risk: contract drift between parent runtime and finance mirrors.
Mitigation: refresh `export_parent_runtime_mirror.py`, `export_openclaw_runtime_snapshot.py`, and relevant audits in the same commit as runtime changes.

## Rejected Options

Rejected: keep TradingAgents as sidecar and merely increase cadence | does not satisfy the new architecture direction and keeps finance as primary cognition.

Rejected: let TradingAgents deliver directly to Discord | bypasses existing product validator, delivery safety, decision log, and review-only guardrails.

Rejected: delete finance judgment/render pipeline immediately | too much blast radius; finance still owns deterministic context, safety, and audit surfaces.

Rejected: silent finance fallback in TradingAgents-primary mode | hides the exact failure the operator needs to see.

## Final Verdict

Go for Phase 0 and Phase 1 implementation: complete.

Go for Phase 2 and Phase 3 implementation: complete behind explicit switches and a live parent runtime lane.

Go for default production enablement: true for `finance-tradingagents-primary-review-v1` after live cutover verification on 2026-04-27.

Recommended next action:

1. Review the Phase 0 through Phase 3 diff plus proof artifacts.
2. Observe the first scheduled live run on Tuesday 2026-04-28.
3. Roll back by disabling `finance-tradingagents-primary-review-v1` or removing the three `OPENCLAW_TRADINGAGENTS_PRIMARY_*` env switches.

## Resume Closeout: 2026-04-27

Completed in this resume:

- Phase 0 fail-closed policy now treats `immediate-alert` as TradingAgents-required by mode, not by trusting a persisted `required` flag.
- Missing `state/tradingagents/report-refresh-status.json` now suppresses `immediate-alert` with `tradingagents_refresh_missing` instead of allowing stale sidecar context to look fresh.
- Required refresh success remains bound to parsed `run_id` plus same-run context pack binding.
- TradingAgents runtime readiness re-exec evidence confirms `/opt/homebrew/bin/python3` enters `/Users/leofitz/miniconda3/bin/python3`.
- Phase 1 primary advisory artifacts exist behind default-off renderer consumption: `latest-primary-decision.json`, `primary-validation.json`, and `primary-runtime-status.json`.

Verification evidence:

- `python3 -m pytest -q tests` -> 433 passed, 2 known Python 3.14 dependency warnings.
- `python3 -m compileall -q scripts tools tests` -> pass.
- `python3 tools/audit_operating_model.py` -> pass.
- `python3 tools/audit_benchmark_boundary.py` -> pass.
- `python3 tools/audit_parent_dependency_drift.py` -> pass, changed_count 0.
- `python3 tools/check_tradingagents_upstream_lock.py` -> pass.
- `python3 tools/audit_tradingagents_upstream_authority.py` -> pass.
- Report path validation through context pack, judgment fallback gate, report render, product validator, decision log, delivery safety, announce card, and reader bundle -> pass.
- `/opt/homebrew/bin/python3 scripts/tradingagents_runtime_readiness.py` -> pass, runtime python `/Users/leofitz/miniconda3/bin/python3`.

Remaining gates:

- Phase 2 report cognition order is implemented but not default; it requires explicit `OPENCLAW_TRADINGAGENTS_PRIMARY_RUNTIME_ENABLED=1` / `OPENCLAW_TRADINGAGENTS_PRIMARY_RENDER_ENABLED=1`.
- Phase 3 parent runtime cutover lane exists as `finance-tradingagents-primary-review-v1` and is now `enabled:true`.
- `review_runtime_gaps.py` still records existing gaps: `ibkr_client_portal_watchlist_sync_not_fresh` and `parent_market_ingest_dependency_external_to_repo`.

## Resume Closeout: 2026-04-27 Phase 2/3

Completed after Phase 1:

- `finance_llm_context_pack.py` now marks `primary_advisory_cognition` when `OPENCLAW_TRADINGAGENTS_PRIMARY_RUNTIME_ENABLED=1`.
- `judgment_envelope_gate.py` records `tradingagents_primary_gate` without mutating the strict JudgmentEnvelope schema.
- `finance_decision_report_render.py` renders TradingAgents primary review first when enabled, then finance deterministic validation.
- Stale or mismatched primary decisions are not rendered as primary; they become explicit `tradingagents_unavailable` fallback.
- `OPENCLAW_TRADINGAGENTS_PRIMARY_REQUIRED=1` makes the cron-facing report job fail closed when the same-run primary decision is missing.
- Parent cron now includes live job `finance-tradingagents-primary-review-v1` with OpenClaw-managed Discord delivery and rollback switches.

Additional verification evidence:

- `python3 -m pytest -q tests` -> 441 passed, 2 known Python 3.14 dependency warnings.
- Primary-runtime local report path with env switches through context pack, judgment gate, renderer, product validator, decision log, delivery safety, announce card, and reader bundle -> pass.
- `python3 tools/audit_parent_dependency_drift.py` -> pass, changed_count 0.

## Live Cutover Closeout: 2026-04-27

Completed after user approval to go live:

- Parent cron job `finance-tradingagents-primary-review-v1` is `enabled:true`.
- Schedule is `35 8 * * 1-5` in `America/Chicago`, with OpenClaw-managed Discord announce delivery.
- Job command keeps all three primary switches together: `OPENCLAW_TRADINGAGENTS_PRIMARY_RUNTIME_ENABLED=1`, `OPENCLAW_TRADINGAGENTS_PRIMARY_RENDER_ENABLED=1`, and `OPENCLAW_TRADINGAGENTS_PRIMARY_REQUIRED=1`.
- Cron prompt now identifies the lane as `live cutover lane`.
- Rollback remains disabling the parent job or removing the three primary env switches.

Live verification evidence:

- Calendar check: Tuesday 2026-04-28 is a normal XNYS trading day with 09:30 ET open, no holiday, and no early close in the local exchange calendar.
- `/opt/homebrew/bin/python3 scripts/tradingagents_runtime_readiness.py` -> pass, runtime python `/Users/leofitz/miniconda3/bin/python3`.
- Primary-required live run -> pass with TradingAgents run `ta:1dc5480798eb5f8d`.
- Primary decision binding: `AAPL cautious_review`, current packet hash `sha256:1b9187b16255b136fcd32f68588f17758f4f8147639ec9f2e39130ac9f36ecf1`.
- Report envelope: `tradingagents_primary_runtime_enabled=true`, `tradingagents_primary_decision_enabled=true`, `tradingagents_primary_finance_validation=downgraded_by_deterministic_gate`, report hash `sha256:8d6e7745600de20c983fc3dfa6690cb22624e71690c9d7d5acf2dd82e324b762`.
- Product validator -> pass; delivery safety -> pass with zero blocking reasons.
- Final verification: `python3 -m pytest -q tests` -> 441 passed, 2 known Python 3.14 dependency warnings; `python3 -m compileall -q scripts tools tests && git diff --check` -> pass.

## Finance Downgrade Closeout: 2026-04-27

Completed after operator requested less finance narration and more TradingAgents content:

- Discord primary title now uses `TradingAgents｜TradingAgents Primary` when a validated primary decision is available.
- `finance_decision_report_render.py` now surfaces TradingAgents advisor summary, bull case, bear/invalidator case, risk debate, required confirmations, source gaps, and final review boundary before finance sections.
- Finance is explicitly labeled as a safety shell: packet binding, deterministic downgrade, validator, decision log, and delivery safety.
- Product validation accepts TA-primary reports as a distinct axis instead of requiring the old finance opportunity-first axis.
- TradingAgents primary artifacts now carry `decision_trace` and `final_review_boundary`.
- `tradingagents_runner.py` disables the upstream Trader/order node and final Portfolio Manager/action node by default, replacing them with `ORDER_AGENT_DISABLED_REVIEW_HYPOTHESIS` and `ORDER_AGENT_DISABLED_FINAL_REVIEW`, so the primary boundary is structural before text validation.
- TradingAgents validator/translator still blocks near-action language as a secondary guard, including reallocate/proceeds, hold-through timing, entry/exit zones, price/upside/downside targets, and explicit execution timing.
- TradingAgents primary `decision_trace` now includes compact analyst readout, research-debate readout, risk readout, required confirmations, source gaps, `order_agent_disabled=true`, `final_action_manager_disabled=true`, and final review boundary.

Live verification evidence:

- Recompiled current primary run `ta:0fc6c91ed7474675` after stricter sanitization.
- Primary-required live run after order/final-action disable: `ta:4fa352333c80a37d`; raw run artifact records `order_agent_disabled=true` and `final_action_manager_disabled=true`.
- Current report hash after order/final-action disable and pre-action risk readout cleanup: `sha256:0854f01a34f2257c0ba6fb019015c6eb0d0c294ae6d79aa0d7adb0e54853e93a`.
- Product validator -> pass, 0 errors, 0 warnings.
- Decision log -> pass with `execution_decision=none`.
- Delivery safety -> pass with zero blocking reasons.
- Report action-language scan for `ORDER_AGENT_DISABLED_FINAL_REVIEW`, `Action Plan`, `trim`, `immediately`, `rebuild`, `liquidation`, `get out`, and `exit` -> no matches.
- Targeted regression: `python3 -m pytest -q tests/test_tradingagents_advisory_translate.py tests/test_finance_llm_context_pack_tradingagents.py tests/test_judgment_context_pack_gate.py tests/test_thesis_delta_report_render.py tests/test_tradingagents_request_packet.py tests/test_tradingagents_runner_isolation.py tests/test_tradingagents_surface_compiler.py tests/test_tradingagents_bridge_validator.py` -> 38 passed.
