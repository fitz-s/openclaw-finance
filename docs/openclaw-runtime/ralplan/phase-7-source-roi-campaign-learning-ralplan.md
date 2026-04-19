# RALPLAN Phase 7: Source ROI / Campaign Learning

Status: approved_for_implementation
Go for implementation: true

Prior commits:
- Phase 5 Board Package: `2d890ed`
- Phase 6 Follow-up Routing: `f2c2a5b`

## Task Statement

Add finance-local learning artifacts that measure source contribution, context coverage, follow-up grounding, and campaign outcomes without mutating thresholds or active runtime behavior.

## Current Facts

Fact: `score_report_usefulness.py` currently scores report markdown quality/noise.

Fact: `review_runtime_gaps.py` summarizes watchlist freshness, report quality, wake/threshold bridge, and benchmark absorption.

Fact: Decision log already records hashes/refs for reports, boards, starter queries, alias maps, and wake attribution.

Fact: Phases 1-6 now emit source health, atoms, claim graph, context gaps, undercurrents, campaign board, board package, and follow-up route artifacts.

## Principles

1. Learning recommends; it does not mutate thresholds or active delivery.
2. Measure campaign usefulness, not just report prose quality.
3. Source ROI includes additivity, freshness, coverage, and contribution, not just reliability.
4. Context gaps are a metric, not a failure by themselves.
5. Keep outputs local and review-only.

## Selected Plan

Implement finance-local scripts:
- `scripts/source_roi_tracker.py`
- `scripts/context_coverage_audit.py`

Outputs:
- `state/source-roi-history.jsonl`
- `state/campaign-outcomes.jsonl`
- `docs/openclaw-runtime/context-coverage-audit.json`

Optionally enrich `tools/review_runtime_gaps.py` and `tools/score_report_usefulness.py` to surface these artifacts as review evidence, not active policy.

## Rejected Options

Rejected: automatic threshold tuning from source ROI | violates no automatic threshold mutation.

Rejected: active source suppression from low ROI | too early and could hide review context.

Rejected: external dashboard integration | out of scope.

## Authority Boundary

Phase 7 may:
- write local learning JSON/JSONL artifacts
- update docs/snapshots/tests
- add review-only recommendations

Phase 7 must not:
- mutate thresholds
- dispatch or suppress reports
- change wake/delivery behavior
- call broker/execution APIs
- send Discord messages

## Test Plan

Required tests:
- `test_source_roi_tracker_scores_source_contribution_without_mutation`
- `test_source_roi_history_is_append_only_jsonl`
- `test_context_coverage_audit_reports_gap_rate`
- `test_campaign_outcomes_record_campaign_ids_and_followup_hits`
- `test_learning_outputs_no_threshold_mutation`

## Acceptance Criteria

- Source ROI history exists and is append-only.
- Campaign outcomes exist and include campaign id, board class, stage, refs, follow-up route info when available.
- Context coverage audit reports source coverage score, context gap rate, freshness breach rate, and grounding risk.
- Full tests pass.
- Critic verifies no active runtime mutation.

## Critic Review

Verdict: APPROVE.

Checks:
- Scope is local and review-only.
- Metrics are useful for later Phase 8 cutover decision.
- No automatic policy mutation is allowed.

Implementation critic requirement:
- Before commit/push, critic must verify no threshold mutation, no report dispatch/suppression, no Discord send, and no execution semantics.

## Final RALPLAN Verdict

Go for implementation: true.
