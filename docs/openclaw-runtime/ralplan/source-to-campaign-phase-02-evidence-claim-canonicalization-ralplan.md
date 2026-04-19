# RALPLAN Source-to-Campaign Phase 02: EvidenceAtom And ClaimAtom Canonicalization

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Harden the existing EvidenceAtom and ClaimAtom shadow substrate so source provenance, rights, lane/sublane, and export policy survive before observations are compressed into summaries.

This phase is compatibility-first. It keeps old fields and does not change wake, judgment, delivery, Discord output, or execution authority.

## Principles

1. Never compress before provenance.
2. Preserve backward compatibility for existing observation consumers.
3. ClaimAtoms must carry enough source metadata to support future follow-up slicing and reviewer replay.
4. Rights/export policy must be explicit before reviewer/operator surfaces use evidence text.
5. This phase remains shadow-only.

## Decision Drivers

1. Existing `source_atom_compiler.py` writes useful atoms but still exposes a `raw_snippet` as the main text field.
2. Existing `claim_graph_compiler.py` derives claims but does not carry source rights/reliability/sublane enough for later source/follow-up slicing.
3. Later report-time replay and reviewer packet exact replay need stable lineage fields now.

## Viable Options

Option A: Remove `raw_snippet` immediately and replace it with raw vault refs.
- Pros: strongest rights boundary.
- Cons: breaks existing tests and consumers before archive/replay layer exists.

Option B: Keep current atom/claim shape unchanged.
- Pros: zero risk.
- Cons: fails the review requirement; provenance and rights remain too weak.

Option C: Add canonical fields while keeping legacy fields.
- Pros: preserves compatibility and creates migration path.
- Cons: temporary duplicate text fields.

Selected: Option C.

Rejected: Option A | too disruptive before report archive and raw vault are implemented.
Rejected: Option B | does not move evidence fabric forward.

## Implementation Scope

- Extend source atom contract with canonical fields: `lane`, `source_sublane`, `raw_snippet_ref`, `safe_excerpt`, `export_policy`, `raw_snippet_redaction_required`.
- Extend claim atom contract with source metadata and lineage fields.
- Update `source_atom_compiler.py` to populate canonical fields deterministically.
- Update `claim_graph_compiler.py` to use safe excerpt when available and preserve source metadata.
- Add tests for rights/export policy and claim lineage.

## Acceptance Criteria

- Every atom has lane/sublane and rights/export fields.
- Restricted/unknown sources have `safe_excerpt=None` and `raw_snippet_redaction_required=true`.
- Raw snippet remains bounded and marked legacy/internal-compatible.
- Every claim has `atom_id`, `source_id`, `source_lane`, `source_sublane`, reliability/uniqueness, and evidence rights.
- Full test suite remains green.

## Test Plan

- `test_source_atom_adds_canonical_rights_and_safe_excerpt_fields`
- `test_claim_atom_preserves_source_metadata_for_lineage`
- existing source atom/claim/context tests

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-02-implementation-critic.md` after implementation.
