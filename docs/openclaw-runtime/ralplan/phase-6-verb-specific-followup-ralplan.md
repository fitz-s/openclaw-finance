# RALPLAN Phase 6: Verb-Specific Follow-up Engine

Status: approved_for_implementation
Go for implementation: true

Prior commits:
- Phase 4 CampaignProjection 2.0: `2f44490`
- Phase 5 Board Package: `2d890ed`

## Task Statement

Upgrade follow-up from generic latest-bundle Q&A into verb-specific, object-specific, evidence-sliced context routing and answer validation.

This phase is finance-local only. It does not implement active Discord thread listening or parent runtime routing.

## Current Facts

Fact: `finance_followup_context_router.py` parses query as `verb primary secondary` and selects campaign or bundle card.

Fact: `finance_campaign_cache_builder.py` pre-bakes shallow verb cards for top campaigns but does not include `trace` or evidence slice IDs.

Fact: `finance_followup_answer_guard.py` validates binding, verb, review-only, structure, and forbidden mutation keys, but does not require evidence slice IDs or insufficient_data discipline.

Fact: Reader bundle and campaign board now carry richer aliases, refs, campaigns, known unknowns, source health, atoms/claims/gaps.

## Principles

1. Verb controls evidence slice: `why`, `challenge`, `compare`, `scenario`, `sources`, `trace`, and `expand` must select different context.
2. Selected handle is explicit: route must not guess from raw thread history.
3. Bundle/campaign artifacts are memory; thread text is UI only.
4. Missing data must return insufficient_data, not generic prose.
5. Follow-up remains explain-only: no new judgment, threshold mutation, actionability change, or execution semantics.

## Decision Drivers

1. Improve usefulness of Discord thread follow-up without touching active Discord runtime.
2. Make context selection deterministic enough for tests and later parent router integration.
3. Preserve existing report path and safety behavior.

## Viable Options

### Option A: Finance-local router/cache/guard upgrade

Enhance current router, cache builder, and answer guard. Emit route artifacts and evidence slice IDs. No parent thread listener.

Pros:
- Low blast radius.
- Testable now.
- Directly improves future parent router contract.

Cons:
- Does not make Discord threads actively respond yet.

### Option B: Implement parent Discord thread router now

Wire main-channel guard and thread follow-up into OpenClaw runtime.

Pros:
- Direct UX improvement.

Cons:
- Parent/gateway/Discord active runtime risk.
- Needs separate gate and possibly restart/reload.

### Option C: Keep generic Q&A and just improve prompt

Pros: minimal code.

Cons: Fails the core problem; context slice remains ambiguous.

## Selected Plan

Choose Option A.

Implement finance-local deterministic follow-up routing and validation:
- add alias resolution from campaign IDs, thread keys, object handles, campaign aliases, and report handles
- add `evidence_slice_id`
- add `missing_fields` / `insufficient_data` route metadata
- add `trace` cache cards
- require answer guard to carry `evidence_slice_id`
- allow explicit `insufficient_data` answers while blocking generic execution/judgment language

## Rejected Options

Rejected: Option B | active Discord thread router belongs to a later parent-runtime gated package.

Rejected: Option C | prompt-only improvements do not make context deterministic.

## Authority Boundary Impact

Phase 6 may:
- enrich follow-up context route JSON
- enrich campaign cache
- strengthen answer guard
- update contracts/tests

Phase 6 must not:
- read raw thread history as source of truth
- create/respond to Discord threads
- mutate judgments or thresholds
- alter report delivery
- execute trades

## Files Likely Touched

- `scripts/finance_followup_context_router.py`
- `scripts/finance_campaign_cache_builder.py`
- `scripts/finance_followup_answer_guard.py`
- `docs/openclaw-runtime/contracts/followup-answer-contract.md`
- tests for router/cache/guard

## Test Plan

Required tests:
- `test_followup_router_resolves_campaign_and_bundle_aliases`
- `test_followup_router_emits_evidence_slice_id`
- `test_compare_requires_secondary_handle`
- `test_missing_compare_context_returns_insufficient_data_metadata`
- `test_campaign_cache_builds_trace_card`
- `test_followup_guard_requires_evidence_slice_id`
- `test_followup_guard_allows_insufficient_data_but_blocks_execution`

Regression:
- existing follow-up guard tests
- campaign projection tests
- Discord operator surface tests
- full finance tests

## Rollback Plan

- Revert router/cache/guard changes.
- Existing starter queries and bundle route still work as before.
- No runtime/Discord rollback needed.

## Acceptance Criteria

- Every successful route has `evidence_slice_id`.
- Compare without secondary handle fails.
- Missing required evidence slice reports `insufficient_data` metadata.
- Answer guard blocks missing evidence slice IDs and execution language.
- No active Discord runtime changes.
- Critic runs before commit/push.

## Architect Review

Verdict: APPROVE WITH NARROWING.

Steelman antithesis: Active Discord thread response is the real UX fix. Mitigation: first make deterministic router/package contract; parent runtime can consume it in a later gated phase.

Required narrowing:
- No parent thread router in Phase 6.
- No raw thread history context.
- No LLM-dependent routing.

## Critic Review

Verdict: APPROVE.

Checks:
- Option A matches low-risk implementation.
- Tests are concrete.
- Authority boundary is clear.

Implementation critic requirement:
- Before commit/push, critic must verify no raw thread history, no Discord runtime call, no new judgment/actionability, and evidence_slice_id/insufficient_data behavior exists.

## Final RALPLAN Verdict

Go for implementation: true.

Recommended mode: single executor lane.
