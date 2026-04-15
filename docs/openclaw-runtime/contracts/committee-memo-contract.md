# Committee Memo Contract

`CommitteeMemo` is a typed, role-decomposed review artifact produced by the investment committee sidecar.

It absorbs FinRobot-style role decomposition while remaining strictly outside the hot path and within the review-only boundary.

## Roles

- `thesis_analyst`: assess bull/bear case strength, evidence quality, maturity trajectory.
- `countercase`: stress-test the thesis from the opposing perspective.
- `portfolio_risk`: assess exposure overlap, factor concentration, correlation risk.
- `macro_scenario`: assess scenario sensitivity, macro regime dependency, tail risk.
- `options_structure`: assess options positioning, IV/OI signals, assignment/decay exposure.

## Core Fields

- `memo_id`
- `role`: one of the defined roles.
- `agenda_item_ref`: the `CapitalAgendaItem` being evaluated.
- `assessment`: structured typed assessment (not free prose).
- `risk_flags`: list of identified risk concerns.
- `confidence`: `high` | `medium` | `low` | `insufficient_data`.
- `required_questions`: questions this role cannot answer that another role or future evidence must resolve.

## Forbidden Actions

All committee memos must carry:

```json
{
  "forbidden_actions": [
    "no_user_delivery",
    "no_execution",
    "no_threshold_mutation",
    "no_live_authority_change"
  ]
}
```

## Assessment Structure

Each role's `assessment` field is a typed dict, not free text:

```json
{
  "summary": "one-line typed conclusion",
  "supporting_evidence_refs": [],
  "contradicting_evidence_refs": [],
  "key_risk": "primary risk identified by this role",
  "key_opportunity": "primary opportunity identified by this role",
  "recommendation": "review | watch | escalate | suppress"
}
```

## Merge Rule

`committee_memo_merge.py` cross-references memos per agenda item:

- Compute consensus score across roles.
- Flag role disagreements (analyst bullish but countercase sees fatal flaw).
- Annotate agenda items with merged committee assessment.
- Output: `state/capital-agenda-annotated.json`.

## Hot Path Exclusion

Committee memos are sidecar artifacts. They may enrich agenda items and report context but must not:

- Block the active report chain.
- Be required for product validation or delivery safety.
- Directly appear in user-visible markdown (only their conclusions may be referenced).

## Runtime Boundary

`CommitteeMemo` is bounded research output. It may inform agenda ranking and report context but must not place trades, mutate live authority, bypass product validation, bypass delivery safety, or send user messages directly.
