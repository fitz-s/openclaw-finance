# Source-to-Campaign Phase 01 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/source-to-campaign-phase-01-source-office-scout-ralplan.md`
- `docs/openclaw-runtime/contracts/source-registry-v2-contract.md`
- `docs/openclaw-runtime/contracts/source-scout-contract.md`
- `scripts/source_scout.py`
- `tools/export_source_scout_snapshot.py`
- `docs/openclaw-runtime/source-scout-candidates.json`
- `tests/test_source_scout_phase01.py`

Checks:
- The source scout is deterministic and metadata-only; it does not fetch vendors, require credentials, or alter hot path behavior.
- Candidates cover all six review lanes: market_structure, corp_filing_ir, real_economy_alt, news_policy_narrative, human_field_private, and internal_private.
- Options/IV is represented as `market_structure/options_iv`, with explicit required metrics for IV rank, IV percentile, term structure, skew, OI change, volume/OI ratio, stale-chain detection, provider confidence, and point-in-time replay.
- Every candidate includes rights policy, cost class, latency class, historical depth, point-in-time support, expected value, risks, and promotion blockers.
- All candidates are `shadow_candidate`, `eligible_for_wake=false`, `eligible_for_judgment_support=false`, and `no_execution=true`.
- Reviewer-visible export includes metadata only and no raw vendor payloads.

Risks:
- Candidate lists are curated static evaluations, not live internet scouting. This is acceptable for Phase 01 because source activation requires later RALPLAN and rights review.
- Vendor names in candidates are not endorsements; they are backlog items for future evaluation.
- Parent-side source registry activation remains out of scope for this finance-only phase.

Required follow-up:
- Phase 02 must connect source candidates to EvidenceAtom/ClaimAtom requirements without activating sources.
- Phase 03 must use this options/IV contract to improve `options_flow_proxy_fetcher.py` or a new `options_iv_surface_compiler.py`.

Verification evidence:
- `python3 -m pytest -q tests/test_source_scout_phase01.py`
- `python3 -m compileall -q scripts/source_scout.py tools/export_source_scout_snapshot.py tests/test_source_scout_phase01.py`

Commit gate: pass.
