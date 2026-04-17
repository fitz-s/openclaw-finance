# RALPLAN Source-to-Campaign Phase 11: Reviewer Packet Exact Replay

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Upgrade sanitized reviewer packets to consume Phase 05 report-time archives when available, so new reports can be reviewed against exact report-time source health, atoms, claims, gaps, campaign board, options IV surface, and line-to-claim refs.

## Principles

1. Reviewer packets must prefer report-time archive over current snapshot.
2. Legacy reports without archive must remain explicitly marked non-replayable.
3. Sanitization remains mandatory; raw snippets and Discord conversations stay out.
4. Line-to-claim refs are exposed as coverage metadata, not perfect truth.

## Decision Drivers

1. The review flagged current sanitized snapshot as insufficient for exact replay.
2. Phase 05 now writes report-time archive manifests.
3. Remote reviewers need to see which reports are exactly replayable.

## Selected Plan

- Add archive manifest lookup to `export_reviewer_report_packets.py`.
- Use archived envelope for operator surface where available.
- Use archived source health/atoms/claims/gaps/options IV for information acquisition snapshot.
- Add `report_time_replay` section to each packet.
- Preserve legacy fallback behavior.

## Acceptance Criteria

- Packet for archived report has `exact_replay_available=true`.
- Packet for legacy report has `exact_replay_available=false` and clear reason.
- Sanitizer still excludes raw snippets/thread ids/account ids.
- Index exposes exact replay availability.

## Test Plan

- `test_exporter_uses_report_archive_for_exact_replay_when_available`
- existing reviewer packet sanitizer tests

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-11-implementation-critic.md` after implementation.
