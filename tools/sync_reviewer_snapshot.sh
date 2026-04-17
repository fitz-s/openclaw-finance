#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 tools/export_openclaw_runtime_snapshot.py
python3 tools/export_reviewer_report_packets.py --limit 5
python3 tools/audit_operating_model.py
python3 tools/export_parent_dependency_inventory.py
python3 tools/audit_parent_dependency_drift.py
python3 tools/export_wake_threshold_attribution.py
python3 tools/score_report_usefulness.py
python3 tools/drill_ibkr_watchlist_freshness.py
python3 tools/audit_benchmark_boundary.py
python3 tools/review_runtime_gaps.py

git add docs/openclaw-runtime

if git diff --cached --quiet; then
  echo "finance runtime snapshot unchanged"
  exit 0
fi

git commit -m "Refresh OpenClaw finance runtime snapshot

Constraint: GitHub reviewers cannot read local ~/.openclaw runtime directly
Confidence: high
Scope-risk: narrow
Tested: tools/export_openclaw_runtime_snapshot.py"

if git remote get-url origin >/dev/null 2>&1; then
  git push origin HEAD
else
  echo "No origin remote configured; snapshot commit created locally only."
fi
