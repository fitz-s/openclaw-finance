# RALPLAN Ingestion Fabric Phase 10: Claim-Aware Event Watcher And Undercurrents

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Move watcher and undercurrent semantics away from theme/price overlap as the main signal. Watchers should be able to detect relevant ClaimGraph/ContextGap/SourceHealth changes, and undercurrents should use claim persistence, source diversity, cross-lane confirmation, contradiction load, and degraded source health.

## RALPLAN-DR Summary

### External Scout Inputs

Source class: event/claim graph reasoning, provenance graphs, weak-signal memory, trust/corroboration, contradiction evidence, and time-aware ranking.

Integrated findings:
- Candidate signals should be graph objects with source lineage, not only text matches.
- Confirmation should count independent source/lane corroboration, not repeated copies.
- Weak signals should persist with bounded retention and drift handling.
- Contradiction load should be explicit and suppress promotion.
- Freshness penalties should be one factor, not a hard truth filter.
- Promotion should require sustained, corroborated, spreading signals.

Reference links from scout:
- Cross-document event graph reasoning: https://aclanthology.org/2022.naacl-main.40/
- Claim/data provenance graphs: https://cogcomp.seas.upenn.edu/papers/Zhang22.pdf
- MemStream weak-signal memory: https://arxiv.org/abs/2106.03837
- Counter-weighted positive/negative evidential paths: https://aclanthology.org/2020.coling-main.147/

### Principles

1. **Claims beat theme prose.** Theme matching remains fallback, not the main signal.
2. **Known unknowns are signal.** ContextGaps should increase update relevance without becoming conclusions.
3. **Source health is not neutral.** Quota/freshness/coverage degradation must reduce confidence and be visible.
4. **Peacetime stays peacetime.** PACKET_UPDATE_ONLY should mutate boards, not force wake.
5. **No authority expansion.** Watcher/undercurrent outputs do not change execution, thresholds, or judgment authority.

## Selected Design

Modify `scripts/event_watcher.py`:
- Load `state/claim-graph.json`, `state/context-gaps.json`, and `state/source-health.json` during `tick()`.
- Add `claim_signal_for_watcher()` to match watcher tickers/theme against ClaimGraph rows.
- Include linked context gaps and degraded source-health rows in update reason metadata.
- Preserve old price/theme observation fallback.

Modify `scripts/undercurrent_compiler.py`:
- Default source health path to `finance/state/source-health.json`.
- Treat quota/coverage/rate-limit degradation as degraded source health.
- Add claim persistence fields and source-health degraded reasons.

## Acceptance Criteria

1. Event watcher can detect claim-linked updates without relying on theme word overlap.
2. ContextGaps linked to matched claims appear in watcher signal metadata.
3. Source health degradation appears in watcher/undercurrent metadata.
4. Undercurrents include claim persistence and degraded source-health reasons.
5. Old behavior remains compatible when no claim graph is present.
6. Tests and full suite pass.

## Non-Goals

- Do not trigger Discord delivery directly.
- Do not change wake thresholds.
- Do not remove old price/theme watcher fallback.
- Do not make undercurrent promotion an execution signal.

## Critic Requirements

Critic must verify claim/gap/source-health fields are advisory only, old fallback survives, and no wake/delivery/execution authority changed.
