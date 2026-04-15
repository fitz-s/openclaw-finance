# Followup Answer Contract

Defines the rules for follow-up analysis answers produced in the review room. Follow-up answers are **explain-only** — they interpret existing state, they do not create new judgments.

## Interrogation Verbs

| Verb | Semantics | Required Output Shape |
|------|-----------|-----------------------|
| `trace` | Evidence chain for a handle | Evidence refs → direction → confidence → source |
| `challenge` | Countercase analysis | Invalidators + required confirmations + missing evidence |
| `compare` | Overlap/opportunity cost | Instrument overlap + bucket competition + portfolio relevance |
| `scenario` | Scenario impact analysis | Trigger → transmission path → impacted objects → what changes |

## Answer Format (mandatory)

Every follow-up answer must follow this structure:

```
Fact
  - verifiable observations from bundle/state

Interpretation
  - what the facts mean for the selected handle

Unknown / To Verify
  - gaps in evidence, missing confirmations

What Would Change My Mind
  - specific conditions that would alter the interpretation
```

This structure is inherited from `STYLE_GUIDE.md` `Fact / Interpretation / To Verify` discipline.

## Binding Rules

1. Answer must bind to a valid `report_id` + `bundle_id`
2. Answer must bind to a selected handle from the bundle
3. Answer must use only evidence available in the bundle, not external/new facts

## Forbidden Actions

- `execution`: no trade language, no position recommendations
- `threshold_mutation`: no threshold changes from follow-up reasoning
- `new_unsourced_market_call`: no new market conclusions not in the bundle
- `raw_state_dump`: no raw JSON state in answers
- `thread_history_as_context`: rehydrate from bundle, not from conversation history
- `autonomous_judgment`: no thesis_state mutation, no actionability change

## Rehydration Guarantee

The followup context pack always reconstructs from:
1. The immutable reader bundle (primary context)
2. The selected handle's object card (focus)
3. A compact question ledger (max 5 prior questions, not raw thread)

Thread history is UI only; the bundle is memory.

## Authority

Follow-up answers are **derived commentary**, not canonical state. They do not feed back into the thesis spine, capital competition engine, or judgment envelope chain. They are strictly explain-only within the existing review-only boundary.
