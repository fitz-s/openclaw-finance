# Source-to-Campaign Phase 07 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/source-to-campaign-phase-07-campaign-os-board-upgrade-ralplan.md`
- `docs/openclaw-runtime/contracts/campaign-projection-contract.md`
- `scripts/campaign_projection_compiler.py`
- `tests/test_campaign_projection_lifecycle.py`
- `tests/test_decision_dense_campaign_surfaces.py`

Checks:
- CampaignProjection now carries undercurrent score, advisory promotion candidate, promotion blockers, peacetime update eligibility, packet update visibility, and wake impact.
- CampaignProjection exposes lane coverage summary with source diversity, cross-lane confirmation, cross-lane score, and degraded source counts.
- Board markdown includes an `Evidence：` line with lane/source counts, score, degraded source count, and top blocker.
- Existing object-first `Implication/Why/Verify/Unknown` structure remains intact.
- `wake_impact` remains `none`; no wake/delivery/JudgmentEnvelope/execution behavior changed.

Risks:
- Board cards are slightly longer. Current tests check content but not live Discord byte limits for every market state.
- Evidence quality line is compact and may need UX tuning after real Discord review.

Required follow-up:
- Phase 08 follow-up context router should use these fields in compare/challenge/source slices.
- Phase 11 reviewer packets should expose lane coverage and blockers per campaign.

Verification evidence:
- `python3 -m pytest -q tests/test_campaign_projection_lifecycle.py tests/test_decision_dense_campaign_surfaces.py`
- Full tests and compileall before commit.

Commit gate: pass.
