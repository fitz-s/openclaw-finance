#!/usr/bin/env python3
"""Score delivered finance reports for usefulness and noise."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINANCE = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = FINANCE.parents[1]
STATE = FINANCE / 'state'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'report-usefulness-score.json'
HISTORY = STATE / 'report-usefulness-history.jsonl'
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


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def runs(limit: int = 12) -> list[dict[str, Any]]:
    path = OPENCLAW_HOME / 'cron' / 'runs' / f'{REPORT_JOB_ID}.jsonl'
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines()[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def tail_jsonl(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines()[-limit * 2:]:
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows[-limit:]


def score_text(text: str) -> dict[str, Any]:
    noise = [token for token in NOISE_TOKENS if token in text]
    has_opportunity_first = '报告主轴：先找非持仓/非 watchlist' in text
    has_next_step = '## 下一步观察' in text or '下一步' in text
    has_holdings = '## 持仓影响' in text
    line_count = len(text.splitlines())
    score = 100
    score -= min(len(noise) * 12, 60)
    score += 15 if has_opportunity_first else -20
    score += 10 if has_next_step else -10
    score -= 5 if has_holdings and not has_opportunity_first else 0
    score -= 10 if line_count > 70 else 0
    return {
        'score': max(0, min(100, score)),
        'noise_tokens': noise,
        'line_count': line_count,
        'char_count': len(text),
        'has_opportunity_first_contract': has_opportunity_first,
        'has_next_step': has_next_step,
        'has_holding_section': has_holdings,
    }


def main() -> int:
    delivered = [run for run in runs() if run.get('delivered') is True or run.get('deliveryStatus') == 'delivered']
    recent = []
    for run in delivered[-5:]:
        recent.append({
            'runAtMs': run.get('runAtMs'),
            'durationMs': run.get('durationMs'),
            'deliveryStatus': run.get('deliveryStatus'),
            'quality': score_text(str(run.get('summary') or '')),
        })
    latest = load_json(STATE / 'finance-decision-report-envelope.json', {}) or {}
    latest_quality = score_text(str(latest.get('markdown') or ''))
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pass' if latest_quality['score'] >= 70 and not latest_quality['noise_tokens'] else 'review',
        'latest_product_report': {
            'generated_at': latest.get('generated_at'),
            'report_hash': latest.get('report_hash'),
            'quality': latest_quality,
        },
        'usefulness_history_recent': tail_jsonl(HISTORY, limit=5),
        'recent_delivered_reports': recent,
        'interpretation': 'Historical delivered reports may include pre-fix noise; latest product report is the current contract sample.',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'latest_score': latest_quality['score'], 'out': str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
