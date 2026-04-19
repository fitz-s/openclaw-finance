# RALPLAN Source-to-Campaign Phase 01: Source Office 2.0 And Scout Expansion

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Implement the first Source Office slice from `review-04-17-2026.md`: make source lanes and scout expansion explicit, with special treatment for options volatility / IV source candidates.

This phase is shadow-only. It does not add a new data vendor to the hot path, does not change wake priority, and does not change report delivery.

## Principles

1. Source discovery is not source activation.
2. Every source candidate must carry lane, sublane, rights, cost, latency, replay, and implementation risk.
3. Options/IV must be treated as a first-class market-structure sublane, not as generic price or narrative context.
4. Unknown rights or weak replay support block promotion to hot path.
5. Reviewer-visible source candidates are derived metadata only; no credentials, raw licensed data, or vendor secrets.

## Decision Drivers

1. The review found source health was degraded and overly concentrated in `news_policy_narrative`.
2. The user specifically observed weak IV/options sensitivity.
3. Later EvidenceAtom/ClaimGraph work needs a richer lane registry before changing canonical ingestion.

## Viable Options

Option A: Directly integrate one options vendor.
- Pros: may improve IV sensitivity quickly.
- Cons: high rights/cost/API risk; violates scout-before-activation.

Option B: Only update contracts.
- Pros: minimal risk.
- Cons: does not give scouts/reviewers a concrete source backlog.

Option C: Add a deterministic source scout candidate registry and tests.
- Pros: creates reviewable source expansion backlog while preserving hot path.
- Cons: does not yet improve live data quality.

Selected: Option C.

Rejected: Option A | source rights, API limits, and point-in-time support must be evaluated before activation.
Rejected: Option B | too passive; the user asked scouts to find more sources.

## Implementation Scope

- Extend Source Registry 2.0 contract with `source_sublane`, especially `market_structure.options_iv`.
- Add Source Scout contract.
- Add deterministic `scripts/source_scout.py` producing candidate evaluations.
- Include options/IV candidates and non-options source lanes.
- Add tests for lane classification, rights/cost metadata, no hot-path promotion, and options/IV coverage.
- Add Phase 01 critic artifact.

## Acceptance Criteria

- Source scout outputs candidates across all six review lanes.
- Options/IV candidates include IV rank/percentile/skew/OI/volume-OI/staleness/replay needs.
- Every candidate has rights policy and cost class.
- Every candidate starts as `shadow_candidate` and cannot wake/support judgment directly.
- Contract explicitly distinguishes `source_lane` from `source_sublane`.

## Test Plan

- `test_source_scout_outputs_all_review_lanes`
- `test_options_iv_candidates_require_iv_specific_metrics`
- `test_source_scout_candidates_are_shadow_only`
- `test_source_scout_contract_mentions_rights_cost_replay`

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-01-implementation-critic.md` after implementation.
