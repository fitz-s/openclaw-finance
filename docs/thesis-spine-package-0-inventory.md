# Thesis Spine Package 0 Inventory

Date: 2026-04-15
Package: Freeze and Reality Reconciliation
Status: implementation inventory

## Visionist Precheck

Target shape:

- Finance remains an OpenClaw-embedded, review-only subsystem.
- The active hot path remains `ContextPacket -> WakeDecision -> JudgmentEnvelope -> product report -> decision log -> delivery safety`.
- Thesis Spine objects are persistent state references, not a new user-visible cognition path.
- Package 0 must not enable a new cron, restart OpenClaw, change delivery, or change execution authority.

Primary failure to avoid:

- Treating the partial Thesis Spine draft as already merged runtime truth.
- Creating a second active report path.
- Letting persistent objects become stale memory or free-text investment claims.

## Current Finance Repo Workset

Repository: `/Users/leofitz/.openclaw/workspace/finance`

Tracked modified files:

| File | Package | Classification | Reason |
| --- | --- | --- | --- |
| `scripts/finance_decision_log_compiler.py` | Package 3 | Keep with review | Carries optional thesis/scenario/opportunity/invalidator refs into decision log. Must remain optional and provenance-bound. |
| `scripts/gate_evaluator.py` | Package 2/3 | Revise before merge | Calls the reducer in the wake pipeline. Must stay non-blocking and shadow-safe; reducer failures must not suppress scanner/gate behavior. |
| `scripts/judgment_envelope_gate.py` | Package 3 | Keep with review | Propagates packet refs into deterministic fallback judgment. Must not change adjudication semantics. |
| `tools/audit_operating_model.py` | Package 8 | Defer as reviewer-visibility work | Adds Thesis Spine audit expectations. Should only become strict after contracts are accepted. |
| `tools/export_openclaw_runtime_snapshot.py` | Package 8 | Keep with review | Exports thesis contracts/schemas for GitHub reviewers. Must remain sanitized and not imply live runtime proof. |
| `tools/export_parent_dependency_inventory.py` | Package 8 | Keep with review | Expands parent dependency map. Must distinguish local snapshot from canonical parent runtime. |

Untracked finance files:

| File | Package | Classification | Reason |
| --- | --- | --- | --- |
| `scripts/thesis_spine_util.py` | Package 2 | Keep with review | Shared deterministic helpers for reducers. Must not add dependencies. |
| `scripts/watch_intent_compiler.py` | Package 2 | Keep with review | Converts resolved universe into explicit capital intent objects. Must separate fallback data from user intent. |
| `scripts/thesis_registry_compiler.py` | Package 2 | Keep with review | Builds initial ThesisCard registry from WatchIntent. Must mark generated theses as immature/watch, not investment conclusions. |
| `scripts/thesis_state_reducer.py` | Package 2 | Keep with review | Runs reducers in deterministic order. Must be idempotent. |
| `scripts/opportunity_queue_builder.py` | Package 2 | Keep with review | Converts unknown discovery into lifecycle candidates. Must not re-label holdings as discovery. |
| `scripts/invalidator_ledger_compiler.py` | Package 2 | Keep with review | Builds invalidator ledger from packet contradictions/judgment invalidators. Must preserve refs and timestamps. |

## Parent Workspace Workset

These files live outside the finance git repo but are load-bearing for the embedded OpenClaw runtime.

Contract drafts present:

- `/Users/leofitz/.openclaw/workspace/systems/thesis-spine-contract.md`
- `/Users/leofitz/.openclaw/workspace/systems/thesis-card-contract.md`
- `/Users/leofitz/.openclaw/workspace/systems/scenario-card-contract.md`
- `/Users/leofitz/.openclaw/workspace/systems/opportunity-queue-contract.md`
- `/Users/leofitz/.openclaw/workspace/systems/invalidator-ledger-contract.md`

Schema drafts present:

- `/Users/leofitz/.openclaw/workspace/schemas/watch-intent.schema.json`
- `/Users/leofitz/.openclaw/workspace/schemas/thesis-card.schema.json`
- `/Users/leofitz/.openclaw/workspace/schemas/scenario-card.schema.json`
- `/Users/leofitz/.openclaw/workspace/schemas/opportunity-queue.schema.json`
- `/Users/leofitz/.openclaw/workspace/schemas/invalidator-ledger.schema.json`

Reference-bearing existing schemas:

- `/Users/leofitz/.openclaw/workspace/schemas/packet.schema.json`
- `/Users/leofitz/.openclaw/workspace/schemas/wake-decision.schema.json`
- `/Users/leofitz/.openclaw/workspace/schemas/judgment-envelope.schema.json`
- `/Users/leofitz/.openclaw/workspace/schemas/decision-log.schema.json`

Runtime draft touchpoints:

- `/Users/leofitz/.openclaw/workspace/services/market-ingest/packet_compiler/compiler.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/wake_policy/policy.py`
- `/Users/leofitz/.openclaw/workspace/ops/tests/test_judgment_envelope_gate.py`
- `/Users/leofitz/.openclaw/workspace/ops/scripts/finance_contract_schema_validate.py`
- `/Users/leofitz/.openclaw/workspace/ops/fixtures/finance_semantic_contracts/*.json`

Classification:

- Keep Package 1 contracts/schemas if schema validation passes.
- Keep Package 3 packet/wake/judgment refs only if they are optional and backward compatible.
- Keep fixtures/tests only if they prove the ref chain without creating a mandatory live dependency.

## Explicitly Out of Scope for Package 0

- No `cron/jobs.json` edits.
- No OpenClaw restart or gateway reload.
- No report cutover.
- No Discord delivery test.
- No sidecar job.
- No execution or trading adapter.
- No automatic threshold mutation.

## Critic Gate

The current draft is acceptable to continue only if the following remain true:

1. Thesis refs are optional metadata, not a second cognition path.
2. Reducers are deterministic and local-state based.
3. Report delivery cannot bypass `JudgmentEnvelope -> product validation -> decision log -> safety`.
4. Parent workspace changes are documented as load-bearing runtime dependencies, not hidden inside the finance repo.
5. Deprecated renderer/template surfaces are not revived.

Current verdict: pass to Package 1/2 review, with one required revision: keep `gate_evaluator.py` reducer invocation non-blocking and shadow-safe.

## Review Gate

Review evidence required before Package 1 starts:

- Finance repo status is limited to Thesis Spine files.
- Parent workspace Thesis Spine files are listed explicitly.
- No cron/restart/config changes are part of this package.
- Rollback is file-scoped and does not require destructive workspace reset.

Current review verdict: Package 0 can proceed to verification.

## Rollback

Finance repo rollback scope:

- Revert modified finance files listed above.
- Remove six untracked reducer/helper scripts if the Thesis Spine path is rejected.

Parent workspace rollback scope:

- Remove new Thesis Spine contract/schema/fixture files.
- Revert optional ref additions in packet/wake/judgment/decision-log schemas and packet/wake runtime touchpoints.

Do not use `git reset --hard` because the surrounding OpenClaw workspace contains unrelated live changes.

