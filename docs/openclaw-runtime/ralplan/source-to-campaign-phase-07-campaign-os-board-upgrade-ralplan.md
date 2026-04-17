# RALPLAN Source-to-Campaign Phase 07: Campaign OS Board Upgrade

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Upgrade CampaignProjection and board rendering to consume Phase 06 undercurrent quality fields, so campaign cards disclose lane coverage, source health, score, and promotion blockers.

This remains an operator projection. It does not change delivery wiring, wake priority, JudgmentEnvelope, or execution authority.

## Principles

1. Campaign cards must show evidence quality, not only narrative priority.
2. Human title and decision implication stay primary; machine scores are supporting context.
3. Promotion blockers should reduce false confidence.
4. Board output remains concise and Discord-safe.
5. No execution language.

## Decision Drivers

1. Phase 06 now provides undercurrent_score, promotion_candidate, and blockers.
2. The review requires Campaign OS cards to include lane coverage, known unknowns, and source health disclosure.
3. Existing boards are decision-dense but do not yet surface promotion blockers.

## Selected Plan

- Extend CampaignProjection contract with `lane_coverage_summary`, `undercurrent_score`, `promotion_candidate`, and `promotion_blockers`.
- Propagate these fields from undercurrents to campaigns.
- Add an `Evidence` board line with source diversity, cross-lane confirmation, score, and top blocker.
- Keep existing board structure and limits.

## Acceptance Criteria

- Campaigns derived from undercurrents carry score and blockers.
- Board markdown contains an `Evidence：` line.
- Source health and known unknowns remain visible.
- Existing campaign tests remain compatible.

## Test Plan

- `test_campaign_projection_carries_undercurrent_quality_gates`
- `test_campaign_board_contains_evidence_quality_line`
- existing campaign projection and decision dense tests

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-07-implementation-critic.md` after implementation.
