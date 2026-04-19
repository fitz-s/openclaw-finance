# Finance Thread Lifecycle Contract

Finance follow-up thread registry records are runtime routing cache entries, not memory or audit logs.

## Record Fields

```json
{
  "created_at": "...",
  "updated_at": "...",
  "last_user_message_at": null,
  "last_bot_reply_at": null,
  "last_activity_at": "...",
  "inactive_after_hours": 72,
  "lifecycle_status": "active|inactive|archived|deleted|registry_pruned",
  "account_id": "default",
  "allowed_reply_agent": "Mars"
}
```

## Rules

- Default inactive timeout is 72 hours.
- Inactive records are removed from active follow-up registry.
- Registry removal does not delete report archive, decision log, or reviewer packet data.
- Discord thread archive/delete is parent runtime behavior and is not required for finance-side pruning.
- Thread history is UI only; bundle/archive is memory.
