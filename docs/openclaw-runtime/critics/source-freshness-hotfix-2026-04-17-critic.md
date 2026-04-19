# Source Freshness Hotfix Critic — 2026-04-17

Verdict: APPROVE

Scope reviewed:
- `scripts/finance_discord_report_job.py`
- `scripts/finance_worker.py`
- `scripts/opportunity_queue_builder.py`
- `tests/test_thesis_spine_reducers.py`
- `tests/test_report_time_archive_phase05.py`

Checks:
- Report job now refreshes source atom report, claim graph, context gaps, and opportunity queue before building report context.
- finance_worker now writes both source atom JSONL and JSON report, preventing stale `latest-report.json` from persisting after new scans.
- OpportunityQueue now scores actual source refs for freshness and penalizes stale external URLs such as dated Reuters links.
- Stale external narrative can no longer outrank fresh state market evidence solely because it was rewrapped in a fresh observation timestamp.
- Changes remain review-only; no wake threshold, Discord delivery, JudgmentEnvelope, or execution authority changed.

Risks:
- URL/date parsing is deterministic but heuristic; vendor-specific published_at metadata remains better and should be preferred when available.
- Fresh `state:` evidence can still be low quality if upstream state is bad; this is mitigated by source health and later cutover gate.

Verification required before commit:
- targeted opportunity/report tests
- full test suite
- compileall
- operating-model and benchmark audits
