#!/usr/bin/env python3
"""Evaluate whether TradingAgents can run in the current local runtime."""
from __future__ import annotations

import importlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from tradingagents_bridge_types import TRADINGAGENTS_STATE, now_iso, write_json
from tradingagents_model_resolution import resolve_tradingagents_role


OUT = TRADINGAGENTS_STATE / 'runtime-readiness.json'

PROVIDER_MODULES = {
    'openai': ['langchain_openai', 'openai'],
    'google': ['langchain_google_genai', 'google.genai'],
    'anthropic': ['langchain_anthropic', 'anthropic'],
    'openrouter': ['langchain_openai', 'openai'],
}

COMMON_MODULES = [
    'tradingagents',
    'langgraph',
    'langchain_core',
    'pandas',
    'parsel',
    'questionary',
    'rank_bm25',
    'stockstats',
    'yfinance',
    'backtrader',
]


def _module_available(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def evaluate_runtime_readiness(job_name: str = 'finance-tradingagents-sidecar') -> dict[str, Any]:
    resolved = resolve_tradingagents_role(job_name=job_name)
    errors: list[str] = []
    warnings: list[str] = []

    if resolved.get('status') != 'supported':
        errors.append(str(resolved.get('unsupported_reason') or 'model_resolution_failed'))
        provider = None
        auth_source = None
        required_modules: list[str] = []
    else:
        provider = str(resolved.get('provider') or '')
        auth_source = str(resolved.get('auth_source') or '')
        required_modules = list(COMMON_MODULES) + list(PROVIDER_MODULES.get(provider, []))

    missing_modules = [name for name in required_modules if not _module_available(name)]
    if missing_modules:
        errors.append('missing_modules:' + ','.join(missing_modules))

    auth_present = bool(auth_source) and auth_source != 'none' and bool(os.environ.get(auth_source or ''))
    if auth_source and auth_source != 'none' and not auth_present:
        errors.append(f'missing_auth_source:{auth_source}')

    py_version = platform.python_version()
    py_major = sys.version_info.major
    py_minor = sys.version_info.minor
    if py_major >= 3 and py_minor >= 14:
        warnings.append('python_3_14_plus_langchain_compat_warning')

    report = {
        'generated_at': now_iso(),
        'status': 'pass' if not errors else 'fail',
        'job_name': job_name,
        'resolution': resolved,
        'provider': provider,
        'auth_source': auth_source,
        'auth_present': auth_present,
        'python_version': py_version,
        'required_modules': required_modules,
        'missing_modules': missing_modules,
        'errors': errors,
        'warnings': warnings,
        'review_only': True,
        'no_execution': True,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    report = evaluate_runtime_readiness()
    write_json(OUT, report)
    print(json.dumps({'status': report['status'], 'errors': report['errors'], 'out': str(OUT)}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
