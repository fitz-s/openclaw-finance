# Ingestion Fabric Phase 11 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-11-reader-bundle-followup-slices-ralplan.md`
- `docs/openclaw-runtime/contracts/reader-bundle-contract.md`
- `scripts/finance_report_reader_bundle.py`
- `scripts/finance_followup_context_router.py`
- `tests/test_report_reader_bundle.py`
- `tests/test_followup_context_router_phase6.py`

Checks:
- Reader bundle now loads SourceAtoms, ClaimGraph, ContextGaps, and SourceHealth.
- Object cards carry linked claims, atoms, context gaps, lane coverage, and source-health summary.
- Bundle emits `followup_slice_index` keyed by handle and verb.
- Each slice carries evidence slice ID, source ID/name, version, content hash, retrieval score, permission metadata, and `no_execution=true`.
- Follow-up router returns bundle slices for object handles and uses bundle slice evidence IDs when available.
- Router coverage exposes bundle lane coverage, linked claims, linked context gaps, and source-health summary.
- Raw Discord thread history remains forbidden; bundle is memory, thread is UI.
- Existing campaign alias/cache routing still passes tests.

Risks:
- Claim-to-card matching is heuristic and may miss some links until stronger entity mapping exists.
- Retrieval score is currently deterministic/simple; later phases can make it ranking-aware.
- Follow-up answer generation still depends on downstream answer guard and Discord router integration.

Required follow-up:
- Phase 12 parent handoff should document how runtime thread follow-up rehydrates bundle slices.
- Phase 13 closeout should include slice coverage metrics and insufficient-data monitoring.

Commit gate: pass.
