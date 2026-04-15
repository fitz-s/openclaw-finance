# Capital Graph Contract

`CapitalGraph` is the deterministic exposure graph for OpenClaw Finance.

It links positions, theses, scenarios, factors, and capital buckets into a queryable structure that enables comparative capital governance.

## Nodes

- `position`: stock or option held in portfolio.
- `thesis`: active or watch ThesisCard.
- `scenario`: active or candidate ScenarioCard.
- `factor`: shared exposure factor across multiple nodes (e.g., sector, rate sensitivity, commodity dependency).
- `bucket`: CapitalBucket assignment.

## Edges

- `overlap`: two thesis nodes share the same instrument or highly correlated instruments.
- `hedge`: a thesis/position node covers exposure in another node.
- `conflict`: a thesis invalidator contradicts another thesis's bull case.
- `dependency`: thesis nodes share a ScenarioCard via `scenario_refs`.
- `invalidation`: an open invalidator targets a thesis or position node.

## Generation Rule

`CapitalGraph` must be compiled by deterministic Python from typed state inputs. Same inputs must produce the same graph and the same `graph_hash`.

Required inputs:

- `watch-intent.json`
- `thesis-registry.json`
- `portfolio-resolved.json`
- `scenario-cards.json`
- `capital-bucket-config.json`
- `invalidator-ledger.json`

## Stability Rule

`graph_hash` is computed from the sorted, deterministic JSON of all nodes and edges. Identical input state must always produce the same hash.

## Fallback Rule

Missing or invalid `CapitalGraph` must never block delivery. The report chain must deterministic-fallback to the current `thesis_delta` path when:

- `capital-graph.json` is absent or empty.
- `graph_hash` fails validation.
- Any required input is missing or malformed.

## Runtime Boundary

`CapitalGraph` is a review-only analysis artifact. It may influence context ordering, report structure, agenda ranking, and audit. It must not place trades, mutate live authority, bypass product validation, or bypass delivery safety.

## Authority Boundary

`CapitalGraph` enriches the Thesis Spine persistent object layer. It does not replace the active hot path:

```text
ContextPacket -> WakeDecision -> JudgmentEnvelope -> product report -> decision log -> delivery safety
```
