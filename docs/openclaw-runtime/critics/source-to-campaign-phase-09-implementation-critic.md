# Source-to-Campaign Phase 09 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/source-to-campaign-phase-09-deep-dive-cache-ralplan.md`
- `scripts/finance_campaign_cache_builder.py`
- `scripts/finance_discord_campaign_board_deliver.py`
- `tests/test_decision_dense_campaign_surfaces.py`

Checks:
- Campaign cache now builds all verb cards with required evidence groups, grounding summary, answer status, refresh policy, review-only, and no-execution markers.
- Compare/scenario/source/trace cards can mark `insufficient_data` instead of pretending missing slices are answerable.
- Thread seed includes `预备深挖` with why/challenge/sources prebrief content, not only a menu.
- The change remains finance-local and does not alter parent Discord routing, wake, JudgmentEnvelope, thresholds, or execution authority.

Risks:
- Cache cards still summarize campaign fields rather than using report-time archive slices. Phase 11 should connect archive artifacts.
- Thread seed is longer; future live Discord tests should monitor length and readability.

Required follow-up:
- Phase 10 thread lifecycle should ensure longer-lived cache/thread surfaces do not accumulate indefinitely.
- Phase 11 reviewer packet exact replay should export cache card coverage.

Verification evidence:
- `python3 -m pytest -q tests/test_decision_dense_campaign_surfaces.py`
- Full tests and compileall before commit.

Commit gate: pass.
