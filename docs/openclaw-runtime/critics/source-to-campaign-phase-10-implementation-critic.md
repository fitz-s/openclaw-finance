# Source-to-Campaign Phase 10 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/source-to-campaign-phase-10-thread-lifecycle-ralplan.md`
- `docs/openclaw-runtime/contracts/finance-thread-lifecycle-contract.md`
- `scripts/finance_followup_thread_registry_repair.py`
- `scripts/finance_thread_lifecycle_gc.py`
- `tests/test_followup_thread_registry_repair.py`
- `tests/test_thread_lifecycle_gc_phase10.py`

Checks:
- Registry records now include lifecycle fields: created_at, last_user_message_at, last_bot_reply_at, last_activity_at, inactive_after_hours, and lifecycle_status.
- Default inactivity window is 72 hours.
- Inactive records are pruned from the active follow-up registry while report archive/decision records remain untouched.
- Dedicated GC wrapper explicitly does not delete Discord threads.
- Existing TTL, missing bundle, max-record, Mars/default ownership, and route repair behavior remain intact.

Risks:
- Parent Discord inbound handler does not yet update last_user_message_at/last_bot_reply_at automatically. Until then, updated_at or manually repaired activity fields act as fallback.
- Removing from registry means old public Discord threads may still exist visually, but they no longer enter finance follow-up hot path.

Required follow-up:
- Parent runtime should update lifecycle activity fields on finance thread inbound/outbound events.
- If true Discord archive/delete is desired, add a separate parent/Discord RALPLAN with permission checks.

Verification evidence:
- `python3 -m pytest -q tests/test_followup_thread_registry_repair.py tests/test_thread_lifecycle_gc_phase10.py`
- Full tests and compileall before commit.

Commit gate: pass.
