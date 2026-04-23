#!/usr/bin/env python3
"""Run TradingAgents in an isolated review-only sidecar wrapper."""
from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

from tradingagents_bridge_types import (
    TRADINGAGENTS_RUNTIME_CACHE,
    TRADINGAGENTS_RUNTIME_LOGS,
    TRADINGAGENTS_SUBMODULE,
    clean_instrument,
    ensure_dir,
    ensure_within,
    load_json,
    now_iso,
    redact_payload,
    write_json,
)
from tradingagents_google_runtime import patch_google_runtime, patch_yfinance_dataflow


ALLOWED_ENV_KEYS = {
    'PATH',
    'HOME',
    'LANG',
    'LC_ALL',
    'TMPDIR',
    'OPENAI_API_KEY',
    'ANTHROPIC_API_KEY',
    'GOOGLE_API_KEY',
    'ALPHA_VANTAGE_API_KEY',
}


def sanitize_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    source = base if base is not None else dict(os.environ)
    env = {key: value for key, value in source.items() if key in ALLOWED_ENV_KEYS}
    env['TRADINGAGENTS_RESULTS_DIR'] = str(TRADINGAGENTS_RUNTIME_LOGS)
    env['TRADINGAGENTS_CACHE_DIR'] = str(TRADINGAGENTS_RUNTIME_CACHE)
    return env


def import_ta() -> tuple[type[Any], dict[str, Any]]:
    root = str(TRADINGAGENTS_SUBMODULE)
    if root not in sys.path:
        sys.path.insert(0, root)
    graph = importlib.import_module('tradingagents.graph.trading_graph')
    google_client = importlib.import_module('tradingagents.llm_clients.google_client')
    y_finance = importlib.import_module('tradingagents.dataflows.y_finance')
    config_mod = importlib.import_module('tradingagents.default_config')
    patch_google_runtime(graph, google_client)
    patch_yfinance_dataflow(y_finance)
    return graph.TradingAgentsGraph, copy.deepcopy(config_mod.DEFAULT_CONFIG)


def build_runtime_config(request: dict[str, Any], raw_dir: Path) -> dict[str, Any]:
    ensure_dir(TRADINGAGENTS_RUNTIME_CACHE)
    ensure_dir(TRADINGAGENTS_RUNTIME_LOGS)
    os.environ.update(sanitize_environment())
    _, default_config = import_ta()
    config = copy.deepcopy(default_config)
    config.update(request.get('config', {}) if isinstance(request.get('config'), dict) else {})
    config['project_dir'] = str(TRADINGAGENTS_SUBMODULE / 'tradingagents')
    config['results_dir'] = str(TRADINGAGENTS_RUNTIME_LOGS)
    config['data_cache_dir'] = str(TRADINGAGENTS_RUNTIME_CACHE)
    return config


def json_safe_payload(value: Any) -> Any:
    """Convert LangChain/Pydantic/runtime objects into JSON-safe structures."""
    if isinstance(value, dict):
        return {str(key): json_safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe_payload(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    model_dump = getattr(value, 'model_dump', None)
    if callable(model_dump):
        try:
            return json_safe_payload(model_dump())
        except Exception:
            pass

    to_dict = getattr(value, 'dict', None)
    if callable(to_dict):
        try:
            return json_safe_payload(to_dict())
        except Exception:
            pass

    if hasattr(value, 'content') and hasattr(value, '__class__'):
        try:
            return {
                'message_class': value.__class__.__name__,
                'content': json_safe_payload(getattr(value, 'content')),
            }
        except Exception:
            pass

    return str(value)


def _build_log_ref(raw_dir: Path, instrument: str, analysis_date: str) -> dict[str, Any] | None:
    candidate = raw_dir / 'eval_results' / instrument / 'TradingAgentsStrategy_logs' / f'full_states_log_{analysis_date}.json'
    if not candidate.exists():
        return None
    return {'path': str(candidate), 'exists': True}


def run_request(request: dict[str, Any]) -> dict[str, Any]:
    request_path = Path(str(request.get('request_path') or ''))
    run_root = request_path.parent
    ensure_within(run_root.parent.parent, run_root)
    raw_dir = ensure_dir(run_root / 'raw')
    ensure_dir(run_root / 'local-debug')

    instrument = clean_instrument(request.get('instrument'))
    if not instrument:
        raise ValueError('invalid request instrument')
    analysis_date = str(request.get('analysis_date') or '')
    if not analysis_date:
        raise ValueError('missing analysis_date')

    started_at = now_iso()
    try:
        TradingAgentsGraph, _ = import_ta()
        config = build_runtime_config(request, raw_dir)
        cwd = Path.cwd()
        os.chdir(raw_dir)
        try:
            graph = TradingAgentsGraph(
                selected_analysts=request.get('selected_analysts', ['market', 'social', 'news', 'fundamentals']),
                debug=False,
                config=config,
            )
            final_state, signal = graph.propagate(instrument, analysis_date)
        finally:
            os.chdir(cwd)

        safe_state = json_safe_payload(final_state)
        redacted_state, redaction_report = redact_payload(safe_state)
        redacted_state_path = raw_dir / 'redacted-final-state.json'
        redaction_report_path = raw_dir / 'redaction-report.json'
        write_json(redacted_state_path, redacted_state)
        write_json(redaction_report_path, {
            'generated_at': now_iso(),
            'status': 'pass',
            **redaction_report,
            'review_only': True,
            'no_execution': True,
        })
        log_ref = _build_log_ref(raw_dir, instrument, analysis_date)
        if log_ref:
            write_json(raw_dir / 'full-state-log-ref.json', log_ref)

        artifact = {
            'generated_at': now_iso(),
            'status': 'pass',
            'run_id': request.get('run_id'),
            'instrument': instrument,
            'analysis_date': analysis_date,
            'started_at': started_at,
            'completed_at': now_iso(),
            'signal': str(signal or '').strip().upper() or None,
            'final_state_path': str(redacted_state_path),
            'redaction_report_path': str(redaction_report_path),
            'full_state_log_ref_path': str(raw_dir / 'full-state-log-ref.json') if log_ref else None,
            'runtime_notes': [
                'review_only',
                'no_execution',
                'future runner must use validator-gated surface outputs only',
            ],
            'review_only': True,
            'no_execution': True,
        }
    except Exception as exc:
        artifact = {
            'generated_at': now_iso(),
            'status': 'fail',
            'run_id': request.get('run_id'),
            'instrument': instrument,
            'analysis_date': analysis_date,
            'started_at': started_at,
            'completed_at': now_iso(),
            'error_class': exc.__class__.__name__,
            'error_message': str(exc),
            'traceback_preview': traceback.format_exc(limit=5),
            'review_only': True,
            'no_execution': True,
        }

    write_json(raw_dir / 'run-artifact.json', artifact)
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run TradingAgents sidecar request.')
    parser.add_argument('--request', required=True)
    args = parser.parse_args(argv)

    request = load_json(Path(args.request), {}) or {}
    request['request_path'] = str(args.request)
    artifact = run_request(request)
    print(json.dumps({
        'status': artifact['status'],
        'run_id': artifact.get('run_id'),
        'instrument': artifact.get('instrument'),
        'artifact': str(Path(args.request).parent / 'raw' / 'run-artifact.json'),
    }, ensure_ascii=False))
    return 0 if artifact['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
