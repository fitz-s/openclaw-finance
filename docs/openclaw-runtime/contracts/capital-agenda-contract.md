# Capital Agenda Contract

`CapitalAgendaItem` is the ranked, review-only capital attention unit for OpenClaw Finance.

It replaces report-centric review with capital-centric review: each agenda item must justify why it deserves scarce attention relative to the existing book.

## Core Fields

- `agenda_id`
- `agenda_type`: `new_opportunity` | `existing_thesis_review` | `hedge_gap_alert` | `invalidator_escalation` | `exposure_crowding_warning`
- `priority_score`: comparative score across all agenda items.
- `linked_thesis_ids`
- `linked_positions`
- `linked_scenarios`
- `displacement_case_refs`
- `opportunity_cost_refs`
- `required_questions`: what must be answered before this item resolves.
- `attention_justification`: why this item deserves attention over other items.
- `no_execution`: must always be `true`.

## Agenda Types

- `new_opportunity`: opportunity candidate with displacement case. Requires explanation of what it replaces or improves.
- `existing_thesis_review`: active thesis with open invalidators or stale confirmations.
- `hedge_gap_alert`: bucket with weak or missing hedge coverage.
- `invalidator_escalation`: high-hit-count invalidator that may require thesis status change.
- `exposure_crowding_warning`: bucket utilization above threshold with multiple overlapping theses.

## Ranking Rule

Agenda items are ranked comparatively, not by novelty alone:

```text
priority_score = displacement_significance * invalidator_impact * hedge_gap_severity * scenario_sensitivity
```

Weights are deterministic and configurable. Same inputs must produce the same ranking.

## Delivery Cap

Maximum 5 agenda items per delivered report. Maximum 8 agenda items compiled (top 5 delivered, remainder available in state for audit).

## Binding Rule

Each delivered agenda item must bind:

- At least one `thesis_ref` or `position_ref`.
- `displacement_case_refs` if overlap exists.
- `opportunity_cost_refs` if the item competes for a saturated bucket.
- `attention_justification` explaining why this item matters now.

Unbounded agenda items (no refs, no justification) must be rejected by the compiler.

## Runtime Boundary

`CapitalAgendaItem` is a review-only artifact. It organizes attention priority but does not authorize execution, threshold mutation, or delivery bypass. `no_execution` must always be `true`.

## Fallback Rule

Missing or invalid `capital-agenda.json` must fall back to the current `thesis_delta` report path. The agenda must never block delivery.
