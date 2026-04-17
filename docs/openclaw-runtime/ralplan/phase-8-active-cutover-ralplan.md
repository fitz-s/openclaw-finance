# RALPLAN Phase 8: Active Cutover

Status: blocked_until_parent_runtime_gate
Go for implementation: false
Deliberate RALPLAN: true

Prior implementation commits:
- Phase 1 Source Health: `fdae2c9`
- Phase 2 Evidence Substrate: `29c1ac7`
- Phase 3 Undercurrents: `bc8154a`
- Phase 4 Campaign Lifecycle: `2f44490`
- Phase 5 Board Package: `2d890ed`
- Phase 6 Follow-up Slices: `f2c2a5b`
- Phase 7 Learning: `c8f1e17`

## Task Statement

Cut over from finance-local shadow/package artifacts to active Discord campaign board delivery and thread follow-up.

This is the first phase that may touch parent runtime delivery behavior. It is blocked until parent runtime gate checks and explicit cutover authority are satisfied.

## Current Facts

Fact: finance repo now emits all required local artifacts:
- `campaign-board.json`
- `campaign-stage-history.jsonl`
- `campaign-threads.json`
- `discord-campaign-board-package.json`
- `campaign-cache.json`
- `followup-context-route.json`
- follow-up answer guard validation
- source ROI / context coverage audits

Fact: active OpenClaw cron delivery currently uses announce stdout. It does not maintain persistent editable board messages or create campaign threads.

Fact: existing cron payloads already target Discord channel `channel:1479790104490016808` for finance reports.

Fact: parent workspace is dirty and outside finance repo ownership. Parent runtime changes need gate discipline.

## Principles

1. No route-card-only fallback. Worst case must return full readable `discord_primary_markdown` or full markdown.
2. Main channel delivery must not depend on thread router success.
3. Board/thread cutover must be reversible by switches.
4. Thread is UI, bundle/campaign artifacts are memory.
5. No execution authority, no trading semantics, no threshold mutation.
6. Runtime success requires observed delivery evidence, not config presence.

## Decision Drivers

1. User experience requires persistent Discord-native boards and thread follow-up.
2. Active delivery path is high blast radius and must be gated.
3. Finance-local artifacts now provide enough contract surface for a parent adapter to consume safely.

## Viable Options

### Option A: Staged active cutover with feature flags

Add parent runtime support behind switches:
- `DISCORD_BOARDS_ENABLED`
- `DISCORD_THREADS_ENABLED`
- `FOLLOWUP_ROUTER_ENABLED`

Start in test/private target, then promote to finance channel after observed evidence.

Pros:
- Safest active path.
- Clear rollback.
- Main report fallback remains intact.

Cons:
- Requires parent runtime edits and gate/restart process.

### Option B: Direct production cutover

Patch parent runtime and immediately use boards/threads in finance channel.

Pros:
- Fastest UX improvement.

Cons:
- Too risky; no shadow adapter observation.

### Option C: Keep stdout-only forever

Use `finance_discord_report_job.py` stdout as sole delivery path.

Pros:
- No parent runtime risk.

Cons:
- Does not achieve persistent boards or thread follow-up.

## Selected Plan

Choose Option A: staged active cutover with feature flags and observed delivery proof.

## Required Parent Runtime Work

Parent adapter must consume `discord-campaign-board-package.json` and support:
- main-channel primary post/update
- persistent Live Board message update
- persistent Peacetime Board message update
- persistent Risk Board message update
- campaign thread creation/update from `campaign-threads.json`
- main-channel reply redirect, not reasoning ingestion
- thread reply routing to finance follow-up context route

## Required Runtime Switches

Default values before observed cutover:

```text
DISCORD_BOARDS_ENABLED=false
DISCORD_THREADS_ENABLED=false
FOLLOWUP_ROUTER_ENABLED=false
FINANCE_BOARD_TEST_TARGET_ENABLED=false
```

Rollback switches:

```text
DISCORD_BOARDS_ENABLED=false
DISCORD_THREADS_ENABLED=false
FOLLOWUP_ROUTER_ENABLED=false
```

Rollback floor:
- deliver full `discord_primary_markdown` or markdown
- never route-card-only
- no thread dependency for main report

## Required Gate Checks

Before any parent runtime mutation:

```bash
/Users/leofitz/.openclaw/workspace-neptune/.venv/bin/python -m harness.cli gate quick --agent mars modify_cron_jobs
/Users/leofitz/.openclaw/workspace-neptune/.venv/bin/python -m harness.cli gate quick --agent mars config_patch
/Users/leofitz/.openclaw/workspace-neptune/.venv/bin/python -m harness.cli gate quick --agent mars gateway_restart
```

Only run the specific gate needed for the actual action. Gateway restart/reload must go through Neptune/Fitz authority per workspace rules.

## Pre-Mortem

Scenario 1: Board update succeeds but main report becomes unreadable.
- Mitigation: main-channel delivery must read fallback primary independently of board/thread code.

Scenario 2: Threads get created repeatedly or become spam.
- Mitigation: `campaign-threads.json` must persist thread IDs and statuses; idempotency required.

Scenario 3: Follow-up router answers from raw backlog or guesses context.
- Mitigation: parent router must call finance follow-up context route using explicit verb/handle/evidence_slice_id; raw thread history is forbidden.

## Test Plan

Unit tests:
- adapter reads board package and chooses main primary fallback
- board update disabled by switches by default
- thread creation disabled by switches by default
- route-card-only fallback rejected
- follow-up router requires explicit verb/handle/evidence_slice_id

Integration tests:
- dry-run parent adapter produces planned operations without sending Discord messages
- test/private target receives one board update and one thread seed
- main report still delivered when thread router disabled
- deleted thread is marked stale/unbound without blocking main report

Observability:
- `route_card_only_delivery_count = 0`
- `discord_primary_missing_count`
- `board_update_failures`
- `thread_creation_failures`
- `followup_rehydration_failures`
- `main_channel_redirect_count`
- `raw_machine_footer_in_primary_count`
- `object_alias_coverage_rate`

## Acceptance Criteria

- In test target, Live/Scout/Risk board package renders without external side effects until switches are enabled.
- With boards enabled, persistent board messages update idempotently.
- With threads enabled, campaign thread registry records external thread IDs.
- With follow-up enabled, thread replies route through finance follow-up context route.
- Main channel fallback works when thread router is disabled or fails.
- Rollback switches restore primary markdown delivery.
- No execution authority added.

## Rejected Options

Rejected: direct production cutover | too risky without adapter dry run and observed evidence.

Rejected: stdout-only forever | fails persistent board/thread objective.

Rejected: thread history as memory | violates follow-up contract and causes context drift.

## Architect Review

Verdict: APPROVE AS CUTOVER PLAN, BLOCK IMPLEMENTATION UNTIL GATES PASS.

The architecture is now ready for active cutover because finance-local package contracts exist. The only unsafe part is parent runtime mutation, which is correctly gated.

## Critic Review

Verdict: APPROVE PLAN / REJECT IMMEDIATE IMPLEMENTATION.

Reasons:
- Plan has rollback switches and acceptance criteria.
- Plan preserves main-channel fallback.
- Plan requires observed evidence before claiming runtime success.
- Immediate implementation would violate parent runtime gate discipline in the current session.

## Final RALPLAN Verdict

Go for implementation: false until parent runtime gate and explicit cutover authority are satisfied.

Recommended next action:
- Stop at this RALPLAN in finance repo.
- When Fitz authorizes active runtime cutover, run the relevant Neptune gate check first, then implement parent adapter in a separate package with critic before commit/push.
