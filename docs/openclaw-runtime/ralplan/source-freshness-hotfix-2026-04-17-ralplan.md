# RALPLAN Hotfix: Source Freshness / Repeated Reuters Loop

Status: approved_for_implementation
Go for implementation: true

## Problem

Reports such as R935E repeatedly elevate BNO/Hormuz based on old Reuters sources from 2026-04-16 / 2026-04-15. The follow-up correctly reveals the source age, but the report hot path failed earlier: it let stale narrative sources keep driving opportunities.

## Root Cause

1. `finance_discord_report_job.py` did not refresh `source-atoms/latest-report.json`, `claim-graph.json`, or `context-gaps.json` before undercurrent/campaign/report rendering.
2. `finance_worker.py` wrote only `source-atoms/latest.jsonl`, leaving the JSON report stale.
3. `opportunity_queue_builder.py` used observation `ts` as freshness and did not score source refs by actual URL/source timestamp. Old Reuters URLs could be rewrapped in fresh observations and keep high scores.

## Plan

- Refresh source atom report, claim graph, and context gaps in the deterministic report job before context pack/rendering.
- Make finance_worker write `source-atoms/latest-report.json` alongside JSONL.
- Add source freshness metadata and penalty to OpportunityQueue.
- Sort opportunities by source-adjusted score.
- Add tests to prevent stale external sources from outranking fresh state evidence.

## Acceptance

- Old external URLs lower opportunity score even if observation `ts` is recent.
- Fresh state market evidence can outrank stale narrative evidence.
- Report job refreshes atom report -> claim graph -> context gaps before undercurrent/campaign/render.
- Existing tests pass.

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-freshness-hotfix-2026-04-17-critic.md`.
