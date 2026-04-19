#!/usr/bin/env python3
"""Check finance repo contracts do not drift back to the legacy renderer model."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs' / 'openclaw-runtime' / 'operating-model-audit.json'
PROMPT_CONTRACT = ROOT / 'docs' / 'openclaw-runtime' / 'finance-job-prompt-contract.json'
LEGACY_REPORT_V1_FILES = [
    ('REPORT_TEMPLATE.md', ROOT / 'legacy' / 'report-v1' / 'REPORT_TEMPLATE.md', ROOT / 'REPORT_TEMPLATE.md'),
    ('report-renderer.md', ROOT / 'legacy' / 'report-v1' / 'prompts' / 'report-renderer.md', ROOT / 'prompts' / 'report-renderer.md'),
    ('finance_deterministic_report_render.py', ROOT / 'legacy' / 'report-v1' / 'scripts' / 'finance_deterministic_report_render.py', ROOT / 'scripts' / 'finance_deterministic_report_render.py'),
    ('finance_report_validator.py', ROOT / 'legacy' / 'report-v1' / 'scripts' / 'finance_report_validator.py', ROOT / 'scripts' / 'finance_report_validator.py'),
    ('quality_gate.py', ROOT / 'legacy' / 'report-v1' / 'scripts' / 'quality_gate.py', ROOT / 'scripts' / 'quality_gate.py'),
    ('native_premarket_brief.py', ROOT / 'legacy' / 'report-v1' / 'scripts' / 'native_premarket_brief.py', ROOT / 'scripts' / 'native_premarket_brief.py'),
    ('native_premarket_brief_live.py', ROOT / 'legacy' / 'report-v1' / 'scripts' / 'native_premarket_brief_live.py', ROOT / 'scripts' / 'native_premarket_brief_live.py'),
    ('finance_llm_report_render.py', ROOT / 'legacy' / 'report-v1' / 'scripts' / 'finance_llm_report_render.py', ROOT / 'scripts' / 'finance_llm_report_render.py'),
]
COMPAT_TEMPLATE_MARKERS = [
    'Compatibility Stub',
    'Active finance reporting no longer uses this template',
    'legacy/report-v1/REPORT_TEMPLATE.md',
]

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
    ROOT / 'docs' / 'openclaw-runtime' / 'contracts' / 'thesis-spine-contract.md': [
        'Thesis Spine',
        'WatchIntent',
        'ThesisCard',
        'ScenarioCard',
        'OpportunityQueue',
        'InvalidatorLedger',
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
    prompt_contract = {}
    try:
        prompt_contract = json.loads(PROMPT_CONTRACT.read_text(encoding='utf-8'))
    except Exception:
        prompt_contract = {}
    jobs = prompt_contract.get('jobs') if isinstance(prompt_contract.get('jobs'), dict) else {}
    prompt_expectations = {
        'finance-premarket-brief': [
            'contains_deterministic_report_job',
            'runs_finance_discord_report_job',
            'forbids_progress_text',
        ],
        'finance-subagent-scanner': ['contains_context_pack', 'contains_non_authority_boundary', 'contains_unknown_discovery_contract'],
        'finance-subagent-scanner-offhours': ['contains_context_pack', 'contains_non_authority_boundary', 'contains_unknown_discovery_contract'],
        'finance-weekly-learning-review': ['contains_context_pack', 'contains_non_authority_boundary', 'contains_threshold_mutation_ban'],
        'finance-thesis-sidecar': ['contains_context_pack', 'contains_non_authority_boundary', 'contains_threshold_mutation_ban'],
    }
    for job_name, fields in prompt_expectations.items():
        job = jobs.get(job_name) if isinstance(jobs.get(job_name), dict) else {}
        for field in fields:
            key = f'prompt:{job_name}:{field}'
            ok = job.get(field) is True
            checks[key] = ok
            if not ok:
                errors.append({'code': key, 'message': f'prompt contract missing {field} for {job_name}'})
    sidecar = jobs.get('finance-thesis-sidecar') if isinstance(jobs.get('finance-thesis-sidecar'), dict) else {}
    sidecar_delivery = sidecar.get('delivery') if isinstance(sidecar.get('delivery'), dict) else {}
    key = 'prompt:finance-thesis-sidecar:delivery-none-disabled'
    ok = sidecar.get('enabled') is False and sidecar_delivery.get('mode') == 'none'
    checks[key] = ok
    if not ok:
        errors.append({'code': key, 'message': 'finance-thesis-sidecar must remain disabled/manual and delivery none'})
    for label, legacy_path, root_path in LEGACY_REPORT_V1_FILES:
        key = f'legacy-report-v1:{label}:quarantined'
        root_compat_ok = False
        if label == 'REPORT_TEMPLATE.md' and root_path.exists():
            root_text = root_path.read_text(encoding='utf-8', errors='replace')
            root_compat_ok = all(marker in root_text for marker in COMPAT_TEMPLATE_MARKERS)
        ok = legacy_path.exists() and (not root_path.exists() or root_compat_ok)
        checks[key] = ok
        if not ok:
            errors.append({
                'code': key,
                'message': f'{label} must live under legacy/report-v1; root path may only contain a compatibility stub',
            })
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
