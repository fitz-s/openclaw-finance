# SEC Fallback Activation P9 Internal Explorer

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Internal findings:

- `sec_discovery_fetcher.py` already fetches SEC current Atom feeds for 8-K, Form 4, SC 13D, SC 13G and writes `state/sec-discovery.json`.
- `sec_filing_semantics.py` classifies discovery rows conservatively and writes `state/sec-filing-semantics.json`.
- `source_atom_compiler.py` can infer `source:sec_edgar` from SEC-like observations but SEC discovery is not actively wired into the Brave fallback path.
- `brave_source_recovery_policy.py` now exposes breaker state; P9 should run SEC fallback when Brave breaker is open or when explicitly requested.

P9 touchpoints:

- Add `scripts/sec_fallback_activation.py`.
- Optionally call it from `finance_parent_market_ingest_cutover.py` after Brave activation in offhours/market-hours source path, but keep it no-wake/no-delivery.
- Export `sec-fallback-activation-report.json`.
