# RALPLAN Ingestion Fabric Phase 06: Brave Answers Sidecar

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Add Brave Answers as a citation-gated sidecar synthesis lane. It may produce derived hypotheses for analyst review, but it must never become canonical evidence or report authority. Only citations extracted from the answer stream may become EvidenceAtom candidates in later phases.

## RALPLAN-DR Summary

### Principles

1. **Answer prose is not evidence.** Brave Answers text is sidecar-derived context only.
2. **Citations are the only promotion path.** Without citations, the sidecar is review-only and not evidence-candidate-producing.
3. **Streaming is required for citation mode.** Citation/entity/research options require streaming; non-stream use is not the selected path.
4. **No hot-path integration.** This phase adds a callable sidecar script and tests only.
5. **No raw response artifact dump.** Persist bounded derived preview, digests, citation metadata, and request metadata, not raw streaming frames.

### Decision Drivers

1. Review2 requires `brave_answers_sidecar.py`, `chat/completions`, citations, sidecar-only authority, and no canonical evidence authority.
2. Phase 02 confirmed Brave Answers is missing from current OpenClaw provider and must not be placed into scanner hot path.
3. Phase 04/05 already established metadata-only persistence and dry-run/mocked tests for Brave surfaces.
4. Follow-up and campaign surfaces need richer sidecar hypotheses, but only after provenance/citation gating.

### Viable Options

#### Option A - Add Answers directly to scanner/report hot path

Rejected. This would bypass EvidenceAtom/ClaimAtom provenance and recreate prose authority.

#### Option B - Add citation-gated sidecar script only

Selected. It provides bounded sidecar hypotheses, citation extraction, and future EvidenceAtom candidate refs without changing active runtime behavior.

## Selected Design

Add `scripts/brave_answers_sidecar.py`.

Rules:
- Input must be QueryPack-shaped JSON with `authority_level=sidecar_only`.
- Request endpoint is `brave/answers/chat_completions` (`POST /res/v1/chat/completions`).
- Model must default to `brave`.
- Citation mode must set `stream=true` and `enable_citations=true`; enum and usage stream tags are telemetry only.
- Answer prose persists only as bounded `derived_context_preview` plus digest.
- Raw stream frames are never persisted.
- Citation URLs become `citation_evidence_candidates` metadata only.
- If citation count is zero, `promotion_eligible=false` and no evidence candidates are emitted.
- Dry-run works without API key/network.

## Acceptance Criteria

1. Sidecar blocks packs that are not `authority_level=sidecar_only`.
2. Dry-run emits a review-only sidecar record without API key/network.
3. Mocked streaming response with citations emits citation candidates and `promotion_eligible=true`.
4. Mocked response without citations emits no candidates and `promotion_eligible=false`.
5. Raw answer stream frames and API keys are not persisted.
6. Tests prove answer text is not canonical authority.
7. No scanner/wake/report/delivery behavior changes.

## Test Plan

- `test_answers_sidecar_blocks_non_sidecar_authority`
- `test_answers_sidecar_dry_run_requires_no_api_key_or_network`
- `test_answers_sidecar_extracts_citations_as_evidence_candidates`
- `test_answers_without_citations_cannot_promote`
- `test_answers_sidecar_sanitizes_api_key_and_raw_stream_frames`

## Non-Goals

- Do not wire into follow-up runtime.
- Do not create EvidenceAtoms directly.
- Do not use answer prose as canonical claim input.
- Do not implement research-mode long-running orchestration.
- Do not change OpenClaw parent provider.

## Critic Requirements

Implementation critic must verify:
- sidecar-only authority
- citation-only promotion
- answer prose is DerivedContext/Hypothesis only
- no raw stream/frame persistence
- no hot-path integration
- dry-run/mocked tests only, no live API calls
