# OpenClaw Finance Information Dominance Stack

Subtitle: Source-to-Campaign Intelligence Fabric.

This plan upgrades OpenClaw Finance from a report/run-centered review system into a source-to-campaign intelligence operating system. The active authority chain is not replaced. The upgrade adds shadow substrates, campaign projections, board surfaces, and follow-up routing around the existing typed evidence and safety path.

## Phase 0 Decision

Phase 0 is a freeze-and-map phase. It prepares the migration, records the authority chain, installs RALPLAN gates for every later phase, and adds baseline tests. It must not change active runtime behavior.

Status: prepared.

Active-runtime posture:
- No cron changes.
- No gateway restart/reload.
- No Discord channel or adapter changes.
- No wake threshold mutation.
- No source promotion behavior change.
- No report delivery behavior change.
- No execution authority change.

## Why This Upgrade Exists

The current finance system has a usable review-only typed chain, but the operator product is still too report-shaped. It can tell the operator what this run said, but it does not yet operate like an information office that manages source quality, context gaps, peacetime accumulation, source ROI, and campaign lifecycle.

The target system is not a standalone terminal and not a chat app. It is a private market intelligence bureau embedded in OpenClaw:
- source-aware
- point-in-time replayable
- campaign-centric
- Discord-native
- review-only
- portfolio-attached
- multi-clock

## Explored Current Facts

Fact: Parent market-ingest already owns load-bearing source and packet functions.

Relevant parent files:
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/config/source-registry.json`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/source_promotion.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/semantic_normalizer.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/temporal_alignment/alignment.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/packet_compiler/compiler.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/wake_policy/policy.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/validator/judgment_validator.py`

Fact: Current source registry is a v1 allowlist/quality registry, not a source economy.

Missing source registry dimensions:
- source lane
- modality
- asset horizon
- lane-specific freshness budget
- expected latency
- coverage universe
- uniqueness prior
- lineage policy
- point-in-time policy
- compliance class
- redistribution policy
- cost class
- promotion policy

Fact: Finance scanner/worker still compresses context early.

[`finance_worker.py`](../../scripts/finance_worker.py) currently normalizes scanner observations into fields such as `theme`, `urgency`, `importance`, `novelty`, `cumulative_value`, and `summary`. That derived view is useful, but it is too lossy to become the future canonical substrate.

Fact: Campaign OS skeleton already exists.

Existing files:
- [`undercurrent_compiler.py`](../../scripts/undercurrent_compiler.py)
- [`campaign_projection_compiler.py`](../../scripts/campaign_projection_compiler.py)
- [`finance_campaign_cache_builder.py`](../../scripts/finance_campaign_cache_builder.py)
- [`finance_followup_context_router.py`](../../scripts/finance_followup_context_router.py)
- [`campaign-projection-contract.md`](contracts/campaign-projection-contract.md)
- [`undercurrent-card-contract.md`](contracts/undercurrent-card-contract.md)
- [`followup-answer-contract.md`](contracts/followup-answer-contract.md)

Fact: Wake and threshold systems currently coexist.

The canonical wake policy emits `NO_WAKE`, `PACKET_UPDATE_ONLY`, `ISOLATED_JUDGMENT_WAKE`, or `OPS_ESCALATION`. The legacy gate evaluator still has threshold logic and a bridge that can dispatch the active report orchestrator. Any future undercurrent/campaign work must respect both surfaces until the bridge is explicitly retired or narrowed in a later RALPLAN.

## Non-Negotiable Invariants

1. Review-only boundary remains intact.
2. LLM prose is not production evidence.
3. Source candidates must pass deterministic promotion before becoming evidence.
4. Context packs are view caches, not authority.
5. `ContextPacket -> WakeDecision -> JudgmentEnvelope -> product envelope -> validator -> decision log -> delivery safety` remains the user-visible market-report authority chain.
6. Discord boards and campaign threads are operator surfaces, not new authority layers.
7. Follow-up answers are explain/compare/challenge/source-trace only; they cannot create new judgments.
8. Machine provenance remains in artifacts and logs; operator surfaces suppress raw hashes and raw refs.
9. Phase cutovers must be reversible.
10. Every phase after Phase 0 requires a RALPLAN decision record before implementation.

## Authority Chain Map

Active market-report authority remains:

```text
SourceCandidate / EvidenceRecord
  -> ContextPacket
  -> WakeDecision
  -> JudgmentEnvelope
  -> finance-decision-report-envelope.json
  -> finance_report_product_validator.py
  -> finance_decision_log_compiler.py
  -> finance_report_delivery_safety.py
  -> OpenClaw Discord delivery
```

Future source-to-campaign additions must attach as shadow or projection layers until explicitly cut over:

```text
EvidenceAtom shadow substrate
  -> ClaimGraph shadow substrate
  -> ContextGap shadow substrate
  -> UndercurrentCard projection
  -> CampaignProjection projection
  -> Discord board/thread operator surface
  -> verb-specific follow-up context routing
```

## RALPLAN Gate Protocol

`rafplan` in the operator instruction is implemented here as RALPLAN. Every phase after Phase 0 must produce a RALPLAN decision record before implementation starts.

Required record path pattern:

```text
docs/openclaw-runtime/ralplan/phase-<n>-<slug>-ralplan.md
```

Required RALPLAN sections:
- Task statement
- Current facts from local exploration
- Principles
- Decision drivers
- Viable options
- Rejected options
- Selected plan
- Authority boundary impact
- Files likely touched
- Data migration or shadow-mode posture
- Test plan
- Rollback plan
- Acceptance criteria
- Residual risks
- Explicit go/no-go for implementation

Required rule:
- If the RALPLAN says `go_for_implementation: false`, no code changes for that phase.
- If a phase touches parent runtime, cron jobs, gateway config, or Discord adapter behavior, it must also pass the applicable parent gate check before implementation.
- If a phase adds source lanes, private/human/field data, or compliance-sensitive metadata, it must explicitly classify compliance and redistribution boundaries.

## Phase Matrix

### Phase 0: Boundary Freeze, Map, Baseline

Purpose:
- Establish migration authority and testing guardrails.
- Record phase map and RALPLAN gates.
- Verify current repo still passes baseline tests.

Allowed changes:
- Docs.
- Machine-readable maps.
- Tests.
- Snapshot manifest inclusion.

Forbidden changes:
- Active cron changes.
- Parent runtime changes.
- Gateway restart/reload.
- Discord delivery behavior changes.
- Wake threshold changes.
- Source promotion behavior changes.

Acceptance:
- Plan exists.
- Machine map exists and validates.
- Tests assert every later phase requires RALPLAN.
- Active runtime cutover flags are false.
- Existing Campaign/Discord/report tests still pass.

### Phase 1: Source Registry 2.0 + Source Health

Purpose:
- Upgrade source registry into lane-aware source economy.
- Add source health and lane-specific freshness budgets.

Primary touchpoints:
- Parent `services/market-ingest/config/source-registry.json`
- Parent `source_promotion.py`
- Parent `semantic_normalizer.py`
- Parent schemas
- Finance runtime snapshots

Shadow posture:
- Source health may be computed and logged.
- Source health must not change wake dispatch or report delivery until separately cut over.

Acceptance:
- Every source has lane, modality, horizon, freshness budget, compliance class, redistribution policy, and promotion policy.
- Source health degradation is visible in packet/report context but does not silently alter authority.
- Existing parent ingest tests pass.

### Phase 2: EvidenceAtom / ClaimGraph / ContextGap Shadow Substrate

Purpose:
- Stop losing raw context at early scanner compression.
- Parallel-write source atoms, claim atoms, and context gaps.

Primary touchpoints:
- [`finance_worker.py`](../../scripts/finance_worker.py)
- New `source_atom_compiler.py`
- New `claim_graph_compiler.py`
- New `context_gap_compiler.py`
- Parent packet compiler source manifest

Shadow posture:
- Existing `accumulated` observation consumers remain active.
- Atom/claim/gap outputs are non-authoritative until later RALPLAN cutover.

Acceptance:
- Can trace source -> atom -> claim -> context gap -> campaign/report projection.
- No existing report path regression.
- Shadow output deterministic.

### Phase 3: Undercurrent Engine

Purpose:
- Make `PACKET_UPDATE_ONLY` mutate peacetime/risk intelligence state instead of disappearing.

Primary touchpoints:
- [`undercurrent_compiler.py`](../../scripts/undercurrent_compiler.py)
- [`event_watcher.py`](../../scripts/event_watcher.py)
- [`signal_learner.py`](../../scripts/signal_learner.py)
- [`hypothesis_tracker.py`](../../scripts/hypothesis_tracker.py)
- [`wake_dispatcher.py`](../../scripts/wake_dispatcher.py)

Shadow posture:
- Undercurrents may update boards/state.
- They must not create alert spam or bypass wake policy.

Acceptance:
- Repeated weak signals increase persistence/velocity.
- Cross-lane confirmation and contradiction load affect promotion.
- Source freshness degradation is explicit.

### Phase 4: CampaignProjection 2.0

Purpose:
- Make campaign the operator-facing unit.
- Project thesis, opportunity, invalidator, scenario, capital graph, context gaps, and undercurrents into durable campaign objects.

Primary touchpoints:
- [`campaign_projection_compiler.py`](../../scripts/campaign_projection_compiler.py)
- [`finance_decision_report_render.py`](../../scripts/finance_decision_report_render.py)
- [`finance_decision_log_compiler.py`](../../scripts/finance_decision_log_compiler.py)
- Campaign contracts

Shadow posture:
- Campaign board can be generated and validated.
- Active delivery remains current primary until Discord board adapter is ready.

Acceptance:
- Campaigns have human titles, stages, why-now, why-not-now, capital relevance, known unknowns, source freshness, linked claims/atoms/gaps.
- Handles are secondary aliases, not primary operator objects.

### Phase 5: Discord Campaign Boards

Purpose:
- Turn Discord into campaign board + thread surface, not report spam.

Primary touchpoints:
- Finance board markdown outputs
- Product validator/safety
- Parent Discord delivery adapter
- Parent thread registry/router

Shadow posture:
- Test/private delivery first.
- No production board cutover without rollback switch.

Acceptance:
- Live Board, Peacetime Board, and Risk Board can be updated independently.
- Thread deletion is detected and recoverable.
- Main channel full readability is preserved if threads fail.

### Phase 6: Verb-Specific Follow-up Engine

Purpose:
- Replace generic Q&A with verb-specific, object-specific, evidence-sliced follow-up.

Primary touchpoints:
- [`finance_followup_context_router.py`](../../scripts/finance_followup_context_router.py)
- [`finance_campaign_cache_builder.py`](../../scripts/finance_campaign_cache_builder.py)
- [`finance_llm_context_pack.py`](../../scripts/finance_llm_context_pack.py)
- [`finance_followup_answer_guard.py`](../../scripts/finance_followup_answer_guard.py)
- Parent thread router

Shadow posture:
- Context route and answer guard can validate locally before active Discord thread use.

Acceptance:
- `why`, `challenge`, `compare`, `scenario`, `sources`, and `trace` select different evidence slices.
- Missing data returns `insufficient_data` with a load-bearing gap.
- No raw thread history as memory.

### Phase 7: Source ROI / Campaign Learning

Purpose:
- Evaluate source/campaign usefulness, not just report usefulness.

Primary touchpoints:
- [`finance_decision_log_compiler.py`](../../scripts/finance_decision_log_compiler.py)
- [`score_report_usefulness.py`](../../tools/score_report_usefulness.py)
- [`review_runtime_gaps.py`](../../tools/review_runtime_gaps.py)
- New source ROI/context coverage scripts

Shadow posture:
- Learning emits recommendations and metrics only.
- No automatic threshold mutation.

Acceptance:
- Source contribution and campaign outcome metrics exist.
- Peacetime-to-live conversion and false positive rates are tracked.
- Weekly learning remains review-only.

### Phase 8: Active Cutover

Purpose:
- Turn proven shadow surfaces into production operator surfaces.

Primary touchpoints:
- Parent runtime delivery/Discord adapter.
- Finance delivery job fallback behavior.
- Board/thread registries.

Gate posture:
- Requires deliberate RALPLAN.
- Requires parent gate checks if cron/gateway/config changes are involved.
- Requires rollback switches tested before enabling.

Acceptance:
- Worst-case rollback returns to full Discord primary markdown, never route-card-only.
- Board/thread failures do not block main readable report.
- External evidence confirms delivery path.

## Runtime Switch Policy

The following switches are reserved. Phase 0 does not enable them.

```text
SOURCE_ATOM_SHADOW_ENABLED=true
SOURCE_ATOM_ACTIVE_MODE=false
CLAIM_GRAPH_SHADOW_ENABLED=true
CLAIM_GRAPH_ACTIVE_MODE=false
CONTEXT_GAP_SHADOW_ENABLED=true
CONTEXT_GAP_ACTIVE_MODE=false
UNDERCURRENT_BOARD_ENABLED=false
CAMPAIGN_BOARD_ENABLED=false
DISCORD_BOARDS_ENABLED=false
DISCORD_THREADS_ENABLED=false
FOLLOWUP_ROUTER_ENABLED=false
SOURCE_ROI_LEARNING_ENABLED=false
```

Switch rules:
- Shadow switches can be enabled by repo-local code if they only write local state and do not affect delivery.
- Active-mode switches require RALPLAN plus verification.
- Discord/gateway/cron switches require parent runtime gate checks.

## Rollback Floor

The minimum acceptable rollback is:
- Disable board/thread/follow-up/router switches.
- Continue delivering full `discord_primary_markdown` or artifact markdown.
- Never deliver route-card-only as primary.
- Preserve decision log and audit artifacts.
- Preserve review-only boundary.

## Phase 0 Verification

Required local commands:

```bash
python3 -m json.tool docs/openclaw-runtime/information-dominance-stack-map.json >/dev/null
python3 -m pytest -q tests/test_information_dominance_phase0.py
python3 -m pytest -q tests/test_campaign_projection.py tests/test_discord_operator_surfaces.py tests/test_llm_context_pack.py
python3 -m compileall -q scripts tools tests
python3 tools/audit_operating_model.py
python3 tools/audit_benchmark_boundary.py
```

Phase 0 is complete only when these pass and no active runtime file has been changed.
