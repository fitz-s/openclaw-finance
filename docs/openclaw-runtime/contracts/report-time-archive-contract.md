# Report-Time Archive Contract

`ReportTimeArchive` stores local runtime artifacts needed for exact replay of a generated finance report.

It is not committed to git. Sanitized reviewer packets may later derive from it.

## Directory

`state/report-archive/{report_id}/`

## Required Manifest Fields

```json
{
  "generated_at": "...",
  "contract": "report-time-archive-v1",
  "report_id": "RF63A",
  "exact_replay_available": true,
  "artifacts": {},
  "line_to_claim_refs": "line-to-claim-refs.json",
  "no_execution": true
}
```

## Artifact Classes

- envelope
- reader_bundle
- source_atoms
- claim_graph
- context_gaps
- source_health
- campaign_board
- options_iv_surface
- line_to_claim_refs

## Rules

- Archive remains local runtime state under `state/`.
- Raw snippets may exist internally but must not be exported to reviewer packets unless rights allow.
- Missing optional artifacts must be declared rather than silently ignored.
- Archive creation must not block Discord delivery.
- Archive cannot mutate wake, judgment, thresholds, or execution authority.
