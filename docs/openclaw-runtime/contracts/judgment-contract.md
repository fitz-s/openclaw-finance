# Judgment Contract

The agent is an adjudicator, explainer, and escalator. It is not a collector, normalizer, scheduler, parser, risk engine, or execution adapter.

## JudgmentEnvelope

Every model-mediated judgment must output a `JudgmentEnvelope` with:
- `judgment_id`
- `packet_id`
- `packet_hash`
- `instrument`
- `thesis_state`
- `actionability`
- `confidence`
- `why_now`
- `why_not`
- `invalidators`
- `required_confirmations`
- `evidence_refs`
- `policy_version`
- `model_id`

## Rules

- No evidence ref means no production judgment.
- No packet hash means no production judgment.
- Judgment may recommend `review`, `watch`, `reduce`, or `exit`, but validator/risk gate decides whether the output can affect any downstream action.
- Agent output cannot mutate execution state directly.
