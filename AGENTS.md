# OpenClaw Finance Subsystem - Agent Instructions

This repository is an **OpenClaw-embedded finance subsystem**.

It is not a standalone trading bot, not a generic Python report runner, and not a terminal/dashboard product. It runs as one finance lane inside the local OpenClaw runtime at:

- `/Users/leofitz/.openclaw`
- parent workspace: `/Users/leofitz/.openclaw/workspace`
- finance repo: `/Users/leofitz/.openclaw/workspace/finance`

The GitHub repository mirrors the finance subsystem code and sanitized runtime snapshots. GitHub reviewers cannot see live local state, secrets, raw Flex XML, or the real OpenClaw cron database unless those facts are exported into `docs/openclaw-runtime/`.

## First Read

For a zero-context agent, read these files before changing code:

1. `docs/mainline-closeout.md`
2. `docs/openclaw-subsystem.md`
3. `docs/operating-model.md`
4. `docs/job-cognition-surface-plan.md`
5. `docs/verification.md`
6. `docs/openclaw-runtime/finance-cron-jobs.json`
7. `docs/openclaw-runtime/finance-job-prompt-contract.json`
8. `docs/openclaw-runtime/snapshot-manifest.json`

If you are changing packet/wake/judgment semantics, also read:

- `docs/openclaw-runtime/contracts/finance-openclaw-runtime-contract.md`
- `docs/openclaw-runtime/contracts/finance-report-contract.md`
- `docs/openclaw-runtime/contracts/thesis-spine-contract.md`
- `docs/openclaw-runtime/contracts/judgment-contract.md`
- `docs/openclaw-runtime/contracts/wake-policy.md`
- `docs/openclaw-runtime/contracts/risk-gates.md`

## Authority Order

For active runtime behavior, use this order:

1. Live OpenClaw runtime config outside this repo, especially `/Users/leofitz/.openclaw/cron/jobs.json`
2. Canonical parent workspace contracts and schemas under `/Users/leofitz/.openclaw/workspace/systems` and `/Users/leofitz/.openclaw/workspace/schemas`
3. Deterministic scripts in this repo and parent `services/market-ingest`
4. Sanitized snapshots in `docs/openclaw-runtime/`
5. Explanatory docs in this repo

Do not treat `legacy/report-v1/REPORT_TEMPLATE.md`, old direct renderers, old selected-envelope paths, or compatibility packet prose as active authority.

## Active User-Visible Path

The active user-visible finance path is:

```text
OpenClaw cron finance-premarket-brief
-> scripts/finance_llm_context_pack.py
-> JudgmentEnvelope candidate or deterministic no-trade fallback
-> scripts/judgment_envelope_gate.py
-> scripts/finance_decision_report_render.py
-> scripts/finance_report_product_validator.py
-> scripts/finance_decision_log_compiler.py
-> scripts/finance_report_delivery_safety.py
-> Discord announce only if safety passes
```

The final report must come from `finance-decision-report-envelope.json` after product validation, decision log, and delivery safety. Do not hand-write user-visible market reports.

## Review-Only Boundary

Finance is review-only.

Allowed:

- scan evidence candidates
- compile typed packets and wake decisions
- produce `JudgmentEnvelope` review artifacts
- render product reports after validation
- write decision logs and replay/telemetry
- produce sidecar research artifacts

Forbidden:

- place trades
- call broker execution APIs
- set `live_authority=true`
- bypass delivery safety
- mutate thresholds automatically from LLM output
- store raw feeds/news/latest market state in standing memory surfaces
- expose account identifiers, raw Flex XML, secrets, or raw local credentials

## Thesis Spine

The subsystem now works around persistent Thesis Spine objects:

- `WatchIntent`
- `ThesisCard`
- `ScenarioCard`
- `OpportunityQueue`
- `InvalidatorLedger`

These objects live in `finance/state/` during runtime and are described by contracts/schemas in `docs/openclaw-runtime/`.

Important rule:

`state/llm-job-context/*.json` is a **non-authoritative view cache**. It helps LLM jobs reason over compact context, but it is not canonical state. Canonical state remains typed packets, wake decisions, judgment envelopes, Thesis Spine state, validators, decision logs, and safety gates.

## OpenClaw Jobs

Current finance jobs:

- `finance-premarket-brief`: enabled, user-visible report orchestrator, Discord announce
- `finance-subagent-scanner`: enabled, market-hours scanner, no delivery
- `finance-subagent-scanner-offhours`: enabled, off-hours scanner, no delivery
- `finance-weekly-learning-review`: enabled, weekly system review, Discord announce
- `finance-thesis-sidecar`: disabled/manual, artifact-only, delivery none

Do not edit `/Users/leofitz/.openclaw/cron/jobs.json` without running the Mars cron gate from the parent workspace:

```bash
cd /Users/leofitz/.openclaw/workspace-neptune
.venv/bin/python -m harness.cli gate quick --agent mars modify_cron_jobs
```

If the gate does not return `ALLOW`, stop and report the blocker.

## Scanner Job Rules

Only when acting as `finance-subagent-scanner` or `finance-subagent-scanner-offhours`:

- Do not send user messages.
- Read `state/llm-job-context/scanner.json` first.
- Write scanner observations to `finance/buffer/*.json`.
- Run only deterministic closure scripts:
  - `/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_worker.py`
  - `/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/gate_evaluator.py`
- Do not treat held/watchlist symbols as `unknown_discovery`.
- Preserve `object_links`, `supports`, `conflicts_with`, `confirmation_needed`, and `unknown_discovery_exhausted_reason`.

## Report Orchestrator Rules

Only when acting as `finance-premarket-brief`:

- Run `finance_llm_context_pack.py`.
- Read `state/llm-job-context/report-orchestrator.json`.
- The LLM may write only `state/judgment-envelope-candidate.json`.
- Candidate `evidence_refs` must be a subset of context-pack `allowed_evidence_refs`; `judgment_envelope_gate.py --context-pack ...` enforces this.
- Do not write final prose yourself.
- Output only the validated product markdown if `finance_report_delivery_safety.py` passes.
- If safety fails, output only the health-only markdown.

## Sidecar Rules

`finance-thesis-sidecar` must remain disabled/manual unless the user explicitly requests enabling it.

It may run existing artifact scripts:

- `scripts/thesis_research_packet.py`
- `scripts/custom_metric_compiler.py`
- `scripts/scenario_card_builder.py`
- `scripts/thesis_research_sidecar.py`

It must not send Discord messages, mutate thresholds, execute trades, or produce final market recommendations.

## Reviewer Visibility

After runtime-facing changes, refresh sanitized snapshots:

```bash
python3 tools/export_openclaw_runtime_snapshot.py
python3 tools/export_parent_dependency_inventory.py
python3 tools/audit_operating_model.py
python3 tools/audit_parent_dependency_drift.py
python3 tools/export_wake_threshold_attribution.py
python3 tools/score_report_usefulness.py
python3 tools/review_runtime_gaps.py
```

Commit updated `docs/openclaw-runtime/` snapshots so GitHub reviewers can see:

- cron job prompt hashes
- prompt contract booleans
- parent dependency hashes
- runtime contracts and schemas
- telemetry summaries

## Verification

Before claiming completion, run the relevant subset from `docs/verification.md`.

For most changes, run at minimum:

```bash
python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
```

For report-path changes, also run:

```bash
python3 scripts/finance_llm_context_pack.py
python3 scripts/judgment_envelope_gate.py --allow-fallback --adjudication-mode scheduled_context --context-pack state/llm-job-context/report-orchestrator.json
python3 scripts/finance_decision_report_render.py
python3 scripts/finance_report_product_validator.py
python3 scripts/finance_decision_log_compiler.py
python3 scripts/finance_report_delivery_safety.py
```

Do not trigger a Discord-delivering cron job as a "test" unless the user explicitly asks for a live delivery.
