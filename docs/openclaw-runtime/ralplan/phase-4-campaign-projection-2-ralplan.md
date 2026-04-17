# RALPLAN Phase 4: CampaignProjection 2.0

Status: approved_for_implementation
Go for implementation: true

Prior commits:
- Phase 1 Source Health: `fdae2c9`
- Phase 2 Evidence Substrate: `29c1ac7`
- Phase 3 Undercurrent Enrichment: `bc8154a`

## Task Statement

Upgrade CampaignProjection from a human-readable board projection into a source-backed campaign lifecycle projection that can carry undercurrent, atom, claim, context gap, source health, stage history, and thread-key metadata.

This phase still does not activate Discord board edit/update or thread routing. It is compiler/output contract work only.

## Current Facts

Fact: Current [`campaign_projection_compiler.py`](../../scripts/campaign_projection_compiler.py) builds campaigns from capital agenda, opportunities, and undercurrents.

Fact: Current campaigns already include `campaign_id`, `campaign_type`, `board_class`, `stage`, `human_title`, `why_now_delta`, `why_not_now`, `capital_relevance`, confirmations, kill switches, linked refs, source freshness, thread key, and no_execution.

Fact: Current campaign board markdown outputs live/scout/risk surfaces, but it is still primarily section/board text, not lifecycle-aware campaign memory.

Fact: Phase 3 undercurrents now carry source diversity, cross-lane confirmation, contradiction load, known unknowns, atom/claim/context gap refs, and source health summary.

Fact: Phase 4 map requires outputs: `campaign-board.json`, `campaign-stage-history.jsonl`, and `campaign-threads.json`.

## Principles

1. Campaign is projection, not authority: canonical chain remains ContextPacket/WakeDecision/JudgmentEnvelope/product validation/safety.
2. Human title is primary; handles and machine refs are audit/linkage fields.
3. Lifecycle matters: campaign stage transitions must be recorded and replayable.
4. Thread is UI, not memory: `thread_key`/thread registry maps UI to bundle/campaign state, but campaign artifacts remain memory.
5. No active Discord mutation in Phase 4.

## Decision Drivers

1. Use richer Phase 1-3 substrate to make campaigns source-backed before Discord board cutover.
2. Preserve current board markdown compatibility while adding lifecycle and audit fields.
3. Keep implementation in finance repo and avoid parent runtime blast radius.

## Viable Options

### Option A: Enrich existing campaign_projection_compiler only

Add optional fields and history/thread registry outputs to the existing compiler.

Pros:
- Lowest blast radius.
- Existing report renderer already consumes `campaign-board.json`.
- Easy to test with existing campaign projection tests.

Cons:
- Compiler becomes larger.
- Lifecycle handling remains basic.

### Option B: New campaign_engine.py with projection compiler wrapper

Create a new lifecycle engine and have current compiler wrap it.

Pros:
- Cleaner long-term architecture.
- Better separation of projection vs lifecycle state.

Cons:
- More files and migration risk.
- Premature before active board/thread runtime exists.

### Option C: Implement Discord board/thread registry now

Add actual thread registry/update behavior in Phase 4.

Pros:
- Immediate UX movement.

Cons:
- Violates sequence; parent runtime belongs to Phase 5.
- Requires gateway/Discord adapter concerns not approved here.

## Selected Plan

Choose Option A.

Enhance `campaign_projection_compiler.py` to:
- propagate `known_unknowns`, source diversity, cross-lane confirmation, contradiction load, source health summary, atom/claim/context gap refs from undercurrents
- compute clearer campaign stage based on priority + undercurrent quality fields
- write `state/campaign-stage-history.jsonl` with deterministic stage transition summaries
- write/update `state/campaign-threads.json` as local registry with `thread_key`, `campaign_id`, `status=unbound`, and no actual Discord thread IDs unless already known
- preserve existing `campaign-board.json` and board markdown fields

## Rejected Options

Rejected: Option B | cleaner but too broad before active board/thread runtime.

Rejected: Option C | active Discord/thread behavior belongs to Phase 5 and needs parent runtime RALPLAN/gate.

Rejected: make campaigns new authority | violates review-only and current contracts.

## New/Extended Campaign Fields

- `source_diversity`
- `cross_lane_confirmation`
- `contradiction_load`
- `known_unknowns`
- `source_health_summary`
- `linked_atoms`
- `linked_claims`
- `linked_context_gaps`
- `stage_reason`
- `last_stage_hash`
- `thread_status`

## Authority Boundary Impact

Phase 4 may:
- enrich `state/campaign-board.json`
- write `state/campaign-stage-history.jsonl`
- write `state/campaign-threads.json`
- update campaign contracts/tests

Phase 4 must not:
- create Discord threads
- edit Discord board messages
- change report delivery safety
- change wake thresholds
- change JudgmentEnvelope
- execute trades or imply execution

## Files Likely Touched

- `scripts/campaign_projection_compiler.py`
- `docs/openclaw-runtime/contracts/campaign-projection-contract.md`
- `tests/test_campaign_projection.py`
- new `tests/test_campaign_projection_lifecycle.py`
- possibly `finance_decision_log_compiler.py` only if logging stage refs is purely audit-only; defer if unnecessary

## Test Plan

Required tests:
- `test_campaign_projection_carries_undercurrent_shadow_refs`
- `test_campaign_stage_reason_uses_quality_fields_without_authority_change`
- `test_campaign_stage_history_records_transition`
- `test_campaign_threads_registry_is_local_unbound_by_default`
- `test_existing_board_markdown_remains_compatible`
- `test_campaign_projection_no_execution_and_not_authority`

Regression:
- full finance tests
- Campaign/Discord operator surface tests
- product validator tests

## Rollback Plan

- Revert `campaign_projection_compiler.py` enrichment.
- Remove stage history/thread registry writes.
- Existing `campaign-board.json` output shape remains compatible or returns to prior shape.
- No runtime/Discord rollback needed if Phase 4 stays compiler-only.

## Acceptance Criteria

- Campaigns carry source-backed shadow refs and known unknowns.
- Stage history and thread registry are local artifacts only.
- Board markdown still renders and existing tests pass.
- No active Discord or delivery behavior changes.
- Critic runs before commit/push.

## Architect Review

Verdict: APPROVE WITH NARROWING.

Steelman antithesis: Campaign lifecycle may be premature until Discord threads are active. Mitigation: write local lifecycle artifacts only, keep thread status `unbound`, and defer runtime adapter behavior to Phase 5.

Tradeoff: adding lifecycle to existing compiler increases complexity. Mitigation: no new engine yet; keep stage-history functions small and deterministic.

Required narrowing:
- No parent runtime changes.
- No Discord thread creation.
- No delivery safety changes.

## Critic Review

Verdict: APPROVE.

Checks:
- Selected option is lowest blast radius.
- Tests are concrete.
- Boundary forbids active Discord behavior.
- Rollback is simple.

Implementation critic requirement:
- Before commit/push, critic must verify campaign artifacts are projection-only, thread registry does not create/claim external thread IDs, and board markdown remains compatible.

## Final RALPLAN Verdict

Go for implementation: true.

Recommended mode: single executor lane. Use critic/test-engineer only for review if needed.
