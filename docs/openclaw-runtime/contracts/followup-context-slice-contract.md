# Follow-up Context Slice Contract

`FollowupContextSlice` is the deterministic routing surface for Discord finance follow-up questions.

It is derived from reader bundle, campaign board, campaign cache, and context gaps. It is not a new judgment and cannot mutate thesis state, thresholds, wake policy, delivery, or execution authority.

## Required Inputs

- `verb`: why | challenge | compare | scenario | sources | trace | expand
- `primary_handle`
- `secondary_handle` for compare
- reader bundle
- campaign board
- campaign cache

## Required Output Fields

```json
{
  "evidence_slice_id": "slice:<hash>",
  "verb": "compare",
  "resolved_primary_handle": "campaign:...",
  "resolved_secondary_handle": "thesis:...",
  "required_evidence_groups": ["capital_graph_slice", "displacement_case", "bucket_competition"],
  "evidence_slice_coverage": {
    "required_keys": [],
    "present_keys": [],
    "missing_fields": [],
    "coverage_status": "complete|insufficient"
  },
  "context_gap_guidance": [],
  "insufficient_data": false,
  "no_execution": true
}
```

## Verb Groups

- `why`: campaign projection, recent claims, source health, promotion reason, event timeline
- `challenge`: countercase memo, invalidators, contradictions, denied hypotheses, freshness risks
- `compare`: capital graph slice, displacement case, bucket competition, portfolio attachment
- `scenario`: scenario exposure, hedge coverage, crowding risk, linked campaigns
- `sources`: source atoms, claim lineage, rights/redaction, freshness by lane
- `trace`: line/handle to claim to atom to source lineage
- `expand`: prepared campaign cache and report bundle summary

## Insufficient Data Rule

If a required group is missing, the response should be `insufficient_data` and must include context gap guidance. It must not infer or invent missing evidence.
