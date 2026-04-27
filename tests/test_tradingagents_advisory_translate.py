from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
FIXTURES = ROOT / 'tests' / 'fixtures' / 'tradingagents'
sys.path.insert(0, str(SCRIPTS))

from tradingagents_advisory_translate import translate_run


def test_translate_run_builds_normalized_artifacts(tmp_path: Path) -> None:
    run_root = tmp_path / 'run'
    raw_dir = run_root / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURES / 'final_state.json', raw_dir / 'redacted-final-state.json')
    artifact = json.loads((FIXTURES / 'raw_run_artifact.json').read_text(encoding='utf-8'))
    artifact['final_state_path'] = str(raw_dir / 'redacted-final-state.json')
    (raw_dir / 'run-artifact.json').write_text(json.dumps(artifact), encoding='utf-8')

    result = translate_run(run_root)

    assert result['status'] == 'pass'
    advisory = json.loads((run_root / 'normalized' / 'advisory-decision.json').read_text(encoding='utf-8'))
    assert advisory['instrument'] == 'NVDA'
    assert advisory['hypothetical_rating'] == 'OVERWEIGHT'
    assert advisory['execution_readiness'] == 'disabled'
    assert advisory['review_only'] is True
    assert advisory['no_execution'] is True
    assert all('buy' not in str(item).lower() for item in advisory['why_now_safe'])
    assert all('overweight' not in str(item).lower() for item in advisory['why_not_now_safe'])


def test_translate_run_filters_headers_and_executionish_lines(tmp_path: Path) -> None:
    run_root = tmp_path / 'run'
    raw_dir = run_root / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        'status': 'pass',
        'instrument': 'TSLA',
        'analysis_date': '2026-04-23',
        'signal': 'SELL',
        'final_state_path': str(raw_dir / 'redacted-final-state.json'),
    }
    final_state = {
        'company_of_interest': 'TSLA',
        'trade_date': '2026-04-23',
        'market_report': '# Market Context\n### Executive Summary\nTSLA demand remains under pressure after earnings.',
        'news_report': '# News Analysis Report\nPrepared by: Desk\nMacro narrative remains hostile to auto beta.',
        'sentiment_report': '### Tesla Weekly Analysis Report\nCrowded optimism has reversed quickly.',
        'fundamentals_report': '**Date:** 2026-04-23\nMargins remain under pressure.',
        'investment_debate_state': {'judge_decision': 'The setup remains fragile.'},
        'investment_plan': 'Entry Strategy: Sell the rip toward 390.',
        'risk_debate_state': {
            'judge_decision': 'Executive Summary:**\n* Position Sizing: keep it small.\nStop-loss above 405.\nWait for confirmation from deterministic sources.'
        },
    }
    (raw_dir / 'run-artifact.json').write_text(json.dumps(artifact), encoding='utf-8')
    (raw_dir / 'redacted-final-state.json').write_text(json.dumps(final_state), encoding='utf-8')

    result = translate_run(run_root)

    assert result['status'] == 'pass'
    advisory = json.loads((run_root / 'normalized' / 'advisory-decision.json').read_text(encoding='utf-8'))
    analyst = json.loads((run_root / 'normalized' / 'analyst-bundle.json').read_text(encoding='utf-8'))
    assert analyst['market'] == ['TSLA demand remains under pressure after earnings.']
    assert analyst['news'] == ['Macro narrative remains hostile to auto beta.']
    assert advisory['risk_flags_safe'] == ['Wait for confirmation from deterministic sources.']
