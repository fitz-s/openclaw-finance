# OpportunityQueue Contract

`OpportunityQueue` turns unknown discovery from a report section into a persistent promotion/suppression lane.

Candidates may originate from:

- scanner non-watchlist discovery
- SEC semantics
- options-flow proxy
- broad-market proxy
- bounded research sidecar

Core fields:

- `candidate_id`
- `status`
- `instrument`
- `theme`
- `source_refs`
- `promotion_reason`
- `suppression_reason`
- `linked_thesis_id`
- `first_seen_at`
- `last_seen_at`
- `score`

Allowed statuses:

- `candidate`
- `promoted`
- `suppressed`
- `retired`

## Runtime Boundary

`OpportunityQueue` exists to prevent unknown discovery from being a one-off report paragraph. It must separate true non-watchlist discovery from existing holdings and watchlist members.

Promotion creates a candidate thesis for review. It does not create execution authority or bypass product validation.
