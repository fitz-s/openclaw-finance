# RALPLAN P2: Options IV / Volatility Surface Repair

Status: planner_revision_after_architect_iterate
Mode: consensus_planning
Scope: planning-only; no implementation edits in this pass

## Task Statement

Repair the options IV / volatility surface lane so OpenClaw Finance no longer relies on stale Nasdaq/yfinance proxy data as if it were options truth. The system should gain a point-in-time, market-structure `options_iv` lane that can ingest licensed/provider data when credentials exist, disclose source health and rights when they do not, and keep all downstream use review-only and derived-only.

## Current Evidence

- `state/options-flow-proxy.json` is degraded at `2026-04-18T10:30:43Z`: `event_count=0`, with yfinance DNS failures for watchlist symbols.
- `state/options-iv-surface.json` is an old compiled snapshot: `symbol_count=6`, `missing_iv_count=6`, `stale_or_unknown_chain_count=6`, `proxy_only_count=6`, `provider_confidence=0.05`.
- `scripts/options_flow_proxy_fetcher.py` uses Nasdaq option-chain first and yfinance fallback. Nasdaq rows do not provide IV; yfinance may provide `impliedVolatility` but is fragile.
- `scripts/options_iv_surface_compiler.py` only compiles from `state/options-flow-proxy.json`. It does not fetch provider data and remains `options-iv-surface-v1-shadow`.
- `docs/openclaw-runtime/contracts/options-iv-surface-contract.md` requires explicit missing IV, staleness penalties, proxy-only disclosure, and `no_execution`.
- `docs/openclaw-runtime/contracts/source-registry-v2-contract.md` says `market_structure.options_iv` is first-class and must include provider confidence, staleness, point-in-time replay support, and confidence penalties for stale/proxy-only chains.
- `docs/openclaw-runtime/contracts/source-scout-contract.md` requires rights, cost, replay, and options-specific metric disclosure before source promotion.
- `scripts/source_scout.py` currently lists ORATS, ThetaData, and Polygon Options as options-IV candidates. User-supplied official-doc findings add Tradier as a viable courtesy-Greeks/IV fallback, with hourly Greeks and brokerage-account constraints.

## RALPLAN-DR

### Principles

1. Nasdaq/yfinance remains a degraded proxy lane, never primary options-IV truth.
2. Any provider activation must be credential-gated, rights-explicit, point-in-time aware, and review-only.
3. Missing credentials, DNS failures, empty chains, and license restrictions are observable source-health states, not silent empty results.
4. The compiler should consume normalized provider observations and degrade cleanly to proxy-only output without blocking reports.
5. Downstream artifacts may receive derived IV metrics and confidence scores, but not raw licensed payloads, account identifiers, credentials, or execution authority.
6. `options_iv_surface` remains report/context source context only in this P2 plan; it is not JudgmentEnvelope primary authority, wake authority, threshold authority, or execution authority until a separate cutover is planned and approved.

### Top Decision Drivers

1. The current surface is stale and has no IV observations; fixing confidence disclosure alone is insufficient for P2.
2. Candidate providers differ sharply in access model: ThetaData requires a local terminal, Polygon/Massive and Tradier require API credentials/subscription, and ORATS live data requires agreements/subscription.
3. OpenClaw needs deterministic replay and provider health before any campaign or judgment lane can treat IV as load-bearing evidence.

### Viable Options

#### Option A: Promote one paid provider directly into `options_iv`

Implement a single provider adapter first, likely ThetaData or Polygon, and make the IV compiler depend on that provider when credentials exist.

Pros:
- Fastest path to real IV values if the selected provider is available.
- Narrower implementation surface and fewer normalization branches.
- Easier provider-specific tests.

Cons:
- Brittle when credentials/subscription/local terminal are absent.
- Creates premature provider lock-in before rights and replay behavior are proven in this workspace.
- Leaves source-health and fallback semantics underdeveloped.

#### Option B: Provider-neutral normalized options-IV observation lane

Add a credential-gated fetcher with provider adapters that write normalized, derived-only observations plus fetch records. Compile the public surface from normalized observations first, then degraded proxy data second.

Pros:
- Does not assume credentials exist.
- Supports ThetaData, Polygon/Massive, Tradier, and later ORATS without changing compiler semantics.
- Makes source health, rights, replay support, and provider confidence first-class.
- Keeps Nasdaq/yfinance explicitly degraded while allowing real provider data to improve confidence.

Cons:
- More upfront design than a one-provider hotfix.
- Requires careful tests for partial provider success, missing credentials, and mixed provider/proxy rows.
- May produce a healthy substrate before any live provider succeeds.

#### Option C: Keep current compiler and only improve proxy scoring

Leave fetching unchanged, add more warnings and source-health rows around yfinance/Nasdaq failures, and keep `options-iv-surface.json` proxy-only.

Pros:
- Smallest diff.
- Avoids provider licensing complexity.
- Provides immediate diagnostic clarity.

Cons:
- Does not repair missing IV or point-in-time market-structure needs.
- Fails the P2 goal of primary options-IV source readiness.
- Continues relying on yfinance/Nasdaq as the only practical substrate.

### Recommendation

Choose Option B: build a provider-neutral, normalized options-IV observation lane, with ThetaData and Polygon/Massive as the first documented adapter targets, Tradier as a constrained fallback adapter/candidate, and ORATS kept as a high-value candidate unless live API agreements are explicitly available.

The implementation should not fail when no credentials exist. In that case it should write a degraded, review-only health/fetch record and let `options_iv_surface_compiler.py` produce an explicit `proxy_only`/`missing_primary_options_iv_source` surface.

## Architect ITERATE Resolution Notes

- Fetch-record status vocabulary must stay aligned to `docs/openclaw-runtime/contracts/source-fetch-record-contract.md`: `status` is only `ok|partial|rate_limited|failed`. Provider-specific failures such as missing credentials, schema drift, subscription denial, and network errors are represented through `error_class`, `application_error_code`, `quota_state`, `problem_details`, and mapped `source_health.degraded_state`/status fields, not new top-level `SourceFetchRecord.status` values.
- Source-health rows may expose explicit diagnostics such as `degraded_state=missing_credentials`, `degraded_state=network_error`, `degraded_state=fetch_failed`, `schema_status=drift|breaking_drift`, `coverage_status=unavailable|partial`, and `quota_status=degraded`, subject to updating the source-health contract where those values become contract-visible.
- Finance report/context authority must be updated before downstream options-IV job wiring: `options_iv_surface` enters `finance_llm_context_pack.py`, `finance_decision_report_render.py`, `finance_report_reader_bundle.py`, `finance_decision_log_compiler.py`, and `finance_report_product_validator.py` only as derived source context and audit/report material. It does not alter JudgmentEnvelope candidate requirements, allowed evidence authority, wake policy, or report delivery authority in this pass.

## ADR

### Decision

Implement P2 as a credential-gated, provider-neutral market-structure lane rather than making Nasdaq/yfinance or any single paid vendor the primary truth by default.

### Drivers

- Current yfinance/Nasdaq output is degraded, stale, and missing IV.
- Contracts require first-class `market_structure.options_iv` semantics with confidence, staleness, rights, and point-in-time replay.
- Provider availability is subscription- and environment-dependent; credentials cannot be assumed.

### Alternatives Considered

- Single-provider direct integration: rejected for lock-in and missing-credential fragility.
- Proxy-only scoring repair: rejected because it cannot produce primary IV/term/skew evidence.
- ORATS-first implementation: deferred because live/delayed/EOD access and agreements must be explicit before activation.

### Why Chosen

Provider-neutral normalization gives OpenClaw a stable internal contract independent of provider access, while still allowing a real provider to improve IV confidence immediately when configured. It also makes degraded source access visible instead of letting reports recycle stale proxy narratives.

### Consequences

- P2 adds at least one new state artifact and expands `options-iv-surface` semantics.
- Tests must cover missing credentials as a normal degraded path.
- Downstream consumers should only read derived metrics and source-health summaries, not raw vendor payloads.

### Follow-ups

- After credentials/subscription are confirmed, run a separate activation check to mark one provider as primary for `market_structure.options_iv`.
- Consider ORATS live/EOD adapter only after rights and agreements are documented.
- Add provider ROI scoring after several successful market sessions.

## Phased Implementation Plan

### Phase 1: Contract and Artifact Design

Touchpoints:
- `docs/openclaw-runtime/contracts/options-iv-surface-contract.md`
- `docs/openclaw-runtime/contracts/source-scout-contract.md`
- `docs/openclaw-runtime/contracts/source-health-contract.md`
- optional schema snapshot under `docs/openclaw-runtime/schemas/` if this repo treats the surface as schema-governed

Actions:
- Define `options-iv-surface-v2-shadow` or an additive v1-compatible extension with:
  - `primary_source_status`
  - `primary_provider_set`
  - `source_health_refs`
  - `rights_policy`
  - `point_in_time_replay_supported`
  - `derived_only`
  - `raw_payload_retained=false`
  - `missing_primary_options_iv_source` confidence penalty
- Define normalized observation rows for derived metrics only:
  - symbol, expiration, strike, call/put, observed_at, quote/asof timestamp
  - implied volatility, delta/gamma/theta/vega when licensed and available
  - open interest, volume, volume/OI, OI change when available
  - IV rank/percentile/term/skew if provider supports it or compiler can derive it from retained derived observations
  - provider, provider_confidence, rights_policy, latency_class, point-in-time support
- Preserve `shadow_only=true`, `no_execution=true`, and no wake/judgment primary authority.

Acceptance criteria:
- Contract states Nasdaq/yfinance cannot satisfy primary `options_iv`.
- Contract states missing credentials and missing provider data produce degraded health, not empty success.
- Contract names derived-only and raw-payload retention limits.

### Phase 2: Provider Scout and Configuration Update

Touchpoints:
- `scripts/source_scout.py`
- `tests/test_source_scout_phase01.py`
- likely `state/source-scout-candidates.json` generated by script, not hand-edited

Actions:
- Update options-IV candidate metadata from the official-doc findings:
  - ThetaData: local Theta Terminal, `option/snapshot/greeks/implied_volatility`, `expiration=*`, subscription tier for realtime/bulk Greeks.
  - Polygon/Massive Options: OPRA-based US options data, plan-dependent realtime/historical Greeks/IV/OI.
  - ORATS: live/delayed/EOD options, IV rank/percentiles, skewness/kurtosis, 500+ indicators, live agreements/subscription.
  - Tradier: option chain with `greeks=true`, courtesy ORATS Greeks/IV, realtime brokerage-account access, Greeks hourly per market-data page.
- Add explicit promotion blockers for unknown credentials, subscription tier, redistribution, and point-in-time replay if not proven.

Acceptance criteria:
- All options-IV candidates expose the required `OPTIONS_IV_METRICS`.
- Tradier is represented as a constrained fallback/candidate, not as primary truth.
- Tests assert rights/cost/replay blockers for providers whose capabilities are plan-dependent.

### Phase 3: Normalized Provider Fetch Records

Touchpoints:
- new `scripts/options_iv_provider_fetcher.py` or similarly named market-structure fetcher
- `scripts/atomic_io.py` only if existing helpers are insufficient
- new tests, for example `tests/test_options_iv_provider_fetcher_p2.py`
- generated state:
  - `state/options-iv-provider-snapshot.json`
  - `state/options-iv-fetch-records.jsonl` or equivalent fetch-record path

Actions:
- Implement provider adapters behind explicit env/config gates:
  - `THETADATA_BASE_URL` or default local terminal URL, only if terminal is reachable.
  - `POLYGON_API_KEY` or current Massive-compatible key naming, only if present.
  - `TRADIER_ACCESS_TOKEN` and endpoint config, only if present.
  - ORATS remains candidate-only unless an explicit key/agreement config exists.
- Each adapter should return normalized derived observations, not raw vendor payloads.
- On missing credentials, DNS/network failure, non-200, empty symbols, schema drift, or subscription denial, write a `source-fetch-record-v1`-compatible record with:
  - top-level `status` restricted to `ok|partial|rate_limited|failed`
  - `status=failed` for missing credentials, schema drift, subscription denial, network errors, and non-rate-limit application errors
  - `status=rate_limited` only for quota/throttle conditions such as 402/429 or provider-equivalent rate/quota errors
  - `status=partial` only when a provider fetch succeeds for some requested symbols/contracts but not all
  - `error_class` values such as `missing_credentials`, `network_error`, `schema_drift`, `subscription_denied`, `application_error`, or `server_error`
  - `application_error_code` values such as `missing_api_key`, `network_fetch_failed`, `schema_drift`, `subscription_denied`, or provider-safe codes when available
  - `source_id`, `lane=market_structure.options_iv`, `fetched_at`, `quota_state`, `result_count`, and no secrets
- Do not add new dependencies; use existing `requests` and stdlib patterns.
- Keep output path restricted under `state/`.

Acceptance criteria:
- Running fetcher without credentials exits successfully or with documented optional-runtime failure semantics, writes `status=failed`, `error_class=missing_credentials`, `application_error_code=missing_api_key`, and produces source-health-consumable records.
- Tests use mocked HTTP responses and never hit real vendors.
- Raw payloads are not written to state.
- Provider rows carry `no_execution=true`, `derived_only=true`, and provider/source identifiers.

### Phase 4: Surface Compiler Repair

Touchpoints:
- `scripts/options_iv_surface_compiler.py`
- `tests/test_options_iv_surface_phase03.py`
- new P2 tests in `tests/test_options_iv_surface_p2.py`

Actions:
- Extend compiler inputs:
  - primary: `state/options-iv-provider-snapshot.json`
  - fallback: `state/options-flow-proxy.json`
- Compile provider observations into symbol-level IV surface metrics:
  - IV observation count, avg/max IV
  - call/put skew
  - term-structure summary across expirations
  - IV rank/percentile when provider supplies it
  - volume/OI and unusual concentration
  - chain age/staleness and source as-of age
  - provider confidence based on provider tier, freshness, rights, replay, and metric completeness
- Preserve proxy-only rows for symbols with no provider observations, but add `missing_primary_options_iv_source`.
- Ensure old `options-flow-proxy` degradation no longer makes stale old rows look fresh.

Acceptance criteria:
- If provider snapshot has valid IV, output `proxy_only=false` for those symbols and confidence rises only when rights/freshness/replay are acceptable.
- If provider snapshot is absent and proxy is degraded, output status is `degraded` or `empty` with explicit missing-primary penalties.
- Mixed provider/proxy symbols remain separated by provider set and confidence penalties.
- Existing P1 tests still pass or are intentionally updated for additive v2 semantics.

### Phase 5: Source Health Integration

Touchpoints:
- `scripts/source_health_monitor.py`
- `tests/test_source_health_monitor_phase09.py`
- `docs/openclaw-runtime/contracts/source-health-contract.md` if new row fields are contract-visible

Actions:
- Teach source health to ingest options-IV fetch records.
- Add source rows such as:
  - `source:thetadata_options_iv`
  - `source:polygon_options_iv`
  - `source:tradier_options_iv`
  - `source:nasdaq_options_flow_proxy`
  - `source:yfinance_options_proxy`
- Classify missing credentials distinctly from network errors, subscription denial, stale data, and schema drift.
- Map `SourceFetchRecord.status` into source-health without expanding fetch-record vocabulary:
  - `failed` + `error_class=missing_credentials` -> `coverage_status=unavailable`, `degraded_state=missing_credentials`, `problem_details.application_error_code=missing_api_key`
  - `failed` + `error_class=network_error` -> `latency_status=breached` or `unknown`, `coverage_status=unavailable`, `degraded_state=network_error` or `fetch_failed`
  - `failed` + `error_class=schema_drift` -> `schema_status=drift|breaking_drift`, `validation_status=fail`, `degraded_state=fetch_failed`
  - `failed` + `error_class=subscription_denied` -> `rights_status=restricted` or `unknown`, `coverage_status=unavailable`, `degraded_state=fetch_failed`
  - `rate_limited` -> `quota_status=degraded`, `rate_limit_status=limited`, `degraded_state=quota_limited`
  - `partial` -> `coverage_status=partial`, `degraded_state=partial_data`
- Keep stale-reuse guard active when primary options-IV source is absent or stale.

Acceptance criteria:
- Tests assert missing credentials are `coverage_status=unavailable` or `unknown` with `degraded_state=missing_credentials`.
- Tests assert DNS failures like current yfinance error become `network_error`/`network_fetch_failed`.
- Tests assert no source-health test expects `missing_credentials`, `schema_drift`, or `network_error` as top-level `SourceFetchRecord.status`.
- Source health remains advisory/shadow and does not block report delivery by itself.

### Phase 6: Finance Report and Context Authority Wiring

Touchpoints:
- `scripts/finance_llm_context_pack.py`
- `scripts/finance_decision_report_render.py`
- `scripts/finance_report_reader_bundle.py`
- `scripts/finance_decision_log_compiler.py`
- `scripts/finance_report_product_validator.py`
- report/archive/reader contracts if they need additive source-context fields

Actions:
- In `finance_llm_context_pack.py`:
  - add `OPTIONS_IV_SURFACE = STATE / 'options-iv-surface.json'`
  - load it in the report-orchestrator context alongside `CAPITAL_GRAPH`, `CAPITAL_AGENDA`, `DISPLACEMENT_CASES`, and `SCENARIO_EXPOSURE`
  - include an `artifact(OPTIONS_IV_SURFACE)` entry in `report_sources` so pack hashes disclose the source-context dependency
  - add a compact `options_iv_surface_summary` to the report pack containing only derived/audit fields such as `status`, `surface_policy_version`, `generated_at`, `symbol_count`, `provider_set`, `proxy_only_count`, `missing_iv_count`, `stale_or_unknown_chain_count`, `provider_confidence` range/summary, `source_health_refs`, `rights_policy`, `derived_only`, `raw_payload_retained=false`, and `no_execution`
  - add the same compact source-context summary to `report_followup` context where follow-up rehydration needs IV surface context
  - do not add `options_iv_surface` fields to `candidate_contract.required_fields`
  - do not add options-IV rows to `allowed_evidence_refs` unless a separate source-to-evidence cutover explicitly creates allowed EvidenceAtoms
- In `finance_decision_report_render.py`:
  - add an optional `OPTIONS_IV_SURFACE` constant and CLI argument such as `--options-iv-surface`
  - load and pass the surface into `build_report` as source context next to `options_flow`
  - render a bounded derived IV/source-health sentence in the existing options/risk or data-quality sections, with explicit proxy/stale/missing-primary disclosure
  - add only compact fields to the report envelope, for example `options_iv_surface_ref`, `options_iv_surface_hash`, and `options_iv_surface_summary`
  - preserve JudgmentEnvelope authority: `judgment.evidence_refs`, `packet_hash`, `thesis_state`, and `actionability` remain unchanged by options-IV surface context
- In `finance_report_reader_bundle.py`:
  - add `OPTIONS_IV_SURFACE = STATE / 'options-iv-surface.json'`
  - load it in `main()` and pass it to `compile_bundle`
  - add a source-context card or evidence-index attachment with a stable handle such as `SIV1` or an `options_iv_surface` card, containing only derived summaries, source-health refs, rights policy, and no-execution flags
  - do not expose raw vendor payloads, request params containing secrets, or account identifiers in reader-bundle cards
- In `finance_decision_log_compiler.py` / archive path:
  - archive only the report envelope's compact `options_iv_surface_summary`, hash/ref, and validator outcome
  - do not archive provider raw payloads or credentials
  - keep archive records as source-context/audit evidence, not a new decision authority field
- In `finance_report_product_validator.py`:
  - add validation that any report-visible options-IV content is derived-only, bounded, and explicitly review-only when degraded
  - reject raw vendor payload keys, account identifiers, credentials, unbounded chain dumps, or language implying trade execution/wake/threshold authority
  - allow degraded/no-credential options-IV health disclosure without failing product validation when the report remains clear and review-only

Acceptance criteria:
- `finance_llm_context_pack.py` includes `options_iv_surface_summary` as source context and artifact lineage, but JudgmentEnvelope candidate requirements and allowed evidence authority are unchanged.
- The renderer can include compact options-IV context in markdown/envelope without changing packet/JudgmentEnvelope binding or wake authority.
- Reader bundle and decision archive retain only derived summaries, hashes, paths, source-health refs, rights policy, and no-execution metadata.
- Product validator enforces no raw vendor payloads, no credentials/account IDs, no threshold/wake/execution claims, and accepts explicit degraded source-health disclosure.

### Phase 7: Runtime Chain Wiring

Touchpoints:
- `scripts/finance_discord_report_job.py`
- possibly cron/job docs under `docs/openclaw-runtime/finance-crontab.txt` or job contract docs if runtime ordering is documented

Actions:
- Run the provider fetcher as optional before `options_iv_surface_compiler.py`.
- Keep the compiler optional in the report job as today, but make compiler output deterministic even when provider fetch fails.
- Wire runtime only after Phase 6 source-context authority is explicit and validators know how to accept/reject the new derived summary.
- Avoid any Discord delivery expansion: only derived metrics/health summaries may flow into existing report/archive/reader-bundle paths after validators accept them.

Acceptance criteria:
- A no-credential run does not break the premarket report chain.
- Successful provider mock data appears in the surface before report context pack/rendering.
- No job step uses provider data to mutate thresholds, wake policy, or execution authority.

### Phase 8: Verification, Snapshots, and Audits

Touchpoints:
- `tests/`
- `docs/verification.md`
- runtime snapshot exports if contracts change

Actions:
- Add focused unit tests for normalization and compiler scoring.
- Add integration tests for no credentials, mocked provider success, mixed provider/proxy, stale provider, and source-health rows.
- Run the repo baseline:
  - `python3 -m pytest -q tests`
  - `python3 -m compileall -q scripts tools tests`
  - `python3 tools/audit_operating_model.py`
  - `python3 tools/audit_benchmark_boundary.py`
- Run report-path smoke with no credentials:
  - `python3 scripts/options_iv_provider_fetcher.py`
  - `python3 scripts/options_iv_surface_compiler.py`
  - `python3 scripts/source_health_monitor.py`
  - `python3 scripts/finance_llm_context_pack.py`
  - `python3 scripts/judgment_envelope_gate.py --allow-fallback --adjudication-mode scheduled_context --context-pack state/llm-job-context/report-orchestrator.json`
  - `python3 scripts/finance_decision_report_render.py`
  - `python3 scripts/finance_report_product_validator.py`
  - `python3 scripts/finance_report_delivery_safety.py`
- Refresh snapshots only after runtime/contract changes are stable:
  - `python3 tools/export_openclaw_runtime_snapshot.py`
  - `python3 tools/export_parent_dependency_inventory.py`
  - `python3 tools/audit_parent_dependency_drift.py`
  - `python3 tools/export_wake_threshold_attribution.py`
  - `python3 tools/score_report_usefulness.py`
  - `python3 tools/review_runtime_gaps.py`

Acceptance criteria:
- Tests pass without network and without vendor credentials.
- No secrets or raw vendor payloads are written.
- Runtime snapshot/audit artifacts reflect new contract and source-health behavior.

## Expanded Test Plan

### Unit

- Provider normalization maps ThetaData IV/Greeks/OI rows into canonical derived observations.
- Provider normalization maps Polygon/Massive chain snapshot rows into canonical derived observations when IV/Greeks/OI are present.
- Tradier `greeks=true` rows map IV/Greeks as constrained courtesy data with hourly-Greeks confidence penalty.
- Missing credentials produce explicit fetch records with `status=failed`, `error_class=missing_credentials`, and `application_error_code=missing_api_key`.
- Subscription denial, DNS errors, and schema drift produce `status=failed` plus distinct `error_class`/`application_error_code`; rate limits produce `status=rate_limited`.
- Partial provider coverage produces `status=partial` only when some requested options-IV observations are usable.
- Compiler confidence increases only for fresh, rights-compatible, non-proxy provider observations.
- Compiler adds `missing_primary_options_iv_source` when only Nasdaq/yfinance proxy exists.
- Product validator rejects raw provider payload fields, credentials/account identifiers, threshold mutation language, and wake/execution authority claims in options-IV report text or envelope fields.

### Integration

- No credentials: provider fetcher writes degraded records; compiler emits degraded/empty primary surface; report chain continues.
- Mock ThetaData success: compiler emits `proxy_only=false`, IV/skew/term metrics, source-health refs, and review-only flags.
- Mock Polygon success plus proxy fallback: provider symbols use provider confidence; other symbols remain proxy-only.
- Stale provider snapshot: provider IV values remain visible but confidence is penalized and stale-reuse guard is active.
- Source health ingests options-IV fetch records and produces deterministic hashes.
- Finance context pack includes `options_iv_surface_summary` while leaving `candidate_contract.required_fields` and `allowed_evidence_refs` unchanged.
- Renderer, reader bundle, and decision archive include only compact derived options-IV summaries and refs.

### E2E / Report Path

- Premarket report chain runs with no credentials and does not fail due to options-IV fetch.
- Context pack includes the repaired surface only as source context, not JudgmentEnvelope primary authority, wake authority, or threshold authority.
- Product validator and delivery safety pass with degraded options-IV health disclosure.
- Reader bundle/archive include derived surface and source-health summaries, not raw provider payloads.

### Observability

- `state/options-iv-provider-snapshot.json` records generated_at, status, provider set, symbol count, and no-execution flags.
- `state/options-iv-fetch-records.jsonl` records provider attempts with `SourceFetchRecord.status` limited to `ok|partial|rate_limited|failed` and detailed missing-credentials/network/subscription/schema diagnostics in metadata.
- `state/source-health.json` includes options-IV source rows and stale-reuse guard details.
- `state/options-iv-surface.json` summary reports missing IV, proxy-only, stale/unknown, and provider confidence ranges.

## Pre-Mortem

1. Provider adapter silently writes empty success because credentials are absent or subscription lacks Greeks/IV.
   - Mitigation: treat missing credentials, subscription denial, and empty IV fields as `status=failed` or `partial` fetch records with explicit `error_class`/`application_error_code`, source-health degraded states, and compiler penalties.

2. A licensed provider returns rich raw payloads and the implementation persists them in state or exposes them downstream.
   - Mitigation: normalize in memory, write derived-only rows, add tests that raw payload keys are not retained, and mark rights policy on each row.

3. Runtime starts failing during premarket because a provider endpoint is down or local Theta Terminal is unavailable.
   - Mitigation: run fetcher as optional, bounded timeout per provider, compiler degrades deterministically, source health records the outage, report path continues.

4. Downstream report code treats options-IV surface as new judgment authority because it appears in the LLM context pack.
   - Mitigation: Phase 6 explicitly adds it as `options_iv_surface_summary` source context only, keeps `candidate_contract.required_fields` and `allowed_evidence_refs` unchanged, and adds validator checks against wake/threshold/execution claims.

## Rollback Plan

- Keep `scripts/options_flow_proxy_fetcher.py` and current proxy compiler behavior available throughout P2.
- If provider lane causes runtime failures, remove or disable only the optional provider fetch step from `scripts/finance_discord_report_job.py`; leave compiler fallback to proxy-only.
- If surface v2 consumers regress, emit the existing v1 fields alongside additive v2 fields until downstream tests are updated.
- If source-health integration is noisy, keep fetch records but temporarily exclude options-IV provider rows from `source_health_monitor.py` while preserving no-execution/proxy penalties in the surface.
- Do not delete existing state artifacts during rollback; write new generated artifacts atomically and let normal report/archive tools supersede them.

## Concrete File Touchpoints

Likely edits:
- `docs/openclaw-runtime/contracts/options-iv-surface-contract.md`
- `docs/openclaw-runtime/contracts/source-scout-contract.md`
- `docs/openclaw-runtime/contracts/source-health-contract.md`
- `scripts/source_scout.py`
- `scripts/options_iv_provider_fetcher.py` new
- `scripts/options_iv_surface_compiler.py`
- `scripts/source_health_monitor.py`
- `scripts/finance_llm_context_pack.py`
- `scripts/finance_decision_report_render.py`
- `scripts/finance_report_reader_bundle.py`
- `scripts/finance_decision_log_compiler.py`
- `scripts/finance_report_product_validator.py`
- `scripts/finance_discord_report_job.py`
- `tests/test_source_scout_phase01.py`
- `tests/test_options_iv_surface_phase03.py`
- `tests/test_options_iv_provider_fetcher_p2.py` new
- `tests/test_options_iv_surface_p2.py` new
- `tests/test_source_health_monitor_phase09.py`
- report/context/reader/validator tests for options-IV source-context authority

Generated/validated artifacts:
- `state/options-iv-provider-snapshot.json`
- `state/options-iv-fetch-records.jsonl`
- `state/options-iv-surface.json`
- `state/source-health.json`
- runtime docs/snapshots after stable contract changes

## Available Agent Types and Staffing Guidance

Available agent types in this session include:
- `planner`
- `architect`
- `critic`
- `explore`
- `executor`
- `test-engineer`
- `verifier`
- `dependency-expert`
- `security-reviewer`
- `build-fixer`
- `writer`

Recommended `ralph` path:
- One `executor` owns implementation sequentially with high reasoning.
- Use `dependency-expert` read-only first only if live provider API shape must be rechecked against official docs during implementation.
- Use `test-engineer` for test matrix review before broad runtime wiring.
- Use `verifier` for final evidence review.

Recommended `team` path:
- Lane A, `executor`, high reasoning: provider fetcher and normalized observation records.
- Lane B, `executor`, high reasoning: compiler extension and surface contract compatibility.
- Lane C, `test-engineer`, medium reasoning: unit/integration tests and no-credential report smoke.
- Lane D, `writer` or `architect`, medium reasoning: contract/source-scout/source-health documentation.
- Lane E, `verifier`, high reasoning after integration: full test/audit evidence.

Launch hints:
- Sequential: `$ralph implement .omx/plans/p2-options-iv-volatility-surface-repair-ralplan.md`
- Coordinated: `$team implement .omx/plans/p2-options-iv-volatility-surface-repair-ralplan.md`
- Team verification path should run tests in this order: focused P2 tests, full pytest, compileall, operating-model audit, benchmark-boundary audit, then report-path smoke.

## Open Questions

- Which provider credentials or subscriptions actually exist in the deployment environment? The plan does not require them, but activation priority changes if one is already available.
- Should ORATS remain candidate-only until agreements are documented, or should an adapter skeleton be included with all live calls disabled?
- Is `options-iv-surface-v2-shadow` acceptable, or should this be an additive v1-compatible contract to minimize downstream changes?
