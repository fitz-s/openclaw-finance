#!/usr/bin/env python3
"""Run bounded capital committee sidecar for role-decomposed assessment."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, load, now_iso, stable_id, write


SCRIPTS = FINANCE / 'scripts'
COMMITTEE_PACKET = FINANCE / 'state' / 'capital-committee-packet.json'
MEMO_DIR = FINANCE / 'state' / 'committee-memos'
REPORT = FINANCE / 'state' / 'capital-committee-sidecar-report.json'

COMMITTEE_ROLES = ['thesis_analyst', 'countercase', 'portfolio_risk', 'macro_scenario', 'options_structure']

COMPILATION_STEPS = [
    'capital_graph_compiler.py',
    'scenario_exposure_compiler.py',
    'displacement_case_builder.py',
    'capital_agenda_compiler.py',
    'capital_committee_packet.py',
]


def run_step(script: str) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, str(SCRIPTS / script)], capture_output=True, text=True, timeout=60)
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except Exception:
        payload = {'stdout_preview': proc.stdout.strip()[:500]}
    payload['script'] = script
    payload['returncode'] = proc.returncode
    if proc.stderr.strip():
        payload['stderr_preview'] = proc.stderr.strip()[:500]
    return payload


def generate_role_memo(role: str, agenda_item: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    """Generate a deterministic typed memo for one role on one agenda item.

    In the full system, this would delegate to a bounded LLM sidecar per role.
    For now, it produces a deterministic skeleton memo from available state.
    """
    return {
        'memo_id': stable_id('memo', role, agenda_item.get('agenda_id')),
        'role': role,
        'agenda_item_ref': agenda_item.get('agenda_id'),
        'agenda_type': agenda_item.get('agenda_type'),
        'assessment': {
            'summary': f'{role} review of {agenda_item.get("agenda_type")} pending',
            'supporting_evidence_refs': [],
            'contradicting_evidence_refs': [],
            'key_risk': 'pending role-specific assessment',
            'key_opportunity': 'pending role-specific assessment',
            'recommendation': 'review',
        },
        'risk_flags': [],
        'confidence': 'insufficient_data',
        'required_questions': agenda_item.get('required_questions', [])[:3],
        'generated_at': now_iso(),
        'forbidden_actions': [
            'no_user_delivery',
            'no_execution',
            'no_threshold_mutation',
            'no_live_authority_change',
        ],
    }


def main() -> int:
    results = []
    ok = True

    # Run compilation steps
    for script in COMPILATION_STEPS:
        result = run_step(script)
        results.append(result)
        if result.get('returncode') != 0:
            ok = False
            break

    memos: list[dict[str, Any]] = []
    if ok:
        MEMO_DIR.mkdir(parents=True, exist_ok=True)
        packet = load(COMMITTEE_PACKET, {}) or {}
        agenda_items = packet.get('selected_agenda_items', [])

        for item in agenda_items[:5]:
            if not isinstance(item, dict):
                continue
            for role in COMMITTEE_ROLES:
                memo = generate_role_memo(role, item, packet)
                memos.append(memo)
                memo_file = f"{role}-{str(item.get('agenda_id', 'unknown')).replace(':', '-')}.json"
                write(MEMO_DIR / memo_file, memo)

    report = {
        'generated_at': now_iso(),
        'status': 'pass' if ok else 'fail',
        'sidecar_scope': 'bounded_capital_committee_only',
        'memo_count': len(memos),
        'agenda_items_reviewed': len(set(m.get('agenda_item_ref') for m in memos)),
        'roles_active': COMMITTEE_ROLES,
        'steps': results,
        'forbidden_actions': ['no_user_delivery', 'no_execution', 'no_threshold_mutation', 'no_live_authority_change'],
    }
    write(REPORT, report)
    print(json.dumps({'status': report['status'], 'memo_count': len(memos), 'out': str(REPORT)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
