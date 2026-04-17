# Followup Answer Contract

Defines the rules for follow-up analysis answers produced in the review room. Follow-up answers are **explain-only** — they interpret existing state, they do not create new judgments.

## Interrogation Verbs

| Verb | Semantics | Required Output Shape |
|------|-----------|-----------------------|
| `why` | Why this handle matters now | Current evidence chain → why now → constraint |
| `challenge` | Countercase analysis | Invalidators + required confirmations + missing evidence |
| `compare` | Overlap/opportunity cost | Instrument overlap + bucket competition + portfolio relevance |
| `scenario` | Scenario impact analysis | Trigger → transmission path → impacted objects → what changes |
| `sources` | Source trace | Source list → freshness → caveats |
| `expand` | Expand the current report lens | Report summary → dominant objects → follow-up paths |

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
3. Answer must bind to an `evidence_slice_id` emitted by the follow-up context router
4. Answer must use only evidence available in the bundle, campaign board, or selected evidence slice, not external/new facts

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

## Phase 6 Evidence Slice Discipline

The follow-up router must emit:

- `verb`
- `primary_handle`
- `resolved_primary_handle`
- optional `secondary_handle` / `resolved_secondary_handle`
- `evidence_slice_keys`
- `evidence_slice_id`
- `missing_fields`
- `insufficient_data`

If required slice fields are absent, the answer should return `insufficient_data` with the missing fields instead of generic inference. `insufficient_data` is still review-only and still requires `evidence_slice_id`.

If a route supplies `evidence_slice_coverage.coverage_status=insufficient`, an answer may only pass as `answer_status=insufficient_data`. It must not present itself as fully answered.

Parent Discord thread routing is out of scope for Phase 6; thread history remains UI only.
