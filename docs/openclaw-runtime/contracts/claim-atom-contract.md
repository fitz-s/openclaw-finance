# Claim Atom / ClaimGraph Contract

`ClaimAtom` is a deterministic derived statement from an `EvidenceAtom`. `ClaimGraph` stores claim rows and deterministic support/contradiction edges.

This is a shadow substrate in Phase 2.

## Claim Shape

```json
{
  "claim_id": "claim:<stable-hash>",
  "atom_id": "atom:<stable-hash>",
  "source_id": "source:sec_edgar",
  "source_lane": "corp_filing_ir",
  "source_sublane": "corp_filing_ir.sec_filings",
  "subject": "TSLA",
  "predicate": "mentions",
  "object": "bounded object text",
  "magnitude": null,
  "unit": null,
  "direction": "bullish|bearish|neutral|ambiguous|not_applicable",
  "horizon": "intraday|multi_day|quarterly|structural|unknown",
  "certainty": "confirmed|probable|weak|unknown",
  "supports": [],
  "contradicts": [],
  "event_class": "price|filing|flow|narrative|source_health|portfolio|unknown",
  "why_it_matters_tags": [],
  "capital_relevance_tags": [],
  "source_reliability_score": 0.9,
  "source_uniqueness_score": 0.5,
  "evidence_rights": {
    "compliance_class": "public",
    "redistribution_policy": "raw_ok",
    "export_policy": "raw_ok"
  },
  "lineage": {
    "atom_id": "atom:<stable-hash>",
    "point_in_time_hash": "sha256:..."
  },
  "no_execution": true
}
```

## Graph Invariants

- Claims are derived deterministically, not by LLM free prose.
- Claims preserve `atom_id` lineage.
- Claims preserve source lane, sublane, reliability, uniqueness, and evidence rights.
- Contradiction/support edges are deterministic and bounded.
- `graph_hash` is deterministic for the claims list.
- ClaimGraph remains outside wake/judgment/delivery authority in Phase 2.
