# RALPLAN Phase 2: EvidenceAtom / ClaimGraph / ContextGap Shadow Substrate

Status: approved_for_implementation
Go for implementation: true

Prior commits:
- Phase 0 gate: `19f5501 Prepare information dominance phase gates`
- Phase 1 plan: `9985518 Approve source health phase plan`
- Phase 1 implementation: `fdae2c9 Add shadow source health registry phase`

## Task Statement

Add a shadow substrate that preserves raw-ish source context and derived claims before current report/run compression flattens them into `theme`, `summary`, `urgency`, and `importance`.

Phase 2 must create the plan for later implementation of:
- `EvidenceAtom`
- `ClaimAtom` / `ClaimGraph`
- `ContextGap`

No implementation begins until this RALPLAN is approved.

## Current Facts From Local Exploration

Fact: scanner outputs land in `finance/buffer/*.json` and are consumed by [`finance_worker.py`](../../scripts/finance_worker.py).

Fact: [`finance_worker.py`](../../scripts/finance_worker.py) normalizes each observation into `id`, `ts`, `theme`, `urgency`, `importance`, `novelty`, `cumulative_value`, `summary`, and `sources`, then writes `state/intraday-open-scan-state.json`.

Fact: [`live_finance_adapter.py`](../../../../services/market-ingest/adapters/live_finance_adapter.py) reads accumulated scanner state plus price/SEC/flow/portfolio artifacts, builds case objects, converts them to `SourceCandidate`, runs promotion, and emits promoted `EvidenceRecord` rows.

Fact: [`packet_compiler/compiler.py`](../../../../services/market-ingest/packet_compiler/compiler.py) consumes EvidenceRecord JSONL and writes `latest-context-packet.json` with `accepted_evidence_records`, `evidence_refs`, `source_quality_summary`, and `source_manifest`.

Fact: Phase 1 already added Source Registry v2 and Source Health as shadow/audit metadata in packet `source_manifest`; it does not affect wake/delivery.

Fact: There is no current `state/source-atoms/*.jsonl`, `state/claim-graph.json`, or `state/context-gaps.json`.

Fact: Parent tests already cover source promotion, semantic normalizer, live adapter, temporal alignment, packet compiler, wake policy, source health, and judgment validator.

## Principles

1. Preserve before compressing: raw observation/source context must be parallel-written before it is compressed into report-friendly fields.
2. Shadow-only by default: atoms, claims, and gaps must not become wake/judgment/delivery authority in Phase 2.
3. Deterministic and replayable: same inputs produce same atom IDs, claim IDs, gap IDs, graph hash, and context-gap hash.
4. Traceable upward and downward: future campaigns must trace back to claims and atoms; atoms must trace back to original buffer/source/candidate/evidence refs.
5. Explicit insufficiency beats hallucinated closure: missing lanes or weak claims become ContextGap rows, not generic prose.

## Decision Drivers

1. Avoid early information loss from scanner observation compression.
2. Keep active report/wake chain stable while creating future campaign/follow-up substrate.
3. Minimize parent blast radius by doing initial SourceAtom writes in finance and only adding audit manifests to parent packet compiler if necessary.

## Viable Options

### Option A: Finance-only shadow substrate

Add finance-local compilers:
- `scripts/source_atom_compiler.py`
- `scripts/claim_graph_compiler.py`
- `scripts/context_gap_compiler.py`

`finance_worker.py` invokes SourceAtom parallel-write from buffer/observation payloads. ClaimGraph and ContextGap are compiled from SourceAtoms plus existing finance state/EvidenceRecords where available.

Pros:
- Lowest parent blast radius.
- Easy to test and commit in finance repo.
- Keeps current market-ingest authority untouched.

Cons:
- Claim linkage to SourceCandidate/EvidenceRecord promotion is indirect at first.
- Some parent state refs may need later integration.

### Option B: Finance SourceAtoms + parent live adapter claim/gap derivation

SourceAtoms are written by finance_worker. ClaimGraph and ContextGap are derived in parent `live_finance_adapter.py` during candidate/promotion/evidence generation.

Pros:
- Strongest linkage between SourceCandidate, promotion, EvidenceRecord, claim, and gap.
- Best future trace quality.

Cons:
- Higher parent blast radius.
- More difficult to commit/review because finance repo can only snapshot parent changes.
- Greater risk of accidentally changing EvidenceRecord behavior.

### Option C: Parent market-ingest owns all atom/claim/gap artifacts

Move all Phase 2 artifacts into parent `services/market-ingest` and make finance only snapshot/inventory them.

Pros:
- Clean architectural ownership if market-ingest is considered evidence substrate owner.
- Easier long-term integration with packet compiler.

Cons:
- Too large for Phase 2.
- Increases risk in a dirty parent workspace.
- Moves too much away from finance repo before object model is stable.

## Selected Plan

Choose Option A for Phase 2 implementation.

Rationale: The immediate problem is early loss in scanner/finance_worker compression. Finance-only shadow compilers solve that first with the least blast radius. Parent integration can happen in Phase 3/4 after atom/claim/gap schemas prove useful.

## Rejected Options

Rejected: Option B for this phase | good trace quality but too much parent blast radius for first atom/claim/gap implementation.

Rejected: Option C | premature ownership migration; would make the finance repo dependent on parent implementation before the schema is stable.

Rejected: make ClaimGraph part of `ContextPacket` now | would change active packet hash/semantics and violate shadow-only posture.

Rejected: use an LLM to extract claims in Phase 2 | nondeterministic and would reintroduce prose-as-evidence risk.

## Proposed Object Shapes

### EvidenceAtom

```json
{
  "atom_id": "atom:<stable-hash>",
  "source_id": "source:unknown_web",
  "source_class": "news_policy",
  "source_lane": "news_policy_narrative",
  "published_at": "...",
  "observed_at": "...",
  "ingested_at": "...",
  "event_time": "...",
  "timezone": "UTC",
  "entity_ids": [],
  "symbol_candidates": [],
  "region": null,
  "sector": null,
  "supply_chain_nodes": [],
  "modality": "text|tabular|event|time_series|mixed",
  "raw_ref": "finance-scan:<id>",
  "raw_snippet": "bounded text snippet",
  "raw_uri": null,
  "raw_table_ref": null,
  "language": "unknown|en|zh|...",
  "freshness_budget_seconds": 0,
  "reliability_score": 0.0,
  "uniqueness_score": 0.0,
  "compliance_class": "unknown",
  "redistribution_policy": "unknown",
  "lineage_chain": [],
  "point_in_time_hash": "sha256:...",
  "source_refs": [],
  "no_execution": true
}
```

### ClaimAtom

```json
{
  "claim_id": "claim:<stable-hash>",
  "atom_id": "atom:<stable-hash>",
  "subject": "TSLA|theme:...|source:...",
  "predicate": "moves|files|conflicts|supports|mentions|updates",
  "object": "bounded object text",
  "magnitude": null,
  "unit": null,
  "direction": "bullish|bearish|neutral|ambiguous|not_applicable",
  "horizon": "intraday|multi_day|quarterly|structural|unknown",
  "certainty": "confirmed|probable|weak|unknown",
  "supports": [],
  "contradicts": [],
  "event_class": "price|filing|flow|narrative|source_health|portfolio|unknown",
  "why_it_matters_tags": [],
  "capital_relevance_tags": [],
  "no_execution": true
}
```

### ContextGap

```json
{
  "gap_id": "gap:<stable-hash>",
  "campaign_id": null,
  "claim_id": "claim:<stable-hash>",
  "missing_lane": "market_structure|corporate_filing|real_economy_alt_data|news_policy_narrative|human_field|internal_private|derived_context",
  "why_load_bearing": "...",
  "what_claims_remain_weak": [],
  "which_source_could_close_it": [],
  "cost_of_ignorance": "low|medium|high|unknown",
  "no_execution": true
}
```

## Authority Boundary Impact

Phase 2 may write:
- `state/source-atoms/*.jsonl`
- `state/claim-graph.json`
- `state/context-gaps.json`
- contracts/schema snapshots/tests

Phase 2 must not:
- alter `accepted_evidence_records`
- alter wake score or wake class
- alter `JudgmentEnvelope`
- alter delivery safety
- alter Discord output
- mutate thresholds
- create execution semantics

Optional future manifest fields may be audit-only:
- `source_atom_hash`
- `claim_graph_hash`
- `context_gap_hash`
- `shadow_context_mode: "audit_only"`

## Files Likely Touched For Implementation

Finance repo:
- `scripts/finance_worker.py`
- `scripts/source_atom_compiler.py` (new)
- `scripts/claim_graph_compiler.py` (new)
- `scripts/context_gap_compiler.py` (new)
- `docs/openclaw-runtime/contracts/source-atom-contract.md` (new)
- `docs/openclaw-runtime/contracts/claim-atom-contract.md` (new)
- `docs/openclaw-runtime/contracts/context-gap-contract.md` (new)
- `tests/test_information_dominance_phase2_contract.py` (new)
- possibly `tests/test_source_atom_compiler.py`, `tests/test_claim_graph_compiler.py`, `tests/test_context_gap_compiler.py`

Parent workspace only if needed later:
- `services/market-ingest/packet_compiler/compiler.py`
- `services/market-ingest/adapters/live_finance_adapter.py`

## Data Migration / Shadow-Mode Posture

1. Add schemas/contracts first.
2. Add compilers that can run from existing state without being in hot path.
3. Add optional finance_worker parallel-write for SourceAtoms after tests lock deterministic behavior.
4. Keep ClaimGraph/ContextGap generated manually or as deterministic sidecar initially.
5. Do not wire artifacts into report delivery or wake policy.
6. Only after passing a full market-day shadow observation should later phases use them for CampaignProjection.

## Test Plan

Required tests:
- `test_source_atom_compiler_writes_deterministic_atoms`
- `test_source_atom_preserves_raw_ref_and_point_in_time_hash`
- `test_source_atom_does_not_mutate_accumulated_observations`
- `test_claim_graph_derives_claims_from_atoms_without_llm`
- `test_claim_graph_hash_is_deterministic`
- `test_context_gap_marks_missing_market_structure_for_narrative_only_claim`
- `test_context_gap_marks_missing_corporate_filing_for_unverified_issuer_claim`
- `test_phase2_artifacts_are_shadow_only`
- `test_packet_wake_class_unchanged_with_phase2_artifacts_present`
- `test_finance_worker_parallel_atom_write_preserves_existing_output`

Parent regression tests:
- source promotion tests pass
- live adapter tests pass
- packet compiler/wake policy tests pass
- temporal alignment tests pass
- judgment validator tests pass

Finance regression tests:
- full `tests` suite pass
- Phase 0/1 information dominance tests pass
- Campaign/Discord surface tests pass

## Rollback Plan

Rollback is local and clean if implementation stays Option A:
- remove new compilers
- remove new contracts/schemas/tests
- remove finance_worker parallel-write call
- remove generated shadow state files
- leave active report/wake/delivery untouched

If any parent manifest fields are added later, revert them separately and refresh parent dependency inventory.

## Acceptance Criteria

- Phase 2 artifacts are deterministic and schema-backed.
- SourceAtoms preserve original source refs/snippets enough for trace without raw dump abuse.
- Claims are derived deterministically from atoms and existing structured fields, not LLM free prose.
- ContextGaps explicitly identify missing source lanes and cost of ignorance.
- Existing finance_worker output remains byte/semantically stable except for shadow files.
- Existing wake/report/delivery behavior remains unchanged.
- Critic review runs before commit/push.
- Commit/push happens only after tests pass.

## Residual Risks

- Deterministic claim extraction may be too shallow initially.
- Raw snippets may accidentally expose too much source text; require bounded snippet length.
- Finance-only Option A gives weaker candidate/evidence linkage than parent-integrated Option B.
- Shadow artifacts can become theater if Phase 3/4 do not consume them.
- Parent dirty state still means finance commits must rely on snapshots/inventory for parent visibility.

## Architect Review

Verdict: APPROVE WITH NARROWING.

Strongest steelman antithesis: Phase 2 should derive claims at the `SourceCandidate -> EvidenceRecord` boundary instead of from finance_worker atoms, because that is where promotion decisions and evidence eligibility are known. This is valid, but doing it now increases parent blast radius. The synthesis is to start finance-only and include stable refs that allow later parent linkage.

Tradeoff tension: preserving raw-ish context improves future intelligence, but increases privacy/copyright/noise risk. The selected plan mitigates this with bounded snippets, raw refs, hashes, and no raw dump into operator surfaces.

Tradeoff tension: deterministic extraction avoids hallucination but may under-capture nuance. This is acceptable in Phase 2 because the target is substrate preservation, not final interpretation.

Required narrowing:
- Bounded `raw_snippet` length.
- Explicit `no_execution=true` on all objects.
- No packet/wake integration except optional audit hashes.
- No LLM claim extraction in Phase 2.

## Critic Review

Verdict: APPROVE.

Checks:
- Principles match selected Option A.
- Alternatives are real and fairly rejected.
- Test plan is concrete enough to prove shadow-only behavior.
- Rollback is clean.
- Authority boundary is explicit.

Critic requirement for implementation round:
- Before commit/push, run a critic pass specifically checking whether any new artifact is consumed by wake/judgment/delivery or leaks raw source content into operator primary surfaces.

## Final RALPLAN Verdict

Go for implementation: true.

Implementation mode recommendation: ultrawork can parallelize implementation into disjoint lanes only if write scopes stay separate:
- Lane A: contracts/schemas/tests.
- Lane B: source_atom_compiler + finance_worker hook.
- Lane C: claim_graph/context_gap compilers.

Do not use team/worker labels outside team mode. If using Codex native subagents, use executor/test-engineer/critic roles with disjoint write scopes.

Implementation stop rule: This RALPLAN approves Phase 2 implementation scope, but implementation should start in the next turn/round after this RALPLAN is committed and pushed.
