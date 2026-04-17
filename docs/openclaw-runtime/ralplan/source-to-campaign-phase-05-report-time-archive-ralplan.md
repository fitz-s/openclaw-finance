# RALPLAN Source-to-Campaign Phase 05: Report-Time Archive And Exact Replay

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Create a report-time archive layer so new finance reports can be replayed with the exact envelope, reader bundle, evidence atoms, claim graph, context gaps, source health, campaign board, options IV surface, and line-to-claim refs from the time of report generation.

This phase writes ignored runtime state only; it does not commit raw state, change delivery, or expose licensed snippets to reviewer packets.

## Principles

1. Exact replay requires report-time artifacts, not current snapshots.
2. Archive before external reviewer export.
3. Archive is internal runtime state; reviewer packets remain sanitized.
4. Line-to-claim mapping can start heuristic, but must be explicit about method and coverage.
5. No runtime behavior change except writing replay artifacts.

## Decision Drivers

1. The review identified that reviewer packets currently use current sanitized source state, not exact historical replay.
2. Existing report-reader bundles do not preserve every report-time artifact.
3. Later reviewer packet upgrades need a stable archive contract.

## Selected Plan

Add `scripts/finance_report_archive_compiler.py`, called by `finance_discord_report_job.py` after reader bundle/cache generation. It writes `state/report-archive/{report_id}/` with manifest and copied artifacts.

## Acceptance Criteria

- Archive manifest has `exact_replay_available=true` for new reports.
- Manifest references envelope, reader bundle, source atoms, claim graph, context gaps, source health, campaign board, options IV surface, and line-to-claim refs when present.
- Line-to-claim refs are generated from operator markdown line subject matching and marked `heuristic_subject_match`.
- Archive is under `state/` and remains ignored by git.
- Report job runs archive compiler as optional non-delivery-critical step.

## Test Plan

- `test_report_archive_compiler_writes_manifest_and_artifacts`
- `test_line_to_claim_refs_link_matching_subject_lines`
- `test_report_job_runs_archive_compiler_optionally`

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-05-implementation-critic.md` after implementation.
