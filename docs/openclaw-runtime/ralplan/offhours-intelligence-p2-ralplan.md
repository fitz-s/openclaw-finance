# RALPLAN P2: Budgeted Brave Compression Lane

Status: approved_for_p2_implementation
Mode: consensus_planning
Scope: LLM Context / Answers compression activation, sidecar-only

## Source Review And Explorer Inputs

Primary review file: `/Users/leofitz/Downloads/review 2026-04-18.md`.

Phase explorer inputs:

- Internal explorer: `docs/openclaw-runtime/scouts/offhours-intelligence-p2-internal-explorer.md`
- External scout: `docs/openclaw-runtime/scouts/offhours-intelligence-p2-external-scout.md`

## Task Statement

Add a budget-aware compression activation lane for Brave LLM Context and Brave Answers. It must run after source discovery, require seed URLs or selected source context, use separate `llm_context` and `answers` budget kinds, and preserve the sidecar-only authority boundary.

## RALPLAN-DR

### Principles

1. Compression after discovery: LLM Context and Answers cannot be first-pass discovery.
2. Separate budgets: `search`, `llm_context`, and `answers` counters must not be conflated.
3. Answers is never authority: answer text remains derived context only; only citation URLs can seed later fetches.
4. Default dry-run: P2 should expose activation and budget reports without causing new live endpoint burn by default.
5. No wake/delivery mutation: compression output must not alter Discord delivery, thresholds, judgment, or execution authority.

### Decision Drivers

1. Current Brave activation only routes Web/News and only budgets Search.
2. Existing LLM Context and Answers scripts have good local guards but no orchestration lane.
3. The review requires Answers to reduce search/API usage only when used as a citation-gated compression primitive.
4. Existing runtime is rate-limited, so live compression must be opt-in later.

### Viable Options

#### Option A: Extend `brave_source_activation.py`

Pros:
- Single activation runner.

Cons:
- Mixes discovery and compression.
- Higher risk of turning Answers into an implicit evidence path.

#### Option B: Add separate `brave_compression_activation.py`

Pros:
- Clean separation of discovery vs compression.
- Easier budget ownership.
- Safer default dry-run behavior.
- Matches the review's source-to-decision layering.

Cons:
- Adds one new runner and report.

#### Option C: Activate Answers directly from QueryPacks

Pros:
- Fastest route to answers.

Cons:
- Violates seed-source discipline and risks generic hallucinated synthesis.

### Recommendation

Choose Option B.

## ADR

Decision: P2 adds a separate budgeted compression activation runner. It consumes QueryPacks plus seed URLs from prior Web/News records, then runs LLM Context and Answers only when scope and budget checks pass. Parent offhours dry-run includes this runner in dry-run mode.

Rejected: single source activation runner | discovery and compression have different authority and budget rules.
Rejected: direct Answers activation | no seed-source discipline.

## Implementation Plan

1. Add `scripts/brave_compression_activation.py`.
   - Reads planned QueryPacks and existing Brave Web/News fetch records.
   - Selects seed URLs from successful/dry-run source records.
   - Builds scoped LLM Context packs and sidecar-only Answers packs.
   - Checks `llm_context` and `answers` budget before invocation.
   - Defaults to dry-run unless `--live` is passed.
   - Writes `state/brave-compression-activation-report.json`.

2. Add budget metadata to records.
   - LLM Context records and Answers sidecar records created by the runner receive `budget_decision`, `session_aperture`, and `compression_activation_runner` fields.

3. Wire parent offhours dry-run path.
   - `finance_parent_market_ingest_cutover.py --scanner-mode offhours-scan` runs compression activation with `--dry-run` after Web/News activation.
   - Market-hours runs do not include it.

4. Update source health/snapshot visibility.
   - Source health already reads Context/Answers records.
   - Snapshot exporter includes sanitized compression activation report and P2 docs.

## Test Plan

- `test_compression_activation_requires_seed_urls_before_context_or_answers`
- `test_compression_activation_llm_context_budget_denial_blocks_fetch`
- `test_compression_activation_answers_budget_denial_blocks_sidecar`
- `test_compression_activation_dry_run_does_not_consume_budget`
- `test_compression_activation_records_are_sidecar_only_and_not_authority`
- `test_parent_cutover_runs_compression_activation_only_for_offhours`
- `test_snapshot_exports_compression_activation_report`

## No-Go Items For P2

- No live Answers default.
- No answer prose as evidence.
- No wake/report/delivery/threshold mutation.
- No cron cadence mutation.
- No broker/execution authority.
