# GitHub Reviewer Visibility Plan

GitHub-hosted runners cannot see the local OpenClaw runtime under `~/.openclaw`, so runtime visibility must be pushed from the machine that runs OpenClaw.

The mechanism in this repository is:

1. `tools/export_openclaw_runtime_snapshot.py` exports sanitized runtime facts into `docs/openclaw-runtime/`.
2. `tools/export_parent_dependency_inventory.py` exports the parent market-ingest dependency hash inventory.
3. `tools/review_runtime_gaps.py` exports current unresolved runtime gaps: watchlist freshness, recent report usefulness, wake/threshold bridge status, and benchmark boundary status.
4. `tools/sync_reviewer_snapshot.sh` refreshes these snapshots, commits changed snapshot files, and pushes when a remote is configured.
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
