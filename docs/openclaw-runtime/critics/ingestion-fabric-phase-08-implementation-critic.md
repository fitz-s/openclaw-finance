# Ingestion Fabric Phase 08 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-08-finance-worker-reducer-ralplan.md`
- `scripts/finance_worker.py`
- `tests/test_finance_worker_reducer_phase08.py`

Checks:
- `finance_worker.py` keeps legacy `accumulated` output intact for old consumers.
- Worker state now marks `worker_role=compatibility_reducer` and `accumulated_authority=legacy_bridge_not_canonical_ingestion`.
- Worker best-effort writes SourceAtoms, ClaimGraph, ContextGaps, and `finance-worker-reducer-report.json`.
- Reducer report includes migration/evaluation mode, idempotency key, claim/gap counts, reduced legacy observation preview, parity basis, and explicit authority boundary.
- ClaimGraph + ContextGap compilation remains shadow-only and cannot block scanner/gate behavior.
- `reduce_claims_to_legacy_observations()` proves claims/gaps can project into legacy observation-shaped rows without making them canonical.
- No parent cron, wake policy, report delivery, thresholds, or execution authority changed.

Risks:
- This is still a bridge: active consumers continue to read legacy `accumulated` until later phases move packet/follow-up/undercurrent to claim/gap artifacts.
- Direct live worker execution was not used in verification because it would process/archive real runtime buffer files.
- Parity metrics are basic counts/hashes now; later cutover needs stronger old/new output comparison.

Required follow-up:
- Phase 09 should consume reducer report and Brave/Answers quota metadata into source health.
- Phase 10/11 should move undercurrent/follow-up consumers toward ClaimGraph/ContextGap directly.

Commit gate: pass.
