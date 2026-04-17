# RALPLAN Ingestion Fabric Phase 11: Reader Bundle And Follow-up Slice Indexing

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Make reader bundles carry claim IDs, lane coverage, source health, context gaps, and a follow-up slice index so Discord follow-up can rehydrate from immutable bundle slices instead of raw thread history.

## RALPLAN-DR Summary

### External Scout Inputs

Source class: retrieval/RAG, locally attributable generation, file-search citations, compact session memory, insufficient-context RAG, and retrieval safety guidance.

Integrated findings:
- Treat every reader-bundle slice as a provenance-bearing evidence unit.
- Store stable slice metadata: slice ID, source name, version, content hash, retrieval score, and permission metadata.
- Prefer evidence-sliced retrieval over raw thread replay.
- Emit structured trace objects, not just inline citations.
- Use explicit insufficient-data behavior when required evidence is missing.
- Treat retrieved content as untrusted and filter by permission metadata before generation.

Reference links from scout:
- OpenAI Retrieval: https://developers.openai.com/api/docs/guides/retrieval
- OpenAI File Search: https://developers.openai.com/api/docs/guides/tools-file-search
- OpenAI Session Memory: https://developers.openai.com/cookbook/examples/agents_sdk/session_memory
- Google sufficient context in RAG: https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/
- Google Attribute First, then Generate: https://research.google/pubs/attribute-first-then-generate-locally-attributable-grounded-text-generation/
- ACL Provenance: https://aclanthology.org/2024.emnlp-industry.97/

### Principles

1. Bundle slices, not thread history, are follow-up memory.
2. Each slice must carry provenance and permission metadata.
3. Missing evidence should produce insufficient data, not generic inference.
4. Bundle enrichment remains derived view, not report authority.
5. Raw source dumps and raw Discord backlog are forbidden in follow-up context.

## Selected Design

Modify `scripts/finance_report_reader_bundle.py`:
- Load SourceAtoms, ClaimGraph, ContextGaps, and SourceHealth.
- Enrich object cards with `linked_claims`, `linked_atoms`, `linked_context_gaps`, `lane_coverage`, and `source_health_summary`.
- Add `followup_slice_index` keyed by object handle and verb.
- Add stable `content_hash`, `retrieval_score`, `source_id`, `source_name`, `version`, and `permission_metadata` per slice.

Modify `scripts/finance_followup_context_router.py`:
- Resolve bundle slices for object handles.
- Include bundle slice coverage, source health, claims, atoms, and context gaps in route output.
- Prefer bundle slice `evidence_slice_id` when available.

Update reader bundle contract.

## Acceptance Criteria

1. Bundle exposes evidence slices.
2. Object cards carry claim IDs, atom IDs, context gap IDs, lane coverage, and source health summary.
3. Follow-up router returns bundle slice metadata for object handles.
4. Router no longer needs raw thread history for evidence selection.
5. Existing campaign/router behavior remains compatible.

## Non-Goals

- Do not implement Discord listener changes.
- Do not call an LLM.
- Do not make bundle canonical report authority.
- Do not expose raw source snippets.

## Critic Requirements

Critic must verify provenance fields, permission metadata, no raw thread history dependency, and compatibility with existing follow-up router behavior.
