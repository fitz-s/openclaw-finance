# Thesis Spine Contract

Thesis Spine is the persistent object layer for OpenClaw Finance.

It does not replace the active hot path:

```text
ContextPacket -> WakeDecision -> JudgmentEnvelope -> product report -> decision log -> delivery safety
```

It adds durable object references so runs can accumulate into review-only investment memory.

## Objects

- `WatchIntent`: why a symbol is in the finance universe.
- `ThesisCard`: durable investment thesis memory for one instrument or theme.
- `ScenarioCard`: scenario object that can link many theses.
- `OpportunityQueue`: promoted/suppressed/retired unknown-discovery candidates.
- `InvalidatorLedger`: cross-time record of invalidators, contradictions, and confirmations.

## Required Runtime Rule

Packet, wake, judgment, and decision log artifacts may carry:

- `thesis_refs`
- `scenario_refs`
- `opportunity_candidate_refs`
- `invalidator_refs`

These IDs are review artifacts. They do not grant execution authority.

## Rollout Rule

Thesis Spine starts in shadow/reference mode.

- Existing packet, wake, judgment, product validation, decision log, and delivery safety gates stay authoritative.
- Missing Thesis Spine state must not block the active report chain.
- Thesis refs may enrich context ordering, report deltas, audit, and learning only after deterministic validation.
- Visible report cutover requires a separate product validator update and report-quality review.

## Safety Boundary

Thesis Spine may influence wake priority, context ordering, report deltas, and weekly learning. It must not place trades, mutate live authority, or bypass product validation and delivery safety.

## Authority Boundary

Persistent objects are machine state and audit context, not prompt memory. Raw feeds, raw news, one-off market notes, and latest packet snapshots must not be copied into standing OpenClaw prompt surfaces.
