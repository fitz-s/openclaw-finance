# Source Scout Contract

`SourceScoutCandidate` is a review-only evaluation record for possible future information sources.

A candidate is not an activated source. It cannot wake the user, support JudgmentEnvelope, mutate thresholds, change Discord delivery, or imply data rights.

## Candidate Shape

```json
{
  "source_candidate_id": "source-scout:options-iv:orats",
  "lane": "market_structure",
  "sublane": "options_iv",
  "provider": "ORATS",
  "coverage": ["US listed equity options", "IV surface", "skew", "term structure"],
  "latency_class": "intraday|daily|event_driven|unknown",
  "cost_class": "free|paid|premium|unknown",
  "rights_policy": "raw_ok|derived_only|none|unknown",
  "api_available": true,
  "historical_depth": "multi-year|limited|unknown",
  "point_in_time_support": true,
  "implementation_complexity": "low|medium|high",
  "expected_value": "why this source improves campaign intelligence",
  "required_metrics": [],
  "credential_ref": null,
  "activation_mode": "candidate_only|credential_gated|local_terminal|proxy_fallback",
  "source_health_id": "source:provider_lane",
  "primary_eligible": false,
  "risks": [],
  "promotion_blockers": [],
  "status": "shadow_candidate",
  "no_execution": true
}
```

## Required Lanes

A scout run must cover at least:
- `market_structure`
- `corp_filing_ir`
- `real_economy_alt`
- `news_policy_narrative`
- `human_field_private`
- `internal_private`

## Options / IV Requirements

Candidates in `market_structure/options_iv` must explicitly describe whether they can support:
- IV rank
- IV percentile
- IV term structure
- skew
- open-interest change
- volume/open-interest ratio
- unusual contract concentration
- stale-chain detection
- provider confidence
- point-in-time replay
- credential or local-terminal activation mode
- source-health row id and whether it is eligible to become primary options-IV context

## Promotion Rules

A source candidate may not be promoted unless:
- rights policy is not `unknown` or `none`
- point-in-time support is understood
- cost and redistribution policy are explicit
- implementation complexity and API limits are reviewed
- credentials/local terminal/subscription requirements are explicit
- primary eligibility is false until rights, metrics, and point-in-time replay are validated
- a later RALPLAN approves activation

## Export Rules

Reviewer exports may include candidate metadata and risk notes. They must not include credentials, raw vendor payloads, licensed snippets, private notes, or account identifiers.
