# Source Freshness Deep Check - 2026-04-18

## Scope

This package isolates the parts that are still not normal after finance renderer / BOOT / Discord loop hardening.

Checked surfaces:

- Finance legacy scanner reducer and gate state.
- Parent `services/market-ingest` live evidence, source health, packet, and wake outputs.
- Brave Search / News / LLM Context / Answers sidecars.
- Options flow / IV surface freshness.
- Cron run history for active finance jobs.
- Discord gateway DNS/network symptoms and market-intel MCP startup.

Out of scope:

- Trading or execution authority.
- Rewriting report UX.
- Changing source promotion policy before root cause is documented.

## Executive Verdict

Finance report/render/validator/safety are operational, but market intelligence quality is not healthy.

The current failure mode is not simply "no new data." Parent market-ingest can produce new evidence records, but nearly all fresh narrative records are demoted to `CONTEXT_ONLY`, and no current evidence is wake-eligible. As a result, reports can continue to repeat the same older Reuters-supported narrative even when newer headlines exist.

The second failure mode is source activation: Brave outputs remain dry-run or quota-limited, and options IV is still a stale proxy surface with no real IV observations.

## Current Evidence Snapshot

Commands run in this package:

```bash
python3 scripts/source_health_monitor.py
python3 scripts/gate_evaluator.py
openclaw cron runs --id b2c3d4e5-f6a7-8901-bcde-f01234567890 --limit 8
openclaw cron runs --id finance-midday-operator-review-v1 --limit 8
openclaw cron runs --id c031f32c-0392-45bb-ae1a-ad7e7aec6938 --limit 8
openclaw cron runs --id f57c165f-7683-4816-ab2c-10abda099b9f --limit 8
```

Latest local state observed:

- `state/intraday-open-scan-state.json`: `last_scan_time=2026-04-18T14:30:00.145439+00:00`, `accumulated=4`.
- `state/report-gate-state.json`: `dataStale=false`, `candidateCount=4`, `recommendedReportType=hold`, `decisionReason=thresholds not met`.
- Parent live evidence: `46` to `54` records depending on last run window.
- Parent wake decision: `PACKET_UPDATE_ONLY`.
- Live evidence promotion: `allowed_for_wake=0`.
- Source health: `degraded`.

## Findings

### F1 - Fresh narrative exists but cannot support wake or judgment

Parent market-ingest emitted fresh Hormuz-related records from scanner/native emergency news, including:

- `2026-04-18T13:00:44Z` NDTV headline about Indian-flagged vessels and Iran gunboats.
- `2026-04-18T12:17:00Z` Times of India Hormuz headline.

But both were promoted as `CONTEXT_ONLY` with `reason_code=source_license_not_allowed_for_wake` and `allowed_for_judgment_support=false`.

Evidence files:

- `/Users/leofitz/.openclaw/workspace/services/market-ingest/state/live-evidence-records.jsonl`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/source_promotion.py`
- `/Users/leofitz/.openclaw/workspace/services/market-ingest/config/source-registry.json`

Observed aggregate:

- `promotion decisions`: `CONTEXT_ONLY=46`
- `allowed_for_wake`: `False=46`
- `allowed_for_judgment_support`: `True=38`, `False=8`
- reason codes: `source_not_wake_eligible=28`, `title_not_confirmed_event=12`, `source_license_not_allowed_for_wake=6`

Root cause:

`native-emergency-news`, NDTV, Times of India, and similar web/news paths fall through to `source:unknown_web`. `source:unknown_web` has `license_usage=unknown`, `eligible_for_wake=false`, and `eligible_for_judgment_support=false`. The policy is defensible for raw unknown web, but too blunt for confirmed-event headline metadata that should at least be usable as support-only or "needs primary confirmation" context.

Impact:

The system can see fresh headlines but cannot use them to wake or materially improve reports. This directly explains repeated report themes based on the same older primary-wire sources.

### F2 - Source freshness stale warning was partially a sequencing artifact

Earlier health showed `no_source_atoms_in_reducer`. After rerunning `source_health_monitor.py` after the reducer/source atom step, the reducer row no longer had that breach.

Current reducer health after rerun:

- `source:finance_worker_reducer`: `coverage_status=ok`
- `last_success_at=2026-04-18T14:30:08.103427Z`
- `breach_reasons=[]`

Root cause:

`finance_parent_market_ingest_cutover.py` runs `source_health_monitor.py` before later scripts may refresh source atoms / claim graph / context gaps in some call paths. In the report job path, source atom compilation happens before parent bridge, but manual scanner/report smoke paths can still expose stale health ordering.

Impact:

This is not the main intelligence-quality failure anymore, but it can produce misleading operator/reviewer diagnostics.

### F3 - Gate stale is currently cleared, but gate authority is still legacy-biased

After latest worker/gate rerun:

- `dataStale=false`
- `candidateCount=4`
- `shouldSend=false`
- `recommendedReportType=hold`
- `wake_class=PACKET_UPDATE_ONLY`

However, `gate_evaluator.py` still determines data staleness from `state/intraday-open-scan-state.json:last_scan_time`, not from parent live-evidence freshness or WakeDecision freshness.

Root cause:

The source-to-campaign fabric is only partially cut over. Parent market-ingest can produce a fresh packet, but the legacy gate still thinks in terms of scanner buffer observations.

Impact:

Fresh parent evidence can update packets and boards without satisfying the old threshold/gate semantics. This can make the system look silent or repetitive despite upstream packet mutation.

### F4 - Brave is not a live primary source path yet

Current Brave state:

- `state/brave-news-search-results.jsonl`: rows are `status=dry_run`.
- `state/brave-answer-sidecars/latest.jsonl`: row is `status=dry_run`.
- `state/brave-llm-context-results.jsonl`: row is `status=dry_run`.
- `source:brave_llm_context`: `quota_status=degraded`, `rate_limit_status=limited`, `last_quota_error=USAGE_LIMIT_EXCEEDED`.

Root cause:

The repo has Brave fetcher/sidecar contracts and dry-run artifacts, but the active production path is not performing live Brave fetches as evidence-producing primary source acquisition. LLM Context has already hit usage limits in the recorded audit.

Impact:

Brave is currently not closing the freshness gap. It gives the appearance of an integrated source lane but does not provide live decision-grade evidence in the active path.

### F5 - Options IV sensitivity is still weak

Current options surface:

- `state/options-flow-proxy.json`: `status=degraded`, `generated_at=2026-04-18T10:30:43.204470+00:00`, `top_events=[]`.
- `state/options-iv-surface.json`: `generated_at=2026-04-18T00:12:00.890411Z`.
- IV summary: `missing_iv_count=6`, `stale_or_unknown_chain_count=6`, `proxy_only_count=6`, provider confidence `0.05`.

Root cause:

The current IV surface is compiled from a Nasdaq/yfinance proxy. It does not reliably receive actual IV observations and currently carries stale/proxy penalties for every symbol.

Impact:

The system remains insensitive to implied-volatility structure, vol skew, term structure, and unusual IV expansion. This matches the user-observed weakness.

### F6 - Scanner cron history proves the previous scanner implementation was unreliable

Recent market-hours scanner history included repeated `cron: job execution timed out` entries at 420s. Offhours scanner also had recent 420s timeouts. The active cron prompt has now been hardened to deterministic output and 180s timeout, but it has not yet had a weekday scheduled run after the change.

Evidence:

- `c031f32c-0392-45bb-ae1a-ad7e7aec6938`: repeated timeout history, total history count `434`.
- `f57c165f-7683-4816-ab2c-10abda099b9f`: repeated timeout history, total history count `98`.

Root cause:

OpenClaw cron still wraps deterministic work in an `agentTurn`. Historical prompts allowed the model to spend large context/time producing scanner prose and observations. The new prompt is stricter, but runtime still depends on an LLM wrapper to run deterministic commands.

Impact:

Until the next weekday run verifies success, scanner cron state remains suspect. Long term, scanner should be a direct command job or a tiny deterministic stdout script path, not a large LLM run.

### F7 - Scheduled report delivery works, but model/runtime cost is high

Recent `finance-premarket-brief` runs delivered successfully. However, run history shows large token usage for what should be a deterministic stdout job, e.g. input tokens above `120k` and durations over two minutes.

Root cause:

The cron delivery adapter is still using an agent/model run to execute a deterministic command and return stdout.

Impact:

This is fragile under model/network outages and wastes quota. It also increases the chance of timeout during market hours.

### F8 - Discord DNS was externally flaky; shell DNS is currently OK but gateway still logged failures

Current shell probes resolved and reached:

- `discord.com`
- `gateway.discord.gg`
- `https://discord.com/api/v10/gateway` returned `200`.

But gateway logs around `09:00-09:05 CT` still showed repeated `getaddrinfo ENOTFOUND discord.com/gateway.discord.gg` plus stale gateway socket restarts.

Root cause:

Likely runtime process / network context instability rather than finance renderer logic. The finance-specific direct bindings for previously stormy channels are currently zero.

Impact:

Even if finance logic is fixed, live Discord delivery can still fail until gateway process/network stability is confirmed.

### F9 - market-intel MCP no longer fails with `spawn python ENOENT`, but gateway MCP startup can still timeout

Plugin manifests now use `/opt/homebrew/bin/python3`. Direct process launch exits cleanly. market-intel tool smoke passes. Gateway logs now show `MCP server connection timed out after 30000ms`, not `spawn python ENOENT`.

Root cause:

The original command path bug was fixed. Remaining issue is MCP handshake/startup timing under gateway load or stdin/stdout protocol expectations.

Impact:

Not directly blocking finance reports, but it is still a runtime health warning.

## Root Cause Stack

1. Source promotion is too binary for unknown/restricted web: fresh confirmed headlines become non-supporting context.
2. Brave source lanes are not live evidence lanes yet; they are dry-run/quota-limited sidecars.
3. Options IV is still proxy-only and stale, with no reliable IV vendor path.
4. Legacy scanner/gate semantics and parent packet semantics are not fully unified.
5. Deterministic jobs are still being mediated by LLM cron runs, causing timeout/quota fragility.
6. Gateway/Discord network stability is an external runtime issue, not solved by finance repo tests.

## Recommended Repair Package Order

### P0 - Promotion policy repair for fresh-but-untrusted headlines

Goal: stop silently discarding fresh market-moving headlines while preserving review-only and source-quality discipline.

Implementation direction:

- Add a `source:news_web_candidate` or explicit `native-emergency-news` registry class.
- Permit confirmed-event headline metadata to become `allowed_for_judgment_support=true` when it has timestamp, source domain, and source URL/title metadata.
- Keep `allowed_for_wake=false` until primary confirmation or cross-source confirmation exists.
- Add validator warnings when primary surface relies on old primary-wire evidence while newer context-only headlines exist.

Acceptance:

- Fresh Hormuz-style confirmed headlines become support-only context, not invisible noise.
- No unknown web source becomes wake-eligible without confirmation.
- Reports must say "fresh unconfirmed headline exists; primary confirmation missing" instead of repeating old Reuters as if nothing changed.

### P1 - Brave live activation with quota-aware fallback

Goal: make Brave Search/News/Answers produce live fetch records or explicit actionable degradation.

Implementation direction:

- Wire Brave News/Search into scanner source acquisition in non-dry-run mode when credentials/quota exist.
- Answers sidecar should contribute citation URLs only, never raw answer text as canonical evidence.
- LLM Context quota failures should open a breaker and route to search/news fallback.
- Add source-health operator field: `source_lane_unavailable_reason`.

Acceptance:

- `state/brave-news-search-results.jsonl` has `status=ok|partial|rate_limited`, not permanent `dry_run`.
- Source health differentiates missing credential, quota exhausted, DNS failure, and no-result.

### P2 - Options IV vendor / real surface repair

Goal: stop treating stale Nasdaq/yfinance proxy as IV awareness.

Implementation direction:

- Promote a real options vendor path or a better Nasdaq parser with freshness SLA.
- Track IV, skew, term structure, volume/OI, and stale-chain confidence separately.
- Board/report should explicitly show "IV unavailable" if all rows are proxy-only.

Acceptance:

- `options-iv-surface.json` has non-null IV observations for liquid watchlist names when the market/options chain is available.
- `provider_confidence=0.05` no longer silently flows into high-confidence report prose.

### P3 - Gate freshness unification

Goal: align old scanner gate with parent market-ingest packet freshness.

Implementation direction:

- Add a deterministic `live_evidence_freshness` block to `report-gate-state.json`.
- Gate stale should consider both legacy scanner observations and parent live evidence/WakeDecision.
- `PACKET_UPDATE_ONLY` should update peacetime/undercurrent boards and source-health warnings even if it does not trigger full report.

Acceptance:

- Parent packet mutation is visible in finance gate diagnostics.
- No stale report warning when live evidence is fresh; no silent full report when all evidence is context-only.

### P4 - Direct deterministic cron execution

Goal: remove LLM agent timeout risk from deterministic scanner/report shell work.

Implementation direction:

- Prefer OpenClaw direct command cron if supported.
- If not supported, make tiny deterministic stdout wrapper scripts and minimize context/model selection.
- Cron run history should show low duration and low/no token usage for deterministic jobs.

Acceptance:

- Scanner and report jobs do not consume 100k+ input tokens to run local scripts.
- Timeout history does not recur after the next weekday schedule.

### P5 - Gateway/MCP runtime stability

Goal: separate finance correctness from transport/runtime failures.

Implementation direction:

- After network stabilizes, reload/restart gateway once and confirm Discord gateway ready.
- Investigate market-intel MCP handshake timeout separately from spawn-path fix.
- Keep finance direct channel bindings at zero for general/market-monitoring/evolution unless explicitly intended.

Acceptance:

- No new `getaddrinfo ENOTFOUND` bursts in gateway log after restart.
- market-intel MCP starts without 30s timeout.

## Non-Findings / Clarifications

- Renderer/mainline BOOT checks are no longer blocking finance report generation.
- The old `no_source_atoms_in_reducer` breach is not currently active after health rerun; it was a sequencing artifact.
- Today is Saturday, so `finance_discord_report_job.py --mode marketday-review` returning `NO_REPLY` is expected.
- The current issue is intelligence freshness and source eligibility, not trade execution or report validator failure.

## Next Implementation Package

Start with P0 + P3 together. They are tightly coupled: fresh context-only evidence must become visible to the operator, and the gate must disclose why it cannot yet become wake/judgment evidence.

Do not start with report prose tuning. The report prose is repeating old items because the evidence authority layer is suppressing newer sources. Fix source eligibility and gate visibility first.
