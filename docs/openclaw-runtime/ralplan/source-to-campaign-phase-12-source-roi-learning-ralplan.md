# RALPLAN Source-to-Campaign Phase 12: Source ROI And Campaign Learning

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Upgrade source ROI and campaign outcome learning so source contribution is tracked by lane, campaign value, context gaps, follow-up hits, and future false-positive/closure metrics without mutating policy.

## Principles

1. Source ROI recommends; it does not mutate thresholds.
2. Learning happens at campaign/source-lane level, not just report prose level.
3. Context gap closure and false-positive metrics can start as explicit null/proxy fields.
4. Review-only, no execution.

## Decision Drivers

1. The review requires source-to-campaign contribution metrics.
2. Phase 05 archive and Phase 11 reviewer replay now expose better evidence context.
3. Existing source_roi_tracker is useful but too narrow.

## Selected Plan

- Add source ROI contract.
- Extend source ROI rows with source lanes, contribution refs, campaign value score, false-positive proxy, context gap closure placeholder, and peacetime conversion flag.
- Extend campaign outcome rows with linked claims/gaps and lane/source quality fields.
- Keep all outputs local review-only.

## Acceptance Criteria

- Source ROI rows include source_lane_set and source_to_campaign contribution fields.
- Campaign rows include linked claims/gaps and conversion/follow-up fields.
- No threshold mutation or active runtime behavior changes.

## Test Plan

- `test_source_roi_rows_include_lane_and_campaign_value_fields`
- `test_campaign_outcomes_include_claim_gap_and_conversion_fields`
- existing source ROI tests

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-12-implementation-critic.md` after implementation.
