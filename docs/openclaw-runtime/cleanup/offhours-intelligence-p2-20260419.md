# Offhours Intelligence P2 Closeout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Scope

P2 adds a budget-aware compression activation lane for Brave LLM Context and Brave Answers. It is sidecar-only and defaults to dry-run. It does not change cron cadence, Discord delivery, wake thresholds, judgment authority, or execution authority.

## Implemented

- Added `scripts/brave_compression_activation.py`.
- Compression activation reads planned QueryPacks plus seed URLs from Brave Web/News fetch records.
- LLM Context runs only from scoped seed URLs and uses `llm_context` budget.
- Brave Answers runs only as `authority_level=sidecar_only` and uses `answers` budget.
- Missing seed URLs produce explicit blocked results instead of generic synthesis.
- Budget-denied context/answer calls are blocked before network.
- Dry-run records do not consume `llm_context` or `answers` budget.
- Parent offhours dry-run path includes `brave_compression_activation`; market-hours path does not.
- Snapshot export includes sanitized `brave-compression-activation-report.json` and P2 scout/ralplan/critic/closeout entries.

## Explicitly Not Activated

- No live Answers default.
- No answer prose as canonical evidence.
- No wake/report/delivery/threshold mutation.
- No cron cadence mutation.
- No broker/execution authority.

## Smoke Evidence

```bash
python3 scripts/brave_compression_activation.py --max-packs 2
```

Observed result:

- `dry_run=true`
- `seed_url_count=0` in the current runtime because recent Brave Search/News records are rate-limited / lack usable seed URLs.
- Results are explicit `blocked` rows with `missing_seed_urls`.
- No budget was consumed.

Parent dry-run evidence:

```bash
python3 scripts/finance_parent_market_ingest_cutover.py --dry-run --scanner-mode offhours-scan
```

Observed steps include:

```text
offhours_source_router
finance_context_pack
query_pack_planner
brave_source_activation
brave_compression_activation
finance_source_health
```

## Verification

```bash
python3 -m pytest -q tests/test_brave_compression_activation_p2.py tests/test_parent_market_ingest_cutover_p1_offhours.py tests/test_offhours_snapshot_p2.py
# 7 passed

python3 -m pytest -q tests
# 321 passed

python3 -m compileall -q scripts tools tests
# pass

python3 tools/audit_operating_model.py
# pass, error_count=0

python3 tools/audit_benchmark_boundary.py
# pass, blocking_reasons=[]

python3 tools/export_openclaw_runtime_snapshot.py
# pass
```

## Residual Risks

- P2 proves the compression lane and guardrails, but current live Brave source records are rate-limited and do not provide seed URLs, so no useful compression output is expected yet.
- Future live activation should only happen after source yield improves and budget telemetry is stable.
- Answers citation candidates still require later fetch before promotion into EvidenceAtoms.

## Next Phase

P3 should have its own internal explorer, external scout, ralplan, implementation, critic, commit, and push. Recommended P3 target: all-days offhours cadence/governor design in shadow-first mode, using P1/P2 telemetry to avoid message storms and quota burn.
