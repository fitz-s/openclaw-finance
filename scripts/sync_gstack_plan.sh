#!/usr/bin/env bash
set -euo pipefail

# Sync the newest Claude Code plan file back into a target gstack design doc.
# Useful when /office-hours is used inside plan mode and downstream gstack skills
# keep reading a stale .gstack file.

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <target-gstack-file> [source-plan-file]"
  echo "Example: $0 .gstack/projects/myproj/design.md"
  exit 1
fi

TARGET="$1"
SOURCE="${2:-}"

if [[ -z "${SOURCE}" ]]; then
  if [[ ! -d ".claude/plans" ]]; then
    echo "Error: .claude/plans not found"
    exit 1
  fi
  SOURCE="$(ls -t .claude/plans/*.md 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "${SOURCE}" ]]; then
  echo "Error: no source plan file found"
  exit 1
fi

if [[ ! -f "${SOURCE}" ]]; then
  echo "Error: source file not found: ${SOURCE}"
  exit 1
fi

mkdir -p "$(dirname "${TARGET}")"
cp "${SOURCE}" "${TARGET}"
echo "Synced:"
echo "  source: ${SOURCE}"
echo "  target: ${TARGET}"
