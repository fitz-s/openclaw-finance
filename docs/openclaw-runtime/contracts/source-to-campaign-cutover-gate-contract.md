# Source-to-Campaign Cutover Gate Contract

The cutover gate is a deterministic readiness report. It is not active authority.

## Output Shape

```json
{
  "status": "ready|hold",
  "blocking_reasons": [],
  "checks": {},
  "no_execution": true,
  "no_wake_mutation": true,
  "no_delivery_mutation": true,
  "no_threshold_mutation": true
}
```

## Rules

- Missing required artifacts produce `hold`.
- `ready` does not alter wake, delivery, thresholds, or execution authority.
- Rollback is to ignore the gate output and keep current report path.
