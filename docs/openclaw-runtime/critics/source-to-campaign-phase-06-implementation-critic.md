# Source-to-Campaign Phase 06 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/source-to-campaign-phase-06-undercurrent-engine-ralplan.md`
- `docs/openclaw-runtime/contracts/undercurrent-card-contract.md`
- `scripts/undercurrent_compiler.py`
- `tests/test_undercurrent_engine.py`

Checks:
- Undercurrent cards now expose deterministic scoring and promotion gate fields.
- Promotion requires source diversity, cross-lane confirmation, capital relevance, manageable contradiction load, persistence, and acceptable freshness.
- Promotion blockers are explicit and reviewable.
- `PACKET_UPDATE_ONLY` semantics are explicit as `packet_update_visibility=board_mutation_only` and `wake_impact=none`.
- Existing undercurrent consumers remain compatible because old fields are preserved.
- No wake policy, threshold, Discord delivery, JudgmentEnvelope, or execution behavior changed.

Risks:
- Scoring weights are deterministic heuristics and should be validated against campaign outcomes in Phase 12.
- Capital relevance is inferred from linked refs and may over/under-score sparse cards.
- This phase only prepares board mutation semantics; actual Campaign OS board behavior remains later-phase work.

Required follow-up:
- Phase 07 should consume `undercurrent_score`, `promotion_candidate`, and blockers in CampaignProjection stage logic.
- Phase 12 should evaluate undercurrent false-positive rate and tune weights.

Verification evidence:
- `python3 -m pytest -q tests/test_undercurrent_engine.py`
- Full tests and compileall before commit.

Commit gate: pass.
