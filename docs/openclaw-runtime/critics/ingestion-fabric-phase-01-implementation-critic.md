# Ingestion Fabric Phase 01 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-01-contracts-ralplan.md`
- `docs/openclaw-runtime/contracts/query-pack-contract.md`
- `docs/openclaw-runtime/contracts/source-fetch-record-contract.md`
- `docs/openclaw-runtime/contracts/source-atom-contract.md`
- `tests/test_ingestion_fabric_phase01_contracts.py`

Checks:
- QueryPack contract separates query planning from evidence and includes lane, purpose, freshness/date filters, allowed domains, authority level, and forbidden actions.
- SourceFetchRecord contract records endpoint, request params, quota state, result count, status, error code, and watermark key.
- EvidenceAtom contract now includes `fetch_id` bridge semantics for deterministic fetchers.
- Brave Answers sidecar-only rule is explicit.
- No runtime source fetching or active behavior changed.

Risks:
- Contracts alone do not improve ingestion until Brave fetchers and source memory are implemented.

Required follow-up:
- Phase 2 should audit current Brave API runtime capabilities and gaps against these contracts.

Verification evidence:
- `python3 -m pytest -q tests/test_ingestion_fabric_phase01_contracts.py`

Commit gate: pass.
