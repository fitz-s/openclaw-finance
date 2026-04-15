#!/usr/bin/env python3
"""Check finance repo contracts do not drift back to the legacy renderer model."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs' / 'openclaw-runtime' / 'operating-model-audit.json'

MUST_CONTAIN = {
    ROOT / 'docs' / 'openclaw-runtime' / 'contracts' / 'finance-openclaw-runtime-contract.md': [
        'typed EvidenceRecord / ContextPacket / WakeDecision',
        'JudgmentEnvelope',
        'finance_decision_report_render.py',
        'finance_report_product_validator.py',
        'finance_decision_log_compiler.py',
        'finance_report_delivery_safety.py',
        'Compatibility Surfaces',
    ],
    ROOT / 'docs' / 'openclaw-runtime' / 'contracts' / 'finance-report-contract.md': [
        'ContextPacket',
        'WakeDecision',
        'JudgmentEnvelope',
        'finance-decision-report-envelope.json',
        'compatibility mirror',
    ],
    ROOT / 'docs' / 'openclaw-runtime' / 'contracts' / 'finance-gate-taxonomy.md': [
        'Market Candidate Gate',
        'Wake / Dispatch Gate',
        'Judgment Gate',
        'Product Report Gate',
        'Decision Log / Delivery Safety Gate',
    ],
    ROOT / 'docs' / 'operating-model.md': [
        'Authority Order',
        'Benchmark Boundary',
        'Review-Only Safety',
    ],
}

BANNED_ACTIVE_CLAIMS = {
    ROOT / 'docs' / 'openclaw-runtime' / 'contracts' / 'finance-openclaw-runtime-contract.md': [
        r'OpenClaw report orchestrator cron\s*->\s*finance_report_packet\.py',
        r'finance_deterministic_report_render\.py\s*->\s*finance_report_validator\.py\s*->\s*validated ReportEnvelope',
    ],
    ROOT / 'docs' / 'openclaw-runtime' / 'contracts' / 'finance-report-contract.md': [
        r'only report cognition substrate',
        r'reports must be rendered from `finance/state/report-input-packet\.json`',
    ],
    ROOT / 'docs' / 'openclaw-runtime' / 'contracts' / 'finance-gate-taxonomy.md': [
        r'finance-report-validation\.json.*active',
        r'native_premarket_brief_live\.py.*preflight.*Purpose',
    ],
}


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8') if path.exists() else ''


def build_report() -> dict:
    checks: dict[str, bool] = {}
    errors: list[dict[str, str]] = []
    for path, tokens in MUST_CONTAIN.items():
        text = read(path)
        checks[f'{path.name}:exists'] = path.exists()
        if not path.exists():
            errors.append({'code': f'{path.name}:missing', 'message': str(path)})
            continue
        for token in tokens:
            key = f'{path.name}:contains:{token[:32]}'
            ok = token in text
            checks[key] = ok
            if not ok:
                errors.append({'code': key, 'message': f'missing token {token!r} in {path}'})
    for path, patterns in BANNED_ACTIVE_CLAIMS.items():
        text = read(path)
        for idx, pattern in enumerate(patterns, start=1):
            key = f'{path.name}:banned-active-claim:{idx}'
            ok = re.search(pattern, text, flags=re.I | re.S) is None
            checks[key] = ok
            if not ok:
                errors.append({'code': key, 'message': f'banned active-claim pattern {pattern!r} in {path}'})
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pass' if not errors else 'fail',
        'check_count': len(checks),
        'error_count': len(errors),
        'checks': checks,
        'errors': errors,
    }


def main() -> int:
    report = build_report()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'error_count': report['error_count'], 'out': str(REPORT)}, ensure_ascii=False))
    return 0 if not report['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
