# OpenClaw Finance Subsystem — Agent Instructions

OpenClaw-embedded finance subsystem. Review-only capital governance — never executes trades.

## Workspace Map

```
finance/
├── scripts/                         # Deterministic runtime scripts
│   ├── atomic_io.py                 # Shared IO helpers
│   ├── thesis_spine_util.py         # Shared spine helpers
│   │
│   ├── # ── Data Ingestion ──
│   ├── price_fetcher.py
│   ├── watchlist_resolver.py
│   ├── portfolio_fetcher.py / portfolio_resolver.py / portfolio_flex_*.py
│   ├── broad_market_proxy_fetcher.py
│   ├── options_flow_proxy_fetcher.py
│   ├── sec_discovery_fetcher.py / sec_filing_semantics.py
│   │
│   ├── # ── Thesis Spine Compilers ──
│   ├── watch_intent_compiler.py          → state/watch-intent.json
│   ├── thesis_registry_compiler.py       → state/thesis-registry.json
│   ├── scenario_card_builder.py          → state/scenario-cards.json
│   ├── opportunity_queue_builder.py      → state/opportunity-queue.json
│   ├── invalidator_ledger_compiler.py    → state/invalidator-ledger.json
│   │
│   ├── # ── Capital Competition Engine ──
│   ├── capital_graph_compiler.py         → state/capital-graph.json
│   ├── scenario_exposure_compiler.py     → state/scenario-exposure-matrix.json
│   ├── displacement_case_builder.py      → state/displacement-cases.json
│   ├── capital_agenda_compiler.py        → state/capital-agenda.json
│   ├── capital_committee_packet.py       → state/capital-committee-packet.json
│   ├── capital_committee_sidecar.py      → state/committee-memos/*.json
│   ├── committee_memo_merge.py           → state/capital-agenda-annotated.json
│   │
│   ├── # ── Report Pipeline ──
│   ├── finance_llm_context_pack.py       → state/llm-job-context/*.json
│   ├── finance_report_packet.py          → state/report-input-packet.json
│   ├── judgment_envelope_gate.py         → state/judgment-envelope.json
│   ├── finance_decision_report_render.py → state/finance-decision-report-envelope.json
│   ├── finance_report_product_validator.py
│   ├── finance_decision_log_compiler.py
│   ├── finance_report_delivery_safety.py
│   │
│   ├── # ── Output Surfaces ──
│   ├── announce_card_compiler.py         → state/announce-card.json
│   ├── finance_report_reader_bundle.py   → state/report-reader/*.json
│   ├── finance_followup_answer_guard.py  → state/followup-answer-validation.json
│   │
│   ├── # ── Scanner / Worker ──
│   ├── finance_worker.py
│   ├── gate_evaluator.py
│   ├── native_scanner_market_hours.py / native_scanner_offhours.py
│   │
│   └── # ── Research Sidecar ──
│       ├── thesis_research_packet.py / thesis_research_sidecar.py
│       ├── tradingagents_request_packet.py / tradingagents_sidecar_job.py
│       ├── tradingagents_runner.py / tradingagents_advisory_translate.py
│       ├── tradingagents_bridge_validator.py / tradingagents_surface_compiler.py
│       └── custom_metric_compiler.py
│
├── state/                           # Runtime state (not committed)
│   ├── capital-bucket-config.json   # 5-bucket attention budget
│   ├── capital-graph.json           # Deterministic exposure graph
│   ├── capital-agenda.json          # Ranked review-only agenda
│   ├── committee-memos/             # Role-decomposed assessments
│   ├── announce-card.json           # Notification surface
│   ├── report-reader/               # Exploration bundles
│   ├── llm-job-context/             # Non-authoritative view cache (5 roles)
│   └── tradingagents/               # Review-only TradingAgents sidecar state
│
├── tests/                           # pytest suite (84 tests)
├── tools/                           # Audit & snapshot export tools
├── docs/
│   ├── openclaw-runtime/contracts/  # 19 runtime contracts
│   ├── verification.md
│   └── operating-model.md
├── buffer/                          # Scanner observation buffer
├── watchlists/                      # Watchlist source files
└── AGENTS.md                        # ← you are here
```

## Active Report Path

```
cron finance-premarket-brief
→ finance_llm_context_pack.py
→ JudgmentEnvelope candidate or deterministic fallback
→ judgment_envelope_gate.py
→ finance_decision_report_render.py  (--report-mode thesis_delta | capital_delta)
→ finance_report_product_validator.py
→ finance_decision_log_compiler.py
→ finance_report_delivery_safety.py
→ Discord announce only if safety passes
```

**`thesis_delta`** (default): opportunity-expansion-first report.  
**`capital_delta`**: capital-competition-first report. Requires valid `capital-graph.json`; falls back to `thesis_delta` if absent.

## Output Surfaces

The finance subsystem delivers through three separate surfaces:

| Surface | Script | State | Purpose |
|---------|--------|-------|---------|
| **Notification** | `announce_card_compiler.py` | `announce-card.json` | Attention router for Discord. ≤200 chars. |
| **Record** | `finance_decision_report_render.py` | `finance-decision-report-envelope.json` | Canonical report. Unchanged authority chain. |
| **Exploration** | `finance_report_reader_bundle.py` | `report-reader/*.json` | Rehydration bundle for deep-dive. |

**Announce card** replaces the full report as Discord delivery. Contains: `attention_class`, `dominant_object`, `why_now`, `next_decision`, `handles`.

**Reader bundle** converts internal object graph into navigable handles (`T1/O1/I1/S1`). Thread is UI; bundle is memory.

**Followup guard** (`finance_followup_answer_guard.py`) validates deep-dive answers: binding, verb, review-only, structure.

Context pack role `report_followup` provides rehydration context for the review room.

## Capital Competition Engine

Evaluates which theses/opportunities deserve scarce attention slots. Strictly review-only.

**Pipeline:**
```
watch_intent_compiler  (capital_bucket_hint)
→ thesis_registry_compiler  (capital_bucket_ref, competes_with)
→ scenario_card_builder  (exposure_refs, crowding_risk)
→ capital_graph_compiler  (nodes, edges, hedge coverage, utilization)
→ scenario_exposure_compiler  (scenario × bucket matrix)
→ displacement_case_builder  (selective: only genuine overlap/crowding)
→ capital_agenda_compiler  (ranked, capped at 8, max 3 per type)
```

**Rules:**
- All capital objects carry `no_execution=True`
- Compilers are deterministic: same inputs → same `graph_hash`
- Displacement cases are selective — only on genuine overlap, crowding, or hedge gap
- Agenda diversity: max 3 items per `agenda_type`
- Capital pipeline layers on top of Thesis Spine; does not replace it

## Review-Only Boundary

**Allowed:** scan, compile, judge, render, log, produce sidecar artifacts, compile capital graph/agenda, produce committee memos.

**Forbidden:** trade, call broker APIs, set `live_authority=true`, bypass delivery safety, mutate thresholds from LLM output, expose account IDs / Flex XML / secrets.

## OpenClaw Jobs

| Job | Status | Delivery |
|-----|--------|----------|
| `finance-premarket-brief` | enabled | Discord |
| `finance-subagent-scanner` | enabled | none |
| `finance-subagent-scanner-offhours` | enabled | none |
| `finance-weekly-learning-review` | enabled | Discord |
| `finance-thesis-sidecar` | disabled/manual | none |

## Job Rules

**Scanner** (`finance-subagent-scanner*`): No user messages. The active cron entry must call `finance_scanner_job.py`, which runs the deterministic scanner chain and returns one machine stdout line. Read `scanner.json` first. QueryPack is not evidence. Don't treat held/watchlist symbols as `unknown_discovery`.

**Report Orchestrator** (`finance-premarket-brief`): Run `finance_llm_context_pack.py`. LLM writes only `judgment-envelope-candidate.json`. Context pack includes `capital_agenda_items`, `displacement_cases`, `capital_graph_summary`. Do not bypass the deterministic renderer.

**Sidecar** (`finance-thesis-sidecar`): Stays disabled unless user requests. May run thesis spine compilers, capital compilers, and committee sidecar. Committee memos carry `no_execution`, `no_user_delivery`, `no_threshold_mutation`, `no_live_authority_change`. No Discord delivery.

**TradingAgents Sidecar** (manual/local-only until a parent job is explicitly added): may compile request packets, run a review-only TradingAgents subprocess wrapper, translate raw outputs into advisory-only normalized artifacts, and publish only validator-gated reader/context sidecar surfaces under `state/tradingagents/**`. It must not write canonical evidence, mutate wake/thresholds, bypass delivery safety, or send user-visible messages directly.

## First Read

For zero-context: `docs/mainline-closeout.md` → `docs/operating-model.md` → `docs/verification.md` → `docs/openclaw-runtime/snapshot-manifest.json`.

For packet/wake/judgment changes, also read contracts: `finance-openclaw-runtime-contract.md`, `finance-report-contract.md`, `thesis-spine-contract.md`, `judgment-contract.md`, `wake-policy.md`, `risk-gates.md`.

For capital competition changes, also read: `capital-graph-contract.md`, `capital-bucket-contract.md`, `displacement-case-contract.md`, `capital-agenda-contract.md`, `committee-memo-contract.md`.

## Canonical State

`state/llm-job-context/*.json` is a **non-authoritative view cache**. Canonical state = typed packets, wake decisions, judgment envelopes, Thesis Spine objects, capital competition objects, validators, decision logs, safety gates.

## Parent Runtime Mirrors

Finance work often requires edits in the parent OpenClaw workspace outside this repo, for example:
- `/Users/leofitz/.openclaw/cron/jobs.json`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/**`
- `/Users/leofitz/.openclaw/workspace/ops/**`
- `/Users/leofitz/.openclaw/workspace/systems/**`
- `/Users/leofitz/.openclaw/workspace/skills/**`

Whenever a task changes parent workspace files that affect finance behavior, the finance repo must also be updated with reviewer-visible mirrors before commit/push:
- Run `python3 tools/export_parent_runtime_mirror.py` for parent runtime source/cron mirrors.
- Run `python3 tools/export_openclaw_runtime_snapshot.py` for finance cron/model/prompt/runtime snapshots.
- Run the relevant audits (`audit_operating_model.py`, `audit_parent_dependency_drift.py`) when parent dependencies or contracts changed.
- Commit the mirror/snapshot diffs in this repo with the implementation. Do not leave parent-only finance behavior changes invisible to remote reviewers.

## AI Handoff Exoskeleton

This repo includes an AI handoff layer for medium/large future work. It is an exoskeleton, not a replacement for this OpenClaw Finance contract.

- Read `START_HERE.md`, `docs/01_reality_check.md`, and `docs/02_end_to_end_workflow.md` before using the handoff workflow.
- Treat `templates/PROJECT_BRIEF.md`, `templates/PRD.md`, `templates/ARCHITECTURE.md`, `templates/IMPLEMENTATION_PLAN.md`, `templates/VERIFICATION_PLAN.md`, `templates/DECISIONS.md`, `templates/NOT_NOW.md`, `OPEN_QUESTIONS.md`, and `RISKS.md` as the current handoff truth surfaces.
- Use `prompts/01_claude_code_requirements.txt` for requirement-tribunal work and `prompts/02_chatgpt_pro_finalize.txt` for final requirements/architecture lock.
- Use `scripts/build_handoff_zip.py` only to package the guidance/docs/prompts layer. It is not a full source snapshot and must not include raw `state/`, secrets, raw Flex XML, broker account identifiers, or raw licensed/vendor payloads.
- The copied starter-kit `AGENTS.md` is stored at `docs/ai-handoff-starter-AGENTS.md` for reference only. This root `AGENTS.md` remains authoritative.
- Repo-specific integration notes live in `docs/ai-handoff-current-repo-config.md`.

## Verification

```bash
# Minimum
python3 -m pytest -q tests
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py

# Report path
python3 scripts/finance_llm_context_pack.py
python3 scripts/judgment_envelope_gate.py --allow-fallback --adjudication-mode scheduled_context --context-pack state/llm-job-context/report-orchestrator.json
python3 scripts/finance_decision_report_render.py
python3 scripts/finance_report_product_validator.py
python3 scripts/finance_decision_log_compiler.py
python3 scripts/finance_report_delivery_safety.py

# Capital competition
python3 scripts/capital_graph_compiler.py
python3 scripts/scenario_exposure_compiler.py
python3 scripts/displacement_case_builder.py
python3 scripts/capital_agenda_compiler.py

# Output surfaces
python3 scripts/announce_card_compiler.py
python3 scripts/finance_report_reader_bundle.py

# TradingAgents sidecar
python3 tools/check_tradingagents_upstream_lock.py
python3 tools/audit_tradingagents_upstream_authority.py
python3 -m pytest -q \
  tests/test_tradingagents_request_packet.py \
  tests/test_tradingagents_runner_isolation.py \
  tests/test_tradingagents_advisory_translate.py \
  tests/test_tradingagents_bridge_validator.py \
  tests/test_tradingagents_surface_compiler.py \
  tests/test_tradingagents_sidecar_job.py \
  tests/test_finance_llm_context_pack_tradingagents.py \
  tests/test_finance_reader_bundle_tradingagents.py \
  tests/test_followup_context_router_tradingagents.py \
  tests/test_tradingagents_upstream_lock.py \
  tests/test_tradingagents_upstream_authority.py \
  tests/test_export_openclaw_runtime_snapshot_tradingagents.py
```

After runtime changes, refresh snapshots:

```bash
python3 tools/export_openclaw_runtime_snapshot.py
python3 tools/export_parent_runtime_mirror.py
python3 tools/export_parent_dependency_inventory.py
python3 tools/audit_operating_model.py
python3 tools/audit_parent_dependency_drift.py
python3 tools/export_wake_threshold_attribution.py
python3 tools/score_report_usefulness.py
python3 tools/review_runtime_gaps.py
```
