# Ingestion Fabric Phase 07 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-07-query-planner-pack-ralplan.md`
- `scripts/finance_llm_context_pack.py`
- `scripts/query_pack_planner.py`
- `tests/test_query_pack_planner_phase07.py`
- `tests/test_llm_context_pack.py`

Checks:
- Scanner pack now declares `scanner_canonical_role=planner_first_legacy_observation_bridge`.
- Scanner pack explicitly sets `free_form_web_search_canonical_ingestion=false`.
- Scanner pack carries QueryPack contract metadata, closed-schema intent, prompt version, planner output paths, and planning-only tool policy.
- `free_form_web_search_as_canonical_ingestion` is now a forbidden scanner action.
- Legacy observation schema remains as compatibility bridge and is explicitly not canonical ingestion.
- `query_pack_planner.py` emits deterministic QueryPack rows for invalidator checks, opportunity follow-up, thesis closure, and unknown discovery.
- Unknown discovery packs carry known-symbol exclusions so held/watchlist names cannot satisfy the lane.
- QueryPack rows are marked `planner_not_evidence`, `pack_is_not_authority`, and `no_execution`.
- The phase does not edit parent cron jobs, invoke deterministic fetchers, mutate wake/report/delivery, or remove legacy `finance_worker.py` compatibility.

Risks:
- Parent OpenClaw scanner prompt still asks for legacy observations; this phase only changes the finance context pack and adds the planner compiler.
- QueryPack generation is heuristic and should later be informed by source ROI, lane watermarks, and query registry outcomes.
- Active cutover requires Phase 08 reducer migration and parent runtime prompt/job updates.

Required follow-up:
- Phase 08 should move `finance_worker.py` toward reducer-over-claims/query-pack output rather than canonical ingress.
- Phase 09 should wire query registry/source health feedback into planner selection before active scheduling.

Commit gate: pass.
