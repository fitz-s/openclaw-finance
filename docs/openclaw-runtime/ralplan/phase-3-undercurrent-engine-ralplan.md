# RALPLAN Phase 3: Undercurrent Engine

Status: approved_for_implementation
Go for implementation: true

Prior commits:
- Phase 0 gate: `19f5501`
- Phase 1 implementation: `fdae2c9`
- Phase 2 implementation: `29c1ac7`

## Task Statement

Upgrade `undercurrent_compiler.py` from a shallow projection over invalidators/opportunities/capital graph into a shadow Undercurrent Engine that can use Phase 1 Source Health and Phase 2 EvidenceAtom / ClaimGraph / ContextGap artifacts.

Goal: make peacetime/dark-signal accumulation explicit without alert spam or active wake changes.

## Current Facts

Fact: Current [`undercurrent_compiler.py`](../../scripts/undercurrent_compiler.py) derives cards from:
- `invalidator-ledger.json`
- `opportunity-queue.json`
- `capital-graph.json`

Fact: Current `UndercurrentCard` lacks:
- `acceleration_score`
- `cross_lane_confirmation`
- `source_diversity`
- `contradiction_load`
- `known_unknowns`
- links to atoms/claims/context gaps
- stage mutation history

Fact: Phase 1 now provides Source Health shadow artifacts and registry metadata.

Fact: Phase 2 now provides SourceAtoms, ClaimGraph, and ContextGap shadow artifacts.

Fact: `PACKET_UPDATE_ONLY` currently persists in wake dispatch and does not alert. Phase 3 must preserve that no-spam behavior.

## Principles

1. Peacetime visibility without alert spam: `PACKET_UPDATE_ONLY` may mutate undercurrent state, not main-channel alert delivery.
2. Cross-lane beats single-source noise: promotion should favor source diversity, claim persistence, and decreasing context gaps.
3. Known unknowns are first-class: unresolved ContextGaps should be visible on undercurrent cards.
4. Shadow until proven: Phase 3 must not change wake/delivery behavior or campaign board active delivery.
5. Review-only always: no execution semantics, no threshold mutation.

## Decision Drivers

1. Use the new Phase 1/2 substrates before moving to CampaignProjection 2.0.
2. Avoid adding Discord board behavior before undercurrent quality is measurable.
3. Make source freshness/claims/gaps influence peacetime ranking without becoming active gates.

## Viable Options

### Option A: Extend undercurrent_compiler only

Add optional inputs for source health, claim graph, context gaps, and source atoms. Compute richer fields inside the existing compiler and keep output path `state/undercurrents.json`.

Pros:
- Smallest implementation surface.
- Easy to test.
- Preserves existing campaign_projection_compiler inputs.

Cons:
- No persistent stage/history yet.
- Limited event_watcher integration.

### Option B: Add undercurrent_engine.py with history and leave compiler as adapter

Create a new engine that owns persistence/history, while existing compiler becomes compatibility wrapper.

Pros:
- Cleaner long-term separation.
- Better for stage transitions and learning.

Cons:
- More files and more migration risk.
- Bigger blast radius before CampaignProjection 2.0.

### Option C: Wire PACKET_UPDATE_ONLY into board mutation now

Change wake dispatcher / report job so packet updates directly mutate Peacetime/Risk Board.

Pros:
- Immediate UX movement.

Cons:
- Too close to active runtime/delivery behavior.
- Violates shadow-first sequence before undercurrent quality is validated.

## Selected Plan

Choose Option A for Phase 3 implementation.

Add richer undercurrent scoring and metadata inside existing `undercurrent_compiler.py`, using optional shadow inputs:
- `state/source-health.json` if present
- `state/source-atoms/latest.jsonl` if present
- `state/claim-graph.json` if present
- `state/context-gaps.json` if present
- existing invalidator/opportunity/capital graph state

Keep existing output `state/undercurrents.json` and existing consumers compatible.

## Rejected Options

Rejected: Option B | cleaner long-term, but premature before proving score fields.

Rejected: Option C | board mutation belongs after undercurrent quality and CampaignProjection 2.0 are tested.

Rejected: Use LLM sidecars to score undercurrents | nondeterministic and unnecessary for this phase.

## Proposed New Undercurrent Fields

Add optional fields while preserving current ones:
- `acceleration_score`
- `cross_lane_confirmation`
- `source_diversity`
- `contradiction_load`
- `known_unknowns`
- `linked_refs.atom`
- `linked_refs.claim`
- `linked_refs.context_gap`
- `source_health_refs`
- `shadow_inputs`

## Authority Boundary Impact

Phase 3 may:
- enrich `state/undercurrents.json`
- update contracts/tests/snapshot docs
- allow CampaignProjection to read richer fields only if backward compatible

Phase 3 must not:
- dispatch Discord messages
- change wake class
- change wake thresholds
- change delivery safety
- mutate JudgmentEnvelope
- treat undercurrents as execution signals

## Files Likely Touched

- `scripts/undercurrent_compiler.py`
- `docs/openclaw-runtime/contracts/undercurrent-card-contract.md`
- `tests/test_campaign_projection.py`
- `tests/test_undercurrent_engine.py` or equivalent
- optionally `campaign_projection_compiler.py` only for passive display compatibility, not active delivery changes

## Test Plan

Required tests:
- `test_undercurrent_uses_claim_graph_for_source_diversity`
- `test_undercurrent_links_context_gaps_as_known_unknowns`
- `test_source_health_degradation_is_explicit_not_blocking`
- `test_packet_update_only_remains_non_dispatch_behavior`
- `test_existing_campaign_projection_still_reads_undercurrents`
- `test_undercurrent_output_remains_no_execution`

Regression tests:
- full finance tests
- parent market-ingest tests if any parent file touched
- Campaign/Discord operator surface tests

## Rollback Plan

- Revert `undercurrent_compiler.py` enrichment.
- Keep Phase 1/2 artifacts untouched.
- Existing campaign projection falls back to old undercurrent fields.
- No active runtime rollback needed if Phase 3 remains compiler-only.

## Acceptance Criteria

- Undercurrent cards expose source diversity, cross-lane confirmation, contradiction load, and known unknowns.
- Context gaps appear as known unknowns, not as fabricated conclusions.
- Source health stale/unknown appears as degraded metadata, not a hard block.
- Existing CampaignProjection and Discord operator tests still pass.
- Critic pass runs before commit/push.

## Architect Review

Verdict: APPROVE WITH NARROWING.

Steelman antithesis: Under-current scoring may be premature until ClaimGraph quality is proven. Mitigation: fields stay advisory/shadow and preserve old score fields.

Tradeoff: Better dark-signal visibility vs more noisy metadata. Mitigation: cap linked refs and known unknowns, keep no-alert behavior.

Required narrowing:
- No wake dispatcher changes in Phase 3.
- No Discord board edit behavior in Phase 3.
- No LLM scoring.

## Critic Review

Verdict: APPROVE.

Checks:
- Shadow boundary is explicit.
- Options are fair and selected option has lowest blast radius.
- Tests prove both richer undercurrent data and unchanged active behavior.
- Rollback is simple.

Implementation critic requirement:
- Before commit/push, critic must verify no wake/delivery/Discord mutation and no undercurrent->execution semantics.

## Final RALPLAN Verdict

Go for implementation: true.

Recommended mode: single executor lane, with optional critic/test-engineer lanes for review. Avoid broad ultrawork implementation because write scope centers on one compiler.
