# Finance Report Contract

Finance reports must be rendered from `finance/state/report-input-packet.json`, not by rereading raw runtime files ad hoc.

The input packet is the only report cognition substrate for renderer or optional LLM rewrite. It contains compact facts, source refs, hashes, data quality flags, and required omissions. It must not contain raw Flex XML, account identifiers, raw source attribute values, raw news text, or internal threshold phrases such as `thresholds not met`.

Renderer obligations:

- Use `report_policy_version` and `packet_hash` in every report envelope.
- Treat `unavailable_facts` as explicit non-claims; do not narrate unavailable data as fresh.
- Cite packet `source_refs` for numeric claims.
- Prefer `scanner_observations` as context/wake evidence, not as execution instructions.
- Keep portfolio sections bounded to `portfolio_snapshot`, `performance_snapshot`, `cash_nav_snapshot`, and `option_risk_snapshot`.
- If an LLM is used, pass the packet plus a fixed prompt contract and validate the resulting envelope before delivery.

The packet compiler owns data selection. The renderer owns wording. The validator owns delivery eligibility.
