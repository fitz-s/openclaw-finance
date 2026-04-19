# RALPLAN Source-to-Campaign Phase 04: ContextGap First-Class Unknowns

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Upgrade ContextGap records so missing evidence is objectized and actionable, not generic `To Verify` prose.

This phase strengthens gap objects only. It does not alter report delivery, Discord output, wake policy, or execution authority.

## Principles

1. Unknowns must be objects, not loose prose.
2. Every gap must name the missing lane, weak claim, suggested sources, and closure condition.
3. Keep existing fields for compatibility while adding canonical aliases for future follow-up/replay.
4. Gaps remain shadow-only and cannot block delivery in this phase.

## Decision Drivers

1. The review requires `ContextGap` to replace generic verification language.
2. Follow-up `insufficient_data` and report-time replay need gap status and closure semantics.
3. Existing context gaps already exist but lack status/closure fields.

## Selected Plan

Extend `context_gap_compiler.py` and contract with canonical fields while preserving old shape.

## Acceptance Criteria

- Every gap includes `gap_status=open`.
- Every gap includes `closure_condition`.
- Every gap includes `weak_claim_ids` and `suggested_sources` aliases.
- Every gap includes `source_lane_present` and `linked_campaign_id`.
- Existing gap tests remain green.

## Test Plan

- `test_context_gap_records_status_and_closure_condition`
- `test_context_gap_suggested_sources_match_missing_lane`
- existing context gap compiler tests

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-04-implementation-critic.md` after implementation.
