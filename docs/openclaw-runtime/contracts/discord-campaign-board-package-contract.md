# Discord Campaign Board Package Contract

The Discord Campaign Board Package is a finance-local artifact that prepares board surfaces for a future parent Discord adapter.

It has no external side effects.

## Authority

The package does not change the finance authority chain:

`ContextPacket -> WakeDecision -> JudgmentEnvelope -> product report -> validator -> decision log -> delivery safety`

It does not call Discord, edit messages, create threads, mutate cron jobs, restart/reload gateway, or bypass delivery safety.

## Shape

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
  "campaign_board_ref": "...",
  "thread_registry_ref": "...",
  "report_envelope_ref": "...",
  "delivery_instructions": {
    "main_channel_primary": "live_board_markdown_or_primary_fallback",
    "persistent_board_updates": "parent_runtime_only",
    "thread_creation": "parent_runtime_only"
  },
  "no_external_side_effects": true,
  "no_execution": true
}
```

## Fallback Floor

If persistent board update or thread creation is unavailable, the parent runtime must fall back to a full readable primary surface. It must never fall back to route-card-only primary delivery.

## Forbidden In Phase 5 Finance-Local Slice

- Discord API calls.
- Message edits.
- Thread creation.
- Cron job mutation.
- Gateway restart/reload.
- Delivery safety bypass.
- Execution/trade semantics.
