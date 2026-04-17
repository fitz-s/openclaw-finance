# Ingestion Fabric Phase 06 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-06-brave-answers-sidecar-ralplan.md`
- `scripts/brave_answers_sidecar.py`
- `tests/test_brave_answers_sidecar_phase06.py`

Checks:
- Sidecar blocks any pack that is not `authority_level=sidecar_only`.
- Request payload defaults to `model=brave`, `stream=true`, and `enable_citations=true`.
- Advanced Answers flags are request-body knobs and stay behind streaming mode.
- Stream parser handles citation, enum, and usage tags.
- Only citation URLs become `citation_evidence_candidates`.
- Entity enum items and usage tags are telemetry only and never evidence records.
- Answer prose persists only as bounded derived context preview plus digest and is explicitly non-canonical.
- Citation snippets are digested; raw snippets, raw stream frames, and raw response bodies are not persisted.
- Answers without citations have `promotion_eligible=false` and emit no evidence candidates.
- 429-style failures become explicit throttle/quota metadata.
- Dry-run works without API key or network.
- No scanner, wake, report, delivery, threshold, or parent OpenClaw behavior is changed.

Risks:
- Live Brave Answers API behavior is not exercised because tests use mocks and local quota is degraded.
- Research mode can be long-running; this phase does not implement long-running orchestration.
- Citation tag schema should be rechecked before active use because Brave can evolve streaming payloads.
- Answers has separate billing/capacity from Search; source health/quota accounting must treat it separately before scheduling.

Required follow-up:
- Phase 07 should downgrade scanner into QueryPack planner/scout and keep sidecar outputs out of canonical ingestion.
- Phase 09 source health should add Answers-specific quota/rate-limit accounting.

Commit gate: pass.
