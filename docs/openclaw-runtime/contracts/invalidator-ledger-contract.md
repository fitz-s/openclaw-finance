# InvalidatorLedger Contract

`InvalidatorLedger` records contradiction and invalidator history across time.

It is designed to prevent finance learning from only confirming existing theses.

Core fields:

- `invalidator_id`
- `target_type`
- `target_id`
- `status`
- `description`
- `evidence_refs`
- `first_seen_at`
- `last_seen_at`
- `hit_count`
- `resolution`

Allowed statuses:

- `open`
- `hit`
- `resolved`
- `retired`

## Runtime Boundary

`InvalidatorLedger` is a correction surface. It may increase wake priority, downgrade thesis confidence, or require confirmations, but it must not automatically mutate live thresholds or execute portfolio actions.

Resolved invalidators must keep enough refs to support replay and learning review.
