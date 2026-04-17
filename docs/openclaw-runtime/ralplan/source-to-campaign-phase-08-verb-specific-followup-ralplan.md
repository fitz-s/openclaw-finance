# RALPLAN Source-to-Campaign Phase 08: Verb-Specific Follow-up Committee Room

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Upgrade follow-up routing so `why`, `challenge`, `compare`, `scenario`, `sources`, and `trace` expose different evidence requirements and explicit missing-data/context-gap guidance.

This phase remains explain-only. It does not alter parent Discord routing, thread memory, JudgmentEnvelope, wake, or execution authority.

## Principles

1. Verb drives context slice; thread history is not memory.
2. Missing evidence must return `insufficient_data`, not generic inference.
3. Context gaps should explain what is missing and why it matters.
4. Compare/scenario/sources/trace must not all look like the same answer template.
5. Review-only and no execution.

## Decision Drivers

1. The review says follow-up failure is context selection, not context length.
2. Phase 04 ContextGaps now have closure semantics that can be surfaced.
3. Campaign OS now exposes quality fields that follow-up should use.

## Selected Plan

- Add follow-up context slice contract.
- Extend `finance_followup_context_router.py` with verb-specific evidence groups and coverage metadata.
- Add context-gap guidance for missing fields.
- Extend answer guard to reject answered responses when provided coverage shows missing required groups.

## Acceptance Criteria

- Router emits `required_evidence_groups`, `evidence_slice_coverage`, and `context_gap_guidance`.
- Missing compare/scenario/sources/trace fields produce `insufficient_data` and gap guidance.
- Answer guard allows `insufficient_data` but rejects an answered response that includes missing required coverage.
- Existing follow-up tests remain green.

## Test Plan

- `test_followup_router_emits_verb_specific_evidence_groups`
- `test_followup_router_returns_context_gap_guidance_for_missing_compare_slice`
- `test_followup_guard_blocks_answered_response_with_missing_required_coverage`

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-08-implementation-critic.md` after implementation.
