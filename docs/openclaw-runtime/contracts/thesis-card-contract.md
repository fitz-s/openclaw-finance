# ThesisCard Contract

`ThesisCard` is the smallest durable investment-memory unit in OpenClaw Finance.

Required intent:

- Track why an instrument/theme is being watched.
- Preserve bull case, bear case, invalidators, confirmations, linked scenarios, and evidence refs.
- Provide delta context to reports without becoming an execution command.

Core fields:

- `thesis_id`
- `instrument`
- `linked_position`
- `linked_watch_intent`
- `status`
- `maturity`
- `bull_case`
- `bear_case`
- `invalidators`
- `required_confirmations`
- `evidence_refs`
- `scenario_refs`
- `last_meaningful_change_at`
- `promotion_reason`
- `retirement_reason`

Allowed statuses:

- `candidate`
- `active`
- `watch`
- `suppressed`
- `retired`

## Runtime Boundary

`ThesisCard` may explain why an instrument/theme deserves attention and what would invalidate it. It must not encode trade instructions, target position sizes, or execution commands.

Initial generated cards are immature `watch` or `candidate` objects unless promoted by later validated evidence and review-only judgment history.
