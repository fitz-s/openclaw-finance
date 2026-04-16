# Campaign Projection Contract

`CampaignProjection` is an operator-facing projection, not a new authority layer.
It derives from existing canonical finance objects:

`CapitalAgendaItem / ThesisCard / ScenarioCard / OpportunityQueue / InvalidatorLedger / CapitalGraph / DisplacementCase`

Canonical authority remains:

`ContextPacket -> WakeDecision -> JudgmentEnvelope -> deterministic renderer -> product validator -> decision log -> delivery safety`

## Purpose

A campaign is the durable object the operator can follow across days or weeks. It replaces raw `T1/O1/I1/S1` exposure on the Discord surface with a human-readable investment agenda object.

## Schema

```json
{
  "campaign_id": "campaign:<stable-hash>",
  "campaign_type": "live_opportunity|peacetime_scout|undercurrent_risk|hedge_gap|invalidator_cluster|existing_thesis_review",
  "board_class": "live|scout|risk",
  "stage": "scout|accumulating|candidate|review|escalation|cooling|retired",
  "human_title": "人话标题",
  "why_now_delta": "what changed since the last board update",
  "why_not_now": "why this is not an execution or stronger conclusion",
  "capital_relevance": "bucket, overlap, hedge, or displacement relevance",
  "confirmations_needed": ["..."],
  "kill_switches": ["..."],
  "linked_thesis": ["thesis:..."],
  "linked_scenarios": ["scenario:..."],
  "linked_opportunities": ["opportunity:..."],
  "linked_invalidators": ["invalidator:..."],
  "linked_displacement_cases": ["case:..."],
  "source_freshness": {
    "status": "fresh|mixed|stale|unknown",
    "source_refs": ["..."]
  },
  "thread_key": "campaign:<stable-thread-key>",
  "no_execution": true
}
```

## Board Classes

- `live`: deserves current operator attention because wake/escalation/material delta exists.
- `scout`: peacetime opportunity or theme accumulation; visible but non-urgent.
- `risk`: invalidator cluster, crowding, hedge gap, or scenario drift.

## Invariants

- Must not introduce new facts absent from canonical source artifacts.
- Must not set or imply live execution authority.
- Must preserve linked canonical refs for audit/replay.
- Human title is primary; machine handles are secondary.
- Discord boards may show campaigns; artifacts retain canonical source refs.
