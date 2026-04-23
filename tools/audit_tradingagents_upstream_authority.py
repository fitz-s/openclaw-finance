#!/usr/bin/env python3
"""Audit the pinned TradingAgents tree for execution/broker authority surfaces."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINANCE = Path(__file__).resolve().parents[1]
LOCK = FINANCE / 'ops' / 'tradingagents-upstream-lock.json'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'tradingagents-upstream-authority-audit.json'

DANGEROUS_PATTERNS = {
    'place_order': re.compile(r'\bplace_order\b', re.I),
    'submit_order': re.compile(r'\bsubmit_order\b', re.I),
    'market_order': re.compile(r'\bmarket_order\b', re.I),
    'limit_order': re.compile(r'\blimit_order\b', re.I),
    'execution_adapter': re.compile(r'\bexecution_adapter\b', re.I),
    'paper_trade': re.compile(r'\bpaper_trade\b', re.I),
    'ibapi_import': re.compile(r'^\s*(?:import|from)\s+ibapi\b', re.I | re.M),
    'ib_insync_import': re.compile(r'^\s*(?:import|from)\s+ib_insync\b', re.I | re.M),
    'alpaca_import': re.compile(r'^\s*(?:import|from)\s+alpaca\b', re.I | re.M),
    'ccxt_import': re.compile(r'^\s*(?:import|from)\s+ccxt\b', re.I | re.M),
    'interactivebrokers_import': re.compile(r'^\s*(?:import|from)\s+interactivebrokers\b', re.I | re.M),
}

REVIEW_LANGUAGE_PATTERNS = {
    'final_transaction_proposal': re.compile(r'FINAL TRANSACTION PROPOSAL', re.I),
    'buy_hold_sell_rating': re.compile(r'\bBUY/HOLD/SELL\b|\bBUY\b.*\bSELL\b', re.I),
    'simulated_exchange': re.compile(r'simulated exchange', re.I),
    'generic_execute_prompt': re.compile(r'Execute what you can to make progress', re.I),
}

CONTAINMENT_WARNING_PATTERNS = {
    'relative_results_dir': re.compile(r'"results_dir"\s*:\s*os\.getenv\(\s*"TRADINGAGENTS_RESULTS_DIR"\s*,\s*"\./results"', re.S),
    'package_data_cache_dir': re.compile(r'"data_cache_dir"\s*:\s*os\.path\.join\([^)]*"dataflows/data_cache"', re.S),
}

SCAN_SUFFIXES = {'.py', '.md', '.toml', '.txt', '.yaml', '.yml'}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def iter_scan_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob('*')
        if path.is_file()
        and '.git' not in path.parts
        and path.suffix in SCAN_SUFFIXES
    )


def find_patterns(root: Path, patterns: dict[str, re.Pattern[str]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in iter_scan_files(root):
        text = path.read_text(encoding='utf-8', errors='replace')
        for code, pattern in patterns.items():
            for match in pattern.finditer(text):
                line = text.count('\n', 0, match.start()) + 1
                findings.append({
                    'code': code,
                    'path': str(path.relative_to(root)),
                    'line': line,
                    'preview': text[match.start():match.end()][:160],
                })
    return findings


def build_report(write: bool = False) -> dict[str, Any]:
    lock = load_json(LOCK)
    root = FINANCE / lock['submodule_path']
    errors: list[dict[str, str]] = []
    if not root.exists():
        errors.append({'code': 'submodule_missing', 'message': str(root)})

    dangerous_findings = find_patterns(root, DANGEROUS_PATTERNS) if root.exists() else []
    review_language_findings = find_patterns(root, REVIEW_LANGUAGE_PATTERNS) if root.exists() else []
    containment_warnings = find_patterns(root, CONTAINMENT_WARNING_PATTERNS) if root.exists() else []

    for finding in dangerous_findings:
        errors.append({
            'code': f"dangerous_symbol:{finding['code']}",
            'message': f"{finding['path']}:{finding['line']}",
        })

    report = {
        'generated_at': now_iso(),
        'contract': 'tradingagents-upstream-authority-audit-v1',
        'status': 'pass' if not errors else 'fail',
        'submodule_path': str(root),
        'locked_tag': lock.get('locked_tag'),
        'locked_commit': lock.get('locked_commit'),
        'scan_file_count': len(iter_scan_files(root)) if root.exists() else 0,
        'dangerous_findings': dangerous_findings,
        'review_language_findings': review_language_findings,
        'containment_warnings': containment_warnings,
        'errors': errors,
        'policy': {
            'dangerous_broker_or_order_api_allowed': False,
            'review_language_allowed_only_in_quarantined_raw_or_machine_fields': True,
            'future_runner_must_override_results_and_cache_paths': True,
            'runtime_import_allowed_in_p1': False,
            'no_execution': True,
        },
        'no_execution': True,
    }
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return report


def main() -> int:
    report = build_report(write=True)
    print(json.dumps({'status': report['status'], 'error_count': len(report['errors']), 'out': str(OUT)}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
