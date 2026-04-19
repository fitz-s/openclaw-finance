# QueryPack Contract

Related review for offhours expansion: `/Users/leofitz/Downloads/review 2026-04-18.md`.

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
  "session_aperture": {
    "aperture_id": "aperture:XNYS:2026-04-18:weekend_aperture",
    "session_class": "weekend_aperture",
    "is_offhours": true,
    "is_long_gap": true,
    "answers_budget_class": "high"
  },
  "budget_request": {
    "search_units": 1,
    "answers_units": 0,
    "llm_context_units": 0,
    "requires_budget_guard": true
  },
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
- `session_aperture` is routing metadata only. It does not authorize wake, judgment, or delivery.
- `budget_request.requires_budget_guard=true` means the pack must pass `BraveBudgetGuard` before any Brave Search or Answers call.
- Answers budget is separate from Search budget and remains a compression sidecar, never evidence authority.
