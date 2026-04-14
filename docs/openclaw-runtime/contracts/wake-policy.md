# Wake Policy

Wake policy converts normalized evidence updates into bounded operational outcomes. It is deterministic and runs before model judgment.

## Allowed Outcomes

- `NO_WAKE`
- `PACKET_UPDATE_ONLY`
- `ISOLATED_JUDGMENT_WAKE`
- `OPS_ESCALATION`

## Inputs

Wake score considers:
- novelty
- source reliability
- position relevance
- contradiction impact
- freshness
- invalidator hit

## Rules

- Upstream single-source updates are wake candidates, not trade triggers.
- Duplicate events inside a cooldown window are suppressed but kept as packet updates.
- Collector stale/source outage events route to `OPS_ESCALATION`.
- Position invalidator hits are highest-priority judgment wakes.
- Agent sessions do not compute wake score; they consume the wake decision and packet.
