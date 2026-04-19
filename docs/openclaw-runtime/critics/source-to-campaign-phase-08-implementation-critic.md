# Source-to-Campaign Phase 08 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/source-to-campaign-phase-08-verb-specific-followup-ralplan.md`
- `docs/openclaw-runtime/contracts/followup-context-slice-contract.md`
- `docs/openclaw-runtime/contracts/followup-answer-contract.md`
- `scripts/finance_followup_context_router.py`
- `scripts/finance_followup_answer_guard.py`
- `tests/test_followup_context_router_phase6.py`
- `tests/test_followup_answer_guard.py`

Checks:
- Follow-up router now emits verb-specific evidence groups, coverage metadata, context gap guidance, and recommended answer status.
- `why` and `sources` routes produce different evidence requirements, proving the router is no longer a generic bundle digest selector.
- Missing compare context returns `insufficient_data` plus context gap guidance.
- Answer guard blocks responses that claim to be answered while required evidence coverage is missing.
- `insufficient_data` remains allowed and review-only.
- No parent Discord routing, wake, JudgmentEnvelope, threshold, delivery, or execution behavior changed.

Risks:
- Coverage still maps to campaign fields, not a full report-time archive slice. Phase 11 should connect archive artifacts.
- Some context gap guidance is synthesized from campaign known_unknowns and may be broad until line-to-claim bindings improve.

Required follow-up:
- Phase 09 deep-dive cache should preload verb-specific cards for these evidence groups.
- Phase 11 reviewer exact replay should export route coverage examples.

Verification evidence:
- `python3 -m pytest -q tests/test_followup_context_router_phase6.py tests/test_followup_answer_guard.py`
- Full tests and compileall before commit.

Commit gate: pass.
