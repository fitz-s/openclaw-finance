# RALPLAN Ingestion Fabric Phase 08: finance_worker Reducer Migration

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Downgrade `finance_worker.py` from canonical ingestion surface into a compatibility reducer. It must keep old `state/intraday-open-scan-state.json.accumulated` consumers working, while also producing EvidenceAtom -> ClaimGraph -> ContextGap shadow artifacts and a reducer report that makes the authority boundary explicit.

## RALPLAN-DR Summary

### External Scout Inputs

Source class: migration flags, event-sourcing, CDC, schema evolution, and idempotency guidance.

Integrated findings:
- Use a compatibility bridge rather than hard swap; run legacy and new reducer outputs in parallel during migration.
- Shadow-write claim/gap reducer outputs while keeping old summaries for comparison.
- Reducer processing needs stable idempotency keys based on event/claim identity.
- Preserve provenance and correlation through source atoms, claim IDs, graph hashes, and gap hashes.
- Use schema-versioned bridge artifacts instead of in-place breaking changes.
- Cutover later should be gated by parity/health metrics, not by the mere existence of new files.

Reference links from scout:
- LaunchDarkly migration solutions: https://launchdarkly.com/docs/guides/account/migrating-solutions
- LaunchDarkly migration flags: https://launchdarkly.com/docs/home/flags/migration
- Microsoft Fabric event delivery guarantees: https://learn.microsoft.com/en-us/fabric/real-time-hub/fabric-event-delivery-guarantees
- AWS idempotency guidance: https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_prevent_interaction_failure_idempotent.html
- Azure event sourcing pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing
- Confluent schema evolution: https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html

### Principles

1. **Compatibility first.** Do not remove or rewrite `accumulated` in this phase.
2. **Claims/gaps become the richer substrate.** Worker should parallel-write ClaimGraph and ContextGap after SourceAtoms.
3. **Reducer output is advisory.** Legacy observations reduced from claims are compatibility rows, not canonical truth.
4. **Idempotent shadow writes.** Same inputs should produce stable hashes/reports.
5. **No hot-path break.** Worker errors in shadow compilers must not block scanner/gate behavior.

### Decision Drivers

1. Review2 identifies `finance_worker.py` as the current lossy bottleneck.
2. Existing worker already writes SourceAtoms best-effort but does not compile claims/gaps in closure.
3. Existing consumers still depend on `state/intraday-open-scan-state.json.accumulated`.
4. Later phases need packet/follow-up/undercurrent to consume claim/gap artifacts.

### Selected Design

Modify `scripts/finance_worker.py`:
- Keep legacy buffer processing and `accumulated` unchanged.
- Add `reduce_claims_to_legacy_observations()` helper for compatibility projection.
- After writing state and SourceAtoms, compile ClaimGraph and ContextGaps best-effort.
- Write `state/finance-worker-reducer-report.json` containing role, migration/evaluation mode, idempotency key, source atom/claim/gap counts, reduced observation preview, parity basis, and explicit authority boundary.
- Add state metadata showing `worker_role=compatibility_reducer` and `accumulated_authority=legacy_bridge_not_canonical_ingestion`.

## Acceptance Criteria

1. Existing `accumulated` behavior remains compatible.
2. Worker can reduce ClaimGraph + ContextGap into legacy observation-shaped rows.
3. Worker best-effort writes source atoms, claim graph, context gaps, and reducer report.
4. Reducer report states that accumulated observations are legacy bridge, not canonical ingestion.
5. Tests prove reducer output is deterministic and no-execution.
6. Full test/audit suite passes.

## Non-Goals

- Do not remove legacy observation schema.
- Do not change gate thresholds.
- Do not update parent OpenClaw cron jobs.
- Do not make claim/gap artifacts active wake authority yet.

## Test Plan

- `test_reduce_claims_to_legacy_observations_uses_claim_and_gap_metadata`
- `test_finance_worker_shadow_reducer_report_marks_legacy_bridge`
- `test_finance_worker_parallel_claim_gap_write_is_best_effort`
- Existing full suite.

## Critic Requirements

Implementation critic must verify:
- old consumers survive
- no hot-path blocking from shadow reducers
- claims/gaps compile in worker closure
- worker role explicitly downgraded
- no execution/trading authority added
