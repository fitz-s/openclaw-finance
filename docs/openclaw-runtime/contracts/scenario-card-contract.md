# ScenarioCard Contract

`ScenarioCard` is a persistent scenario object that links evidence and theses.

Examples:

- rate-cut timing
- regulatory shock
- earnings revision
- options-flow dislocation
- supply-chain change
- style rotation
- geopolitical event

Scenario cards let wake policy and reports talk about which scenario changed, not just which ticker moved.

Core fields:

- `scenario_id`
- `title`
- `status`
- `scenario_type`
- `linked_thesis_ids`
- `evidence_refs`
- `activation_zone`
- `invalidators`
- `last_meaningful_change_at`

## Runtime Boundary

`ScenarioCard` may activate or suppress context priority across linked theses. It must not directly trigger delivery, execution, or threshold mutation.

Scenario activation must remain explainable through evidence refs, linked thesis IDs, and invalidators.
