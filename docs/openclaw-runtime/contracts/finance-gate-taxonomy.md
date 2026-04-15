# Finance Gate Taxonomy

Finance has distinct gate layers. They must not be collapsed into one vague "gate" in code, prompts, audit reports, or user-facing reports.

## 1. Market Candidate Gate

Artifact:

- `finance/state/report-gate-state.json`

Primary implementation:

- `finance/scripts/gate_evaluator.py`

Purpose:

- Decide whether accumulated scanner observations justify a report candidate.
- Evaluate urgency, importance, novelty, cumulative value, cooldowns, decay, and stale scan guard.

User-facing rule:

- Never expose raw phrases such as `thresholds not met`.
- Translate gate holds into concise Chinese context or do not send a market report.

## 2. Wake / Dispatch Gate

Artifacts:

- `finance/state/latest-wake-decision.json`
- `finance/state/wake-dispatch-state.json`

Primary implementations:

- `services/market-ingest/wake_policy/policy.py`
- `finance/scripts/wake_dispatcher.py`

Purpose:

- Route typed packet updates into one of `NO_WAKE`, `PACKET_UPDATE_ONLY`, `ISOLATED_JUDGMENT_WAKE`, or `OPS_ESCALATION`.
- Apply cooldown and daily cap discipline.

Legacy bridge:

- `gate_evaluator.py` may bridge legacy short/core/immediate thresholds into the active OpenClaw report orchestrator when canonical wake dispatch persists only.
- This bridge does not restore the old renderer path.

## 3. Judgment Gate

Artifacts:

- `finance/state/judgment-envelope.json`
- `finance/state/judgment-validation.json`
- `finance/state/judgment-envelope-gate-report.json`

Primary implementation:

- `finance/scripts/judgment_envelope_gate.py`

Purpose:

- Ensure model-mediated or fallback judgments bind to packet hash, evidence refs, policy version, and model id.
- Enforce adjudication-mode limits.
- Prevent quarantined / non-support evidence from becoming judgment support.

## 4. Product Report Gate

Artifacts:

- `finance/state/finance-decision-report-envelope.json`
- `finance/state/finance-report-product-validation.json`

Primary implementations:

- `finance/scripts/finance_decision_report_render.py`
- `finance/scripts/finance_report_product_validator.py`

Purpose:

- Convert JudgmentEnvelope + packet context into a user-visible report.
- Validate product shape, banned phrases, no-execution language, evidence retention in envelope, and report noise controls.

Deprecated replacements:

- `finance/scripts/finance_report_validator.py`
- `finance/scripts/finance_deterministic_report_render.py`
- `finance/scripts/quality_gate.py`

These are compatibility/legacy surfaces and do not define active delivery eligibility.

## 5. Decision Log / Delivery Safety Gate

Artifacts:

- `finance/state/finance-decision-log-report.json`
- `finance/state/report-delivery-safety-check.json`
- `finance/state/report-delivery-health-only.md`

Primary implementations:

- `finance/scripts/finance_decision_log_compiler.py`
- `finance/scripts/finance_report_delivery_safety.py`

Purpose:

- Record the machine truth chain for replay/audit.
- Fail closed if judgment, product validation, decision log, or delivery safety is missing or invalid.
- Ensure market reports remain review-only.

User-facing rule:

- If this gate fails, output health-only/system-status content. Do not output market analysis.

## Naming Rule

Every finance report failure must name the failed layer:

- `market_candidate_gate`
- `wake_dispatch_gate`
- `judgment_gate`
- `product_report_gate`
- `decision_log_gate`
- `delivery_safety_gate`
