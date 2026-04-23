from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import tradingagents_runner as runner


def _request(tmp_path: Path) -> dict:
    run_root = tmp_path / 'state' / 'tradingagents' / 'runs' / 'ta:test'
    run_root.mkdir(parents=True, exist_ok=True)
    request = {
        'run_id': 'ta:test',
        'instrument': 'NVDA',
        'analysis_date': '2026-04-23',
        'selected_analysts': ['market'],
        'config': {'timeout_seconds': 5},
        'request_path': str(run_root / 'request.json'),
    }
    (run_root / 'request.json').write_text(json.dumps(request), encoding='utf-8')
    return request


def test_sanitize_environment_excludes_broker_session_vars() -> None:
    env = runner.sanitize_environment({
        'PATH': '/usr/bin',
        'OPENAI_API_KEY': 'x',
        'IBKR_SESSION': 'secret',
        'ACCOUNT_ID': 'abc',
    })
    assert 'OPENAI_API_KEY' in env
    assert 'PATH' in env
    assert 'IBKR_SESSION' not in env
    assert 'ACCOUNT_ID' not in env
    assert 'TRADINGAGENTS_RESULTS_DIR' in env


def test_run_request_writes_raw_artifacts(monkeypatch, tmp_path: Path) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(runner, 'TRADINGAGENTS_RUNTIME_CACHE', tmp_path / 'runtime' / 'cache')
    monkeypatch.setattr(runner, 'TRADINGAGENTS_RUNTIME_LOGS', tmp_path / 'runtime' / 'logs')

    class FakeGraph:
        def __init__(self, selected_analysts, debug, config):
            self.config = config

        def propagate(self, instrument, analysis_date):
            log_dir = Path('eval_results') / instrument / 'TradingAgentsStrategy_logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / f'full_states_log_{analysis_date}.json').write_text('{}', encoding='utf-8')
            return ({
                'company_of_interest': instrument,
                'trade_date': analysis_date,
                'market_report': 'Durable demand remains strong.',
                'sentiment_report': 'Sentiment is positive but crowded.',
                'news_report': 'Recent commentary remains supportive.',
                'fundamentals_report': 'Margins remain resilient.',
                'investment_debate_state': {'judge_decision': 'Research is supportive.', 'current_response': 'Research is supportive.'},
                'investment_plan': 'Research supports the case.',
                'trader_investment_plan': 'FINAL TRANSACTION PROPOSAL: BUY.',
                'risk_debate_state': {'judge_decision': 'Wait for confirmation.'},
                'final_trade_decision': 'Rating: Overweight. Wait for deterministic validation.'
            }, 'OVERWEIGHT')

    monkeypatch.setattr(runner, 'import_ta', lambda: (FakeGraph, {'project_dir': '.', 'results_dir': '.', 'data_cache_dir': '.'}))
    artifact = runner.run_request(request)

    raw_dir = Path(request['request_path']).parent / 'raw'
    assert artifact['status'] == 'pass'
    assert (raw_dir / 'run-artifact.json').exists()
    assert (raw_dir / 'redacted-final-state.json').exists()
    assert (raw_dir / 'redaction-report.json').exists()
    assert (raw_dir / 'full-state-log-ref.json').exists()
    assert artifact['signal'] == 'OVERWEIGHT'


def test_run_request_handles_import_failure(tmp_path: Path, monkeypatch) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(runner, 'import_ta', lambda: (_ for _ in ()).throw(ModuleNotFoundError('langgraph')))
    artifact = runner.run_request(request)
    assert artifact['status'] == 'fail'
    assert artifact['error_class'] == 'ModuleNotFoundError'
    assert (Path(request['request_path']).parent / 'raw' / 'run-artifact.json').exists()
