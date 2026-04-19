# Source ROI Contract

`SourceROI` measures review-only source and campaign contribution. It does not mutate source registry, wake policy, thresholds, delivery, or execution authority.

## Source ROI Row

```json
{
  "source_id": "source:reuters",
  "source_lane_set": ["news_policy_narrative"],
  "atom_count": 1,
  "claim_count": 1,
  "campaign_contribution_count": 1,
  "campaign_value_score": 0.0,
  "false_positive_rate_proxy": null,
  "context_gap_closure_time_hours": null,
  "peacetime_to_live_conversion": false,
  "review_only": true,
  "no_threshold_mutation": true,
  "no_execution": true
}
```

## Rules

- ROI rows are advisory metrics only.
- Unknown false-positive and gap-closure values must be null or proxy-labelled, not fabricated.
- Low ROI must not suppress sources automatically.
- High ROI must not authorize trades or wake by itself.
