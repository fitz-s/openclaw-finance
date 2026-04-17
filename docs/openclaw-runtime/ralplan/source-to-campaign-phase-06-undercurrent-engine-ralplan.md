# RALPLAN Source-to-Campaign Phase 06: Undercurrent Engine

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Finish the deterministic undercurrent scoring layer so peacetime / dark-signal accumulation is measurable and board-mutation-ready without changing wake priority.

The existing `undercurrent_compiler.py` already carries claims/gaps/source health. This phase adds explicit score, promotion gates, promotion blockers, and PACKET_UPDATE_ONLY visibility semantics.

## Principles

1. Peacetime visibility is not alert spam.
2. Cross-lane confirmation beats single-source narrative.
3. Promotion requires source diversity, capital relevance, freshness health, and manageable contradiction load.
4. Undercurrents remain review-only and cannot affect wake priority in this phase.
5. Promotion blockers must be explicit.

## Decision Drivers

1. The review requires undercurrents to be first-class and not ticker-move-only.
2. Campaign OS needs deterministic fields for scout/candidate stage decisions.
3. Later cutover needs proof that undercurrent quality is measurable before wake influence.

## Selected Plan

Extend `undercurrent_compiler.py` with deterministic scoring and promotion metadata:
- `undercurrent_score`
- `cross_lane_confirmation_score`
- `contradiction_load_score`
- `freshness_penalty`
- `capital_relevance_score`
- `promotion_candidate`
- `promotion_blockers`
- `peacetime_update_eligible`
- `packet_update_visibility=board_mutation_only`
- `wake_impact=none`

## Acceptance Criteria

- Single-lane undercurrents are blocked from promotion.
- Cross-lane undercurrents can become promotion candidates only if contradiction and freshness are acceptable.
- PACKET_UPDATE_ONLY semantics are explicit: board mutation only, no wake impact.
- Existing CampaignProjection consumers remain compatible.

## Test Plan

- `test_undercurrent_score_requires_cross_lane_confirmation_for_promotion`
- `test_undercurrent_blocks_promotion_on_high_contradiction_load`
- `test_packet_update_only_visibility_is_board_mutation_only`
- existing undercurrent tests

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-06-implementation-critic.md` after implementation.
