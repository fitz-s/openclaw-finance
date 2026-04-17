# Ingestion Fabric Phase 10 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-10-claim-aware-undercurrents-ralplan.md`
- `scripts/event_watcher.py`
- `scripts/undercurrent_compiler.py`
- `tests/test_event_watcher_claim_aware_phase10.py`
- `tests/test_undercurrent_engine.py`

Checks:
- Event watcher can detect ClaimGraph-linked signals by ticker/theme without relying on old theme overlap.
- Event watcher suppresses already-seen claim IDs and exposes linked ContextGap IDs.
- Event watcher includes degraded source-health metadata in claim signal details.
- Old price/theme observation fallback remains in place.
- Undercurrent compiler now defaults to finance-local `state/source-health.json`.
- Undercurrents treat freshness, rights, quota, and coverage degradation as source-health degradation.
- Undercurrents carry claim persistence score, claim IDs, degraded source reasons, quota-degraded count, and unavailable count.
- PACKET_UPDATE_ONLY remains `board_mutation_only`; wake impact remains `none`.
- No execution, threshold, report delivery, or judgment authority was added.

Risks:
- Claim matching is still heuristic text/entity matching; later phases may need stronger entity/coreference normalization.
- Source independence is approximated by source/lane diversity; dependency/copy-chain detection remains future work.
- Event watcher `tick` still can trigger its existing renderer when updates are detected; this phase changes detection inputs, not delivery policy.

Required follow-up:
- Phase 11 should expose claim/gap/source-health slices in reader bundle/follow-up routing.
- Phase 12 should decide whether parent market-ingest owns source-health paths long term.

Commit gate: pass.
