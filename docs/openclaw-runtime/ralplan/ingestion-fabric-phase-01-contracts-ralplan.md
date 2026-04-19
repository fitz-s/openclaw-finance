# RALPLAN Ingestion Fabric Phase 01: QueryPack / SourceFetchRecord Contracts

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Add the canonical contracts that review2 requires before implementing deterministic Brave fetchers: QueryPack, SourceFetchRecord, and EvidenceAtom bridge semantics.

This phase is contracts/tests only. It does not fetch data or alter runtime behavior.

## Principles

1. Query planning is separate from source fetching.
2. Fetch records are separate from evidence atoms.
3. Brave Answers is sidecar-only.
4. Scanner is not canonical ingestion.
5. No runtime behavior changes in this phase.

## Acceptance Criteria

- QueryPack contract exists and includes lane, purpose, freshness/date filters, allowed domains, authority_level, forbidden actions.
- SourceFetchRecord contract exists and includes endpoint, request params, quota state, result count, status, watermark key.
- EvidenceAtom contract explicitly references SourceFetchRecord / fetch_id bridge.
- Tests guard sidecar-only Answers and scanner downgrade semantics.

## Critic Review

Deferred to `docs/openclaw-runtime/critics/ingestion-fabric-phase-01-implementation-critic.md`.
