# Source-to-Campaign Phase 04 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/source-to-campaign-phase-04-context-gap-first-class-unknowns-ralplan.md`
- `docs/openclaw-runtime/contracts/context-gap-contract.md`
- `scripts/context_gap_compiler.py`
- `tests/test_context_gap_compiler.py`
- `tests/test_information_dominance_phase2_contract.py`

Checks:
- ContextGap records now expose canonical status and closure fields while preserving legacy compatibility fields.
- Missing issuer/filing confirmation now uses the Phase 01 lane name `corp_filing_ir`.
- Each generated gap includes `gap_status=open`, `closure_condition`, `weak_claim_ids`, `suggested_sources`, `source_lane_present`, and `linked_campaign_id`.
- `weak_claim_ids` and `suggested_sources` mirror legacy `what_claims_remain_weak` and `which_source_could_close_it`, giving later follow-up/replay code a migration path.
- Phase remains shadow-only: no delivery blocking, threshold mutation, wake change, or execution authority.

Risks:
- Existing downstream fixtures still use older `corporate_filing` strings in some tests/docs; compiler output now uses the canonical `corp_filing_ir` lane while accepting legacy source lookup.
- Gap closure is defined but not yet automated. Later phases must wire closure to report-time archive and source arrivals.

Required follow-up:
- Phase 05 should archive context gaps per report and start line-to-gap/line-to-claim mapping.
- Follow-up router should later return these gap objects in `insufficient_data` responses.

Verification evidence:
- `python3 -m pytest -q tests/test_context_gap_compiler.py tests/test_information_dominance_phase2_contract.py`
- Full tests and compileall before commit.

Commit gate: pass.
