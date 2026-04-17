# RALPLAN Source-to-Campaign Phase 10: 72h Inactive Thread Lifecycle

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Prevent finance follow-up threads from accumulating forever by removing inactive threads from the active follow-up hot path after 72 hours of inactivity.

This phase is finance-side lifecycle management. It does not delete Discord threads by default and does not change parent Discord inbound activity tracking.

## Principles

1. Thread registry is a bounded runtime routing index, not long-term memory.
2. 72h inactive means no user/bot/activity timestamp inside the window.
3. Removing from registry disables hot-path follow-up but preserves report archive and decision logs.
4. Deletion/archive of Discord threads requires parent/Discord support and should not be default.
5. Mars/default ownership remains enforced.

## Decision Drivers

1. User explicitly requested inactive finance threads disappear after 72h.
2. Existing registry TTL is too coarse and based on updated_at, not activity.
3. Parent inbound handler activity updates are a later parent-side dependency.

## Selected Plan

- Extend registry records with lifecycle fields.
- Add inactive pruning to existing repair path.
- Add a dedicated `finance_thread_lifecycle_gc.py` wrapper for manual/cron use.
- Keep Discord deletion out of scope; registry removal is hot-path disappearance.

## Acceptance Criteria

- Records include `created_at`, `last_activity_at`, `inactive_after_hours`, and `lifecycle_status`.
- Inactive records older than 72h are pruned from active registry.
- Recent activity keeps a record active.
- Missing bundle / max records / TTL pruning still work.
- Report job repair path applies inactive pruning by default.

## Test Plan

- `test_thread_lifecycle_fields_added_by_upgrade_record`
- `test_prune_threads_drops_inactive_after_72h`
- `test_recent_thread_activity_survives_inactive_prune`
- existing follow-up registry tests

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-10-implementation-critic.md` after implementation.
