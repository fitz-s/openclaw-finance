#!/usr/bin/env python3
"""Evaluate source-to-campaign cutover readiness without mutating runtime."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'source-to-campaign-cutover-gate.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def has_list(payload: dict[str, Any], key: str) -> bool:
    return isinstance(payload.get(key), list) and len(payload[key]) > 0


def latest_archive_exact(state: Path) -> bool:
    archive = state / 'report-archive'
    manifests = sorted(archive.glob('*/manifest.json'), key=lambda p: p.stat().st_mtime, reverse=True) if archive.exists() else []
    if not manifests:
        return False
    manifest = load_json_safe(manifests[0], {}) or {}
    return bool(manifest.get('exact_replay_available'))


def evaluate(state: Path = STATE) -> dict[str, Any]:
    campaign_board = load_json_safe(state / 'campaign-board.json', {}) or {}
    reviewer_index = load_json_safe(FINANCE / 'docs' / 'openclaw-runtime' / 'reviewer-packets' / 'index.json', {}) or {}
    followup_route = load_json_safe(state / 'followup-context-route.json', {}) or {}
    thread_registry = load_json_safe(state / 'finance-discord-followup-threads.json', {}) or {}
    source_roi = load_json_safe(state / 'source-roi-report.json', {}) or {}
    options_iv = load_json_safe(state / 'options-iv-surface.json', {}) or {}
    checks = {
        'campaign_board_has_evidence_lines': 'Evidence：' in str(campaign_board.get('discord_risk_board_markdown') or '') + str(campaign_board.get('discord_live_board_markdown') or '') + str(campaign_board.get('discord_scout_board_markdown') or ''),
        'campaigns_have_lane_coverage': any(isinstance(c, dict) and isinstance(c.get('lane_coverage_summary'), dict) for c in campaign_board.get('campaigns', []) if isinstance(c, dict)),
        'latest_report_archive_exact': latest_archive_exact(state),
        'reviewer_packets_exact_replay_present': any(bool(r.get('exact_replay_available')) for r in reviewer_index.get('reports', []) if isinstance(r, dict)),
        'followup_route_has_coverage': isinstance(followup_route.get('evidence_slice_coverage'), dict),
        'thread_registry_lifecycle_present': thread_registry.get('inactive_after_hours') == 72 or any(isinstance(r, dict) and r.get('inactive_after_hours') == 72 for r in (thread_registry.get('threads') or {}).values()),
        'source_roi_has_campaign_value': any(isinstance(r, dict) and 'campaign_value_score' in r for r in source_roi.get('source_roi_rows', []) if isinstance(r, dict)),
        'options_iv_surface_present': options_iv.get('contract') == 'options-iv-surface-v1-shadow',
    }
    blocking = [key for key, ok in checks.items() if not ok]
    return {
        'generated_at': now_iso(),
        'status': 'ready' if not blocking else 'hold',
        'blocking_reasons': blocking,
        'checks': checks,
        'readiness_is_authority': False,
        'no_execution': True,
        'no_wake_mutation': True,
        'no_delivery_mutation': True,
        'no_threshold_mutation': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Evaluate source-to-campaign cutover readiness.')
    parser.add_argument('--state', default=str(STATE))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    report = evaluate(Path(args.state))
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'blocking_reasons': report['blocking_reasons'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
