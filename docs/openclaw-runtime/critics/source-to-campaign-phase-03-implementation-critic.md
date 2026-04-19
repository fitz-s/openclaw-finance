# Source-to-Campaign Phase 03 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/source-to-campaign-phase-03-options-iv-sensitivity-ralplan.md`
- `docs/openclaw-runtime/contracts/options-iv-surface-contract.md`
- `scripts/options_iv_surface_compiler.py`
- `scripts/finance_discord_report_job.py`
- `tests/test_options_iv_surface_phase03.py`

Checks:
- Options/IV is now compiled into a dedicated review-only surface instead of remaining buried in generic options flow proxy rows.
- Missing IV data creates `missing_iv_surface` confidence penalties.
- Stale option chain snapshots create `stale_chain_snapshot` penalties.
- Proxy-only Nasdaq/yfinance-style chain data is explicitly disclosed and downweighted.
- The compiler computes average/max IV, call/put skew, max volume/OI ratio, unusual contract count, and top contract summaries when data exists.
- `finance_discord_report_job.py` refreshes the IV surface with `run_optional`, so report generation can keep the shadow artifact current without making it delivery-critical.
- No vendor integration, network fetch, threshold mutation, wake change, or execution authority was added.

Risks:
- Live surface quality is still limited by the existing `options-flow-proxy.json`; current real data can still show all rows as proxy-only and stale.
- This phase improves visibility and confidence penalties, not raw options data quality. Source Scout / future vendor activation remains necessary.

Required follow-up:
- Phase 04/05 should attach IV surface rows to ContextGaps and report-time archive.
- Future source activation should replace proxy-only rows with a true point-in-time IV source.

Verification evidence:
- `python3 -m pytest -q tests/test_options_iv_surface_phase03.py`
- Full tests and compileall before commit.

Commit gate: pass.
