# Finance Gate Taxonomy

Finance has three distinct gate layers. They must not be collapsed into one vague "gate" in code, prompts, or user-facing reports.

## 1. Market Candidate Gate

Artifact:

- `finance/state/report-gate-state.json`

Purpose:

- Decide whether accumulated scanner observations justify a report candidate.
- This is about market signal strength, novelty, urgency, cumulative value, and cooldowns.

Typical internal reasons:

- no candidate met threshold
- short/core/immediate candidate eligible
- cooldown active
- decay removed stale observations

User-facing rule:

- Never expose raw phrases such as `thresholds not met`.
- Translate to "没有新事件达到升级阈值" or an equivalent Chinese explanation.

## 2. Report Integrity Gate

Artifact:

- `finance/state/finance-report-validation.json`

Implementation:

- `finance/scripts/finance_report_validator.py`

Purpose:

- Validate ReportEnvelope structure, hashes, readability, provenance, unavailable-fact discipline, and banned internal text.

Typical failures:

- `input_packet_hash_mismatch`
- `envelope_hash_mismatch`
- missing required section
- raw/internal text leakage
- P&L claim without performance source

User-facing rule:

- If this gate fails, report a system/report integrity failure. Do not output a market report.

## 3. Delivery Freshness Gate

Artifact:

- `ops/state/finance-native-premarket-brief-live-report.json`

Implementation:

- `finance/scripts/native_premarket_brief_live.py` preflight

Purpose:

- Ensure the envelope is fresh, hash-linked to the latest packet, and validator-approved before delivery.

Typical failures:

- `envelope_stale`
- `validator_not_pass`
- `input_packet_hash_mismatch`
- `missing_markdown`

User-facing rule:

- Treat these as delivery-safety failures, not market judgments.

## Rule

Every finance report failure must name which gate failed:

- market_candidate_gate
- report_integrity_gate
- delivery_freshness_gate
