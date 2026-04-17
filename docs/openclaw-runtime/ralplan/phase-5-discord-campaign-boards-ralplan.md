# RALPLAN Phase 5: Discord Campaign Boards

Status: approved_for_implementation
Go for implementation: true

Prior commits:
- Phase 2 Evidence Substrate: `29c1ac7`
- Phase 3 Undercurrent Enrichment: `bc8154a`
- Phase 4 CampaignProjection 2.0: `2f44490`

## Task Statement

Prepare Discord Campaign Boards as the operator-facing delivery surface while preserving active delivery safety and avoiding gateway/cron/Discord side effects in the first implementation slice.

Phase 5 must split finance-local board packaging from parent runtime cutover.

## Current Facts

Fact: `finance_discord_report_job.py` currently returns `discord_live_board_markdown` first, then `discord_primary_markdown`, then artifact markdown.

Fact: `finance_decision_report_render.py` already emits board markdown fields in the envelope when `campaign-board.json` exists.

Fact: `campaign_projection_compiler.py` now emits campaign board, local stage history, and local thread registry.

Fact: Active OpenClaw cron delivery still posts stdout via announce delivery to Discord. It does not edit persistent board messages or create campaign threads.

Fact: Parent runtime changes touching cron/gateway/Discord adapter require gate discipline and potentially explicit approval/restart handling.

## Principles

1. Main channel readability first: never regress to route-card-only or artifact dump.
2. Board packaging before board mutation: produce a deterministic board payload before any active Discord adapter work.
3. Thread is UI, not memory: thread registry maps UI state, while campaign-board/report-reader bundles remain memory.
4. Failure isolation: thread/router failure must not block full primary report or live board delivery.
5. No active external side effects in finance-local implementation slice.

## Decision Drivers

1. User experience requires Discord-native campaign boards, but active runtime delivery is high-risk.
2. Finance repo can safely produce deterministic board payloads and validation gates.
3. Parent runtime adapter/cutover needs separate gate and possibly restart/reload authority.

## Viable Options

### Option A: Finance-local board delivery package first

Add a finance-local deterministic package script/state that exposes:
- live board markdown
- scout board markdown
- risk board markdown
- thread seed markdown
- thread registry refs
- fallback primary markdown
- safety/validation summary

No Discord API call, no cron change, no parent adapter change.

Pros:
- Lowest risk.
- Testable in finance repo.
- Gives parent adapter a clear contract for later cutover.

Cons:
- Does not yet edit persistent Discord board messages.
- UX improvement only materializes after parent adapter integration.

### Option B: Patch OpenClaw parent delivery adapter now

Modify parent runtime so finance reports update board messages and create threads.

Pros:
- Directly addresses UX.

Cons:
- High blast radius.
- Requires parent runtime discovery, gate checks, and possibly restart/reload.
- Risky while parent workspace is dirty.

### Option C: Change cron prompts to print multiple board messages

Use existing announce delivery to emit live/scout/risk as separate messages.

Pros:
- No adapter engineering.

Cons:
- Creates spam and does not provide persistent editable boards.
- Violates board-not-report-spam direction.

## Selected Plan

Choose Option A for Phase 5 implementation.

Implement finance-local board delivery package and validation without active external side effects.

Later parent adapter/cutover requires a separate RALPLAN/gate or subphase before active Discord mutation.

## Rejected Options

Rejected: Option B in this package | too close to active parent runtime and requires gate/restart discipline.

Rejected: Option C | would degrade UX into board spam instead of persistent campaign surfaces.

Rejected: send test Discord messages from implementation | external side effect and not necessary for contract validation.

## Proposed Finance-Local Output

New state artifact:

```text
state/discord-campaign-board-package.json
```

Shape:

```json
{
  "generated_at": "...",
  "status": "pass|degraded|fail",
  "contract": "discord-campaign-board-package-v1",
  "mode": "finance_local_shadow_package",
  "live_board_markdown": "...",
  "scout_board_markdown": "...",
  "risk_board_markdown": "...",
  "primary_fallback_markdown": "...",
  "thread_seed_markdown": "...",
  "campaign_board_ref": "state/campaign-board.json",
  "thread_registry_ref": "state/campaign-threads.json",
  "report_envelope_ref": "state/finance-decision-report-envelope.json",
  "delivery_instructions": {
    "main_channel_primary": "live_board_markdown_or_primary_fallback",
    "persistent_board_updates": "parent_runtime_only",
    "thread_creation": "parent_runtime_only"
  },
  "no_external_side_effects": true,
  "no_execution": true
}
```

## Authority Boundary Impact

Phase 5 finance-local implementation may:
- add board package compiler
- add validator tests
- add docs/contracts
- update `finance_discord_report_job.py` only if behavior remains backward-compatible and stdout still returns one safe primary surface

Phase 5 finance-local implementation must not:
- call Discord API
- edit messages
- create threads
- modify cron jobs
- modify gateway config
- restart/reload gateway
- bypass delivery safety
- change wake/judgment behavior

## Files Likely Touched

- `scripts/finance_discord_campaign_board_package.py` (new)
- `scripts/finance_discord_report_job.py` only if needed for packaging command integration
- `scripts/finance_report_product_validator.py` only for package validation if needed
- `docs/openclaw-runtime/contracts/discord-campaign-board-package-contract.md`
- tests for package compiler
- snapshot manifest/exporter

## Test Plan

Required tests:
- `test_board_package_contains_live_scout_risk_and_fallback`
- `test_board_package_has_no_external_side_effects`
- `test_board_package_preserves_primary_fallback_when_boards_missing`
- `test_board_package_references_thread_registry_but_does_not_create_threads`
- `test_report_job_stdout_behavior_still_safe`
- existing Discord operator surface tests pass

## Rollback Plan

- Remove board package compiler and contract/tests.
- Active report job remains able to return `discord_live_board_markdown` or `discord_primary_markdown` fallback.
- No parent runtime rollback needed because no active adapter changed.

## Acceptance Criteria

- Finance repo produces deterministic board package artifact.
- Artifact clearly separates main-channel primary, persistent board update instructions, and thread creation instructions.
- No external Discord side effects.
- Full tests pass.
- Critic verifies no active runtime mutation before commit/push.

## Architect Review

Verdict: APPROVE WITH HARD BOUNDARY.

Steelman antithesis: Phase 5 should implement the actual parent Discord adapter because UX is the point. This is correct for final product, but unsafe as the first package because adapter cutover touches active runtime. A deterministic package contract is the necessary bridge.

Tradeoff: This package will not immediately fix persistent Discord board edit behavior. It does reduce future adapter ambiguity and prevents another route-card regression.

Required narrowing:
- No Discord API calls.
- No cron/gateway config edits.
- No active thread creation.

## Critic Review

Verdict: APPROVE.

Checks:
- Option A is the only safe implementation slice.
- External side effects are forbidden.
- Tests are concrete.
- Rollback is trivial.

Implementation critic requirement:
- Before commit/push, critic must verify no Discord API call, no cron/gateway mutation, no thread creation, no delivery safety bypass, and preserved fallback primary surface.

## Final RALPLAN Verdict

Go for implementation: true.

Recommended mode: single executor lane. Parent adapter work must be a separate gated package.
