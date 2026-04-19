# Source-to-Campaign Phase 11 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/source-to-campaign-phase-11-reviewer-exact-replay-ralplan.md`
- `tools/export_reviewer_report_packets.py`
- `tests/test_export_reviewer_report_packets.py`

Checks:
- Reviewer exporter now checks `state/report-archive/{report_id}/manifest.json` and prefers archived artifacts when available.
- Packets include `report_time_replay` with exact replay availability, artifact availability, missing artifacts, and line-to-claim coverage summary.
- Archived envelope is used for operator surface when available.
- Archived source atoms, claim graph, context gaps, source health, and options IV surface feed the information acquisition snapshot.
- Legacy reports without archive remain explicitly non-replayable.
- Sanitization still excludes Discord conversation, thread IDs, account IDs, portfolio raw state, and raw snippets.

Risks:
- Line-to-claim refs are still heuristic until renderer emits explicit bindings.
- Real exact replay coverage depends on Phase 05 archive being present for a report.

Required follow-up:
- Phase 12 source ROI should use archived replay artifacts for attribution.
- Future reviewer exports should expose cache coverage and route examples.

Verification evidence:
- `python3 -m pytest -q tests/test_export_reviewer_report_packets.py`
- Full tests and compileall before commit.

Commit gate: pass.
