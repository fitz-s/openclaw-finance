from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from report_usefulness_history import build_row as report_usefulness_row
from thesis_outcome_tracker import build_rows as thesis_outcome_rows
from wake_attribution_logger import append_unique, build_row as wake_attribution_row


def test_wake_attribution_row_is_audit_only() -> None:
    row = wake_attribution_row(
        {'evaluatedAt': '2026-04-01T10:00:00Z', 'window': 'mid', 'shouldSend': True, 'recommendedReportType': 'core'},
        {'packet_id': 'packet:a', 'wake_class': 'PACKET_UPDATE_ONLY', 'wake_reason': 'context update', 'score_inputs': {'wake_score': 0.4}},
        {'action': 'packet_update_only', 'status': 'stored'},
        {'entry': {'decision_id': 'decision:a', 'execution_decision': 'none', 'operator_action': 'logged_no_trade', 'thesis_refs': ['thesis:a']}},
    )

    assert row['threshold_should_send'] is True
    assert row['wake_class'] == 'PACKET_UPDATE_ONLY'
    assert row['execution_decision'] == 'none'
    assert 'threshold_mutation' not in row


def test_thesis_outcomes_bind_decision_to_thesis_refs() -> None:
    rows = thesis_outcome_rows(
        {'theses': [{'thesis_id': 'thesis:a', 'instrument': 'AAPL', 'status': 'watch', 'maturity': 'seed'}]},
        {'entry': {'decision_id': 'decision:a', 'execution_decision': 'none', 'operator_action': 'logged_no_trade', 'thesis_refs': ['thesis:a']}},
        {'status': 'pass'},
    )

    assert len(rows) == 1
    assert rows[0]['thesis_id'] == 'thesis:a'
    assert rows[0]['outcome_scope'] == 'review_only_decision_support'
    assert rows[0]['product_validation_status'] == 'pass'


def test_report_usefulness_history_scores_delta_density() -> None:
    report = {
        'report_hash': 'sha256:a',
        'generated_at': '2026-04-01T10:00:00Z',
        'renderer_id': 'thesis-delta-deterministic-v1',
        'thesis_refs': ['thesis:a'],
        'opportunity_candidate_refs': ['opportunity:a'],
        'invalidator_refs': ['invalidator:a'],
        'markdown': '\n'.join([
            'Finance｜决策报告',
            '## 结论',
            '- 报告主轴：先找非持仓/非 watchlist 的机会拓展',
            '## 下一步观察',
            '- 等待确认：价格/成交量继续确认',
        ]),
    }
    row = report_usefulness_row(report, {'status': 'pass'}, {'status': 'pass', 'blocking_reasons': []})

    assert row['report_renderer'] == 'thesis-delta-deterministic-v1'
    assert row['usefulness_score'] >= 80
    assert row['delta_density'] > 0
    assert row['thesis_ref_count'] == 1


def test_append_unique_prevents_duplicate_event_ids(tmp_path: Path) -> None:
    out = tmp_path / 'events.jsonl'
    row = {'event_id': 'event:a', 'value': 1}

    assert append_unique(out, row) is True
    assert append_unique(out, row) is False
    assert len(out.read_text().splitlines()) == 1
    assert json.loads(out.read_text()) == row
