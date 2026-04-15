#!/usr/bin/env python3
"""Export a sanitized review of current finance runtime gaps."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINANCE = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = FINANCE.parents[1]
STATE = FINANCE / 'state'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'runtime-gap-review.json'
REPORT_JOB_ID = 'b2c3d4e5-f6a7-8901-bcde-f01234567890'

NOISE_TOKENS = [
    'thresholds not met',
    'Native Shadow',
    'confidence: 0.0',
    'thesis_state:',
    'actionability:',
    'Portfolio source status unavailable',
    'Option risk source status stale_source',
    'metadata_only',
    'support-only',
    'packet_hash',
    'judgment_id',
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def read_runs(job_id: str, limit: int = 10) -> list[dict[str, Any]]:
    path = OPENCLAW_HOME / 'cron' / 'runs' / f'{job_id}.jsonl'
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def report_quality(summary: str) -> dict[str, Any]:
    lines = summary.splitlines()
    noise = [token for token in NOISE_TOKENS if token in summary]
    return {
        'line_count': len(lines),
        'char_count': len(summary),
        'has_opportunity_first_contract': '报告主轴：先找非持仓/非 watchlist' in summary,
        'has_unknown_discovery_section': '## 未知探索（非持仓 / 非Watchlist）' in summary,
        'has_holding_section': '## 持仓影响' in summary,
        'noise_tokens': noise,
    }


def recent_report_review() -> dict[str, Any]:
    runs = read_runs(REPORT_JOB_ID, limit=12)
    delivered = [run for run in runs if run.get('delivered') is True or run.get('deliveryStatus') == 'delivered']
    reviewed = []
    for run in delivered[-5:]:
        summary = str(run.get('summary') or '')
        reviewed.append({
            'runAtMs': run.get('runAtMs'),
            'status': run.get('status'),
            'deliveryStatus': run.get('deliveryStatus'),
            'durationMs': run.get('durationMs'),
            'quality': report_quality(summary),
        })
    latest = load_json(STATE / 'finance-decision-report-envelope.json', {})
    latest_markdown = str(latest.get('markdown') or '')
    return {
        'delivered_count_in_recent_window': len(delivered),
        'reviewed_recent_delivered_runs': reviewed,
        'latest_product_report': {
            'generated_at': latest.get('generated_at'),
            'report_hash': latest.get('report_hash'),
            'quality': report_quality(latest_markdown),
        },
        'interpretation': (
            'Recent historical delivered runs still show old-noise patterns until the next delivery. '
            'The latest regenerated product report is the current contract sample.'
        ),
    }


def watchlist_review() -> dict[str, Any]:
    ibkr = load_json(STATE / 'ibkr-watchlists.json', {})
    resolved = load_json(STATE / 'watchlist-resolved.json', {})
    return {
        'ibkr_watchlist_data_status': ibkr.get('data_status'),
        'ibkr_watchlist_fresh': resolved.get('ibkr_watchlist_fresh'),
        'portfolio_fresh': resolved.get('portfolio_fresh'),
        'resolved_data_status': resolved.get('data_status'),
        'resolved_symbol_count': resolved.get('symbol_count'),
        'blocking_reasons': resolved.get('blocking_reasons', []),
        'review': (
            'IBKR Client Portal watchlist sync is best-effort and currently depends on local Client Portal authentication. '
            'Flex holdings and local pinned symbols keep the universe usable when IBKR watchlist fetch is unavailable.'
        ),
    }


def wake_bridge_review() -> dict[str, Any]:
    gate = load_json(STATE / 'report-gate-state.json', {})
    wake = load_json(STATE / 'latest-wake-decision.json', {})
    dispatch = load_json(STATE / 'wake-dispatch-state.json', {})
    bridge = gate.get('legacyThresholdDispatch') if isinstance(gate.get('legacyThresholdDispatch'), dict) else None
    dispatch_history = STATE / 'dispatch-attribution.jsonl'
    thesis_history = STATE / 'thesis-outcomes.jsonl'
    usefulness_history = STATE / 'report-usefulness-history.jsonl'
    return {
        'current_gate': {
            'evaluatedAt': gate.get('evaluatedAt'),
            'window': gate.get('window'),
            'shouldSend': gate.get('shouldSend'),
            'recommendedReportType': gate.get('recommendedReportType'),
            'decisionReason_sanitized': 'present' if gate.get('decisionReason') else None,
        },
        'current_wake': {
            'wake_class': wake.get('wake_class'),
            'wake_reason': wake.get('wake_reason'),
        },
        'current_dispatch': {
            'action': dispatch.get('action'),
            'dispatched': dispatch.get('dispatched'),
            'status': dispatch.get('status'),
        },
        'legacy_threshold_bridge_current': {
            'present': bridge is not None,
            'status': bridge.get('status') if bridge else None,
            'action': bridge.get('action') if bridge else None,
            'dispatched': bridge.get('dispatched') if bridge else None,
        },
        'telemetry_files': {
            'dispatch_attribution_exists': dispatch_history.exists(),
            'thesis_outcomes_exists': thesis_history.exists(),
            'report_usefulness_history_exists': usefulness_history.exists(),
        },
        'measurement_gap': (
            'Telemetry is now persisted locally when the Package 7 writers run. '
            'Historical records before these writers were introduced remain incomplete.'
        ),
    }


def benchmark_decision() -> dict[str, Any]:
    return {
        'status': 'bounded_patterns_only',
        'accepted_pattern_families': [
            'watchlist/portfolio personalization',
            'bounded research sidecar outside hot path',
            'reviewer-visible runtime snapshots',
            'notification discipline and rate limits',
            'replay/eval before model or policy changes',
        ],
        'rejected_wholesale_templates': [
            'linked-account trading/advisory app',
            'standalone financial terminal',
            'multi-agent hot-path trading swarm',
            'chat/code-execution app as active runtime',
        ],
        'next_package_candidate': 'use telemetry to tune report delta density and wake usefulness review, without automatic threshold mutation',
    }


def build_report() -> dict[str, Any]:
    watchlist = watchlist_review()
    reports = recent_report_review()
    wake = wake_bridge_review()
    unresolved = []
    if watchlist['ibkr_watchlist_fresh'] is not True:
        unresolved.append('ibkr_client_portal_watchlist_sync_not_fresh')
    if wake['legacy_threshold_bridge_current']['present']:
        unresolved.append('legacy_threshold_bridge_still_present')
    if any(item['quality']['noise_tokens'] for item in reports['reviewed_recent_delivered_runs'][-3:]):
        unresolved.append('recent_delivered_reports_include_pre-fix_noise')
    unresolved.append('parent_market_ingest_dependency_external_to_repo')
    return {
        'generated_at': now_iso(),
        'status': 'reviewed',
        'unresolved_gaps': sorted(set(unresolved)),
        'watchlist': watchlist,
        'report_usefulness': reports,
        'wake_threshold_bridge': wake,
        'benchmark_absorption': benchmark_decision(),
    }


def main() -> int:
    report = build_report()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'unresolved_gaps': report['unresolved_gaps'], 'out': str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
