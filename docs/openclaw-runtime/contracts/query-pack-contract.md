# QueryPack Contract

`QueryPack` is the deterministic request plan for source acquisition. It may be produced by an LLM planner, but it is not evidence and is not a judgment.

## Shape

```json
{
  "pack_id": "query-pack:<hash>",
  "campaign_id": null,
  "lane": "market_structure|corp_filing_ir|news_policy_narrative|real_economy_alt|human_field_private|internal_private",
  "purpose": "source_discovery|source_reading|claim_closure|followup_slice",
  "query": "site:reuters.com oil prices Hormuz",
  "freshness": "day|week|month|year|null",
  "date_after": "YYYY-MM-DD|null",
  "date_before": "YYYY-MM-DD|null",
  "allowed_domains": [],
  "required_entities": [],
  "max_results": 10,
  "authority_level": "canonical_candidate|sidecar_only",
  "forbidden": ["trade_recommendation", "threshold_mutation", "execution"],
  "no_execution": true
}
```

## Rules

- QueryPack is not evidence.
- QueryPack does not authorize wake, judgment, delivery, or execution.
- `sidecar_only` packs cannot directly produce canonical claims.
- Brave Answers packs must use `authority_level=sidecar_only`.
- Freshness/date filters must be explicit when a lane is time-sensitive.
