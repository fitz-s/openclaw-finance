# GitHub Reviewer Visibility Plan

GitHub-hosted runners cannot see the local OpenClaw runtime under `~/.openclaw`, so runtime visibility must be pushed from the machine that runs OpenClaw.

The mechanism in this repository is:

1. `tools/export_openclaw_runtime_snapshot.py` exports sanitized runtime facts into `docs/openclaw-runtime/`.
2. `tools/export_parent_dependency_inventory.py` exports the parent market-ingest dependency hash inventory.
3. `tools/export_wake_threshold_attribution.py` exports the latest wake-vs-threshold attribution.
4. `tools/score_report_usefulness.py` exports report usefulness/noise scoring.
5. `tools/drill_ibkr_watchlist_freshness.py` exports the IBKR watchlist freshness drill result.
6. `tools/audit_parent_dependency_drift.py` compares parent dependency hashes against the committed snapshot.
7. `tools/audit_benchmark_boundary.py` verifies benchmark ideas remain bounded to OpenClaw-compatible patterns.
8. `tools/review_runtime_gaps.py` exports the roll-up unresolved gap register.
9. `tools/sync_reviewer_snapshot.sh` refreshes these snapshots, commits changed snapshot files, and pushes when a remote is configured.
3. GitHub reviewers inspect ordinary diffs to see changes in cron jobs, model roles, OpenClaw contracts, and crontab wiring.

Recommended local OpenClaw/system cron after the GitHub remote is configured:

```cron
15 8,16 * * 1-5 cd /Users/leofitz/.openclaw/workspace/finance && /bin/bash tools/sync_reviewer_snapshot.sh >> /Users/leofitz/.openclaw/logs/finance-github-snapshot-sync.log 2>&1
```

Recommended review workflow:

- Protect the default branch.
- Let the local sync script push to a `runtime-snapshot` branch or directly create small snapshot commits.
- Require GitHub reviewers to review changes under `docs/openclaw-runtime/` together with source changes.
- Use `.github/workflows/validate.yml` to verify committed JSON snapshots parse and core Python sources compile.

This keeps reviewers aware that the repository is an OpenClaw-embedded subsystem and that runtime truth spans the finance repo plus external OpenClaw cron/config surfaces.
