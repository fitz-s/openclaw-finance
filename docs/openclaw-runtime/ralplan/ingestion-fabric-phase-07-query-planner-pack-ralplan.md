# RALPLAN Ingestion Fabric Phase 07: Query Planner Pack And Scanner Role Downgrade

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Move the scanner surface from LLM-first canonical ingestion toward QueryPack planning. This phase does not delete the legacy observation path; it adds a deterministic QueryPack planner and updates the scanner context pack so free-form web search is no longer described as primary/canonical ingestion.

## RALPLAN-DR Summary

### External Scout Inputs

Source class: agent safety, structured-output, JSON Schema, and eval guidance.

Integrated findings:
- Split the scanner into planner and deterministic ingestion phases; free-form retrieved text/tool output must not directly drive canonical state.
- Planner output should be a closed-world structured schema with explicit required fields and no unvalidated extra fields.
- The planner should expose planning-only tools; deterministic fetchers perform source acquisition later.
- Tool/search output is untrusted until validated by deterministic fetch/normalization.
- Prompt/policy versions should be explicit and regression-tested.
- Tests should cover schema conformance, tool boundary, refusal/blocking behavior, and prompt-injection resistance.

Reference links from scout:
- OpenAI agent safety: https://platform.openai.com/docs/guides/agent-builder-safety
- OpenAI structured outputs: https://openai.com/index/introducing-structured-outputs-in-the-api/
- JSON Schema object reference: https://json-schema.org/understanding-json-schema/reference/object
- JSON Schema 2020-12: https://json-schema.org/draft/2020-12/draft-bhutton-json-schema-01
- OpenAI instruction hierarchy: https://openai.com/index/the-instruction-hierarchy/
- OpenAI evaluation best practices: https://platform.openai.com/docs/guides/evaluation-best-practices

### Principles

1. **Planner is not evidence.** QueryPack output can request source acquisition; it cannot satisfy evidence, wake, judgment, or report authority.
2. **Compatibility bridge first.** Keep legacy scanner observation flow available while shifting semantics to planner-first.
3. **No free-form web_search authority.** The LLM scanner may propose bounded queries; deterministic fetchers perform source acquisition.
4. **No hot-path break.** Do not edit OpenClaw cron jobs or parent runtime in this phase.
5. **Object-linked planning.** Query packs should carry purpose, lane, required entities, source object refs, forbidden actions, and no-execution boundary.

### Decision Drivers

1. Review2 says scanner should become query planner / scout / sidecar analyst, not canonical source ingestion.
2. Phases 04-06 added deterministic Brave Web/News/LLM Context/Answers surfaces that need QueryPack input.
3. Phase 03 added query registry/lane watermarks/source memory, so query repetition can be controlled before fetches.
4. Current scanner pack still emphasizes evidence candidates and legacy observations, which preserves the old mental model.

### Viable Options

#### Option A - Hard cutover scanner to QueryPack-only now

Rejected for this phase. It risks breaking current cron prompt, `finance_worker.py`, and opportunity/invalidator consumers before reducer migration.

#### Option B - Add planner-first pack semantics and deterministic query pack compiler, keep legacy fallback

Selected. It changes the operator/agent contract while preserving old runtime compatibility.

## Selected Design

Add `scripts/query_pack_planner.py`:
- Reads `state/llm-job-context/scanner.json` by default.
- Emits `state/query-packs/scanner-planned.jsonl` and optional report JSON.
- Builds QueryPack records for invalidator checks, opportunity follow-ups, thesis updates, and unknown discovery.
- Adds `source_object_refs`, `exclusion_symbols`, `planner_origin`, `planner_not_evidence=true`, `pack_is_not_authority=true`, and `no_execution=true`.
- Uses deterministic stable IDs.
- Emits closed-schema style QueryPack rows with planner/non-authority flags and no raw external content.

Modify `scripts/finance_llm_context_pack.py` scanner pack:
- `scanner_canonical_role=planner_first_legacy_observation_bridge`.
- `planner_prompt_version=query-planner-v1`.
- `tool_policy.planning_only=true` with free-form web search forbidden as canonical ingestion.
- Add QueryPack contract fields and output path.
- Mark `free_form_web_search_canonical_ingestion=false`.
- Add forbidden action `free_form_web_search_as_canonical_ingestion`.
- Add `query_pack_planner.py` to scanner required commands before legacy closure.
- Keep legacy observation schema as compatibility fallback.

## Acceptance Criteria

1. Scanner context pack declares QueryPack planner-first role.
2. Scanner pack emits enough QueryPack contract metadata for a planner/fetcher to act without guessing.
3. QueryPack planner writes deterministic QueryPack JSONL rows.
4. Unknown discovery QueryPacks include known-symbol exclusions and cannot be satisfied by held/watchlist symbols.
5. QueryPack rows remain non-authoritative and review-only.
6. Existing tests still pass; no cron/report/wake/delivery behavior changes.

## Test Plan

- `test_scanner_pack_declares_query_planner_first_boundary`
- `test_query_pack_planner_emits_required_query_pack_fields`
- `test_unknown_discovery_query_pack_carries_known_symbol_exclusions`
- `test_query_pack_planner_marks_packs_non_authoritative`
- `test_query_pack_planner_cli_writes_jsonl_and_report`

## Rollback

Remove `scripts/query_pack_planner.py`, tests, and scanner pack additions. Legacy scanner observation path remains intact.

## Critic Requirements

Implementation critic must verify:
- no parent cron/runtime mutation
- no active deterministic fetch execution
- no removal of compatibility observation path
- QueryPack is not evidence or judgment
- free-form web_search is no longer primary/canonical in scanner pack
- tests cover planner output and scanner pack boundary
