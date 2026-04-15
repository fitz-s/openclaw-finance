#!/usr/bin/env python3
"""Run bounded Thesis Spine research sidecar without user-visible delivery."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, load, now_iso, write


SCRIPTS = FINANCE / 'scripts'
RESEARCH_PACKET = FINANCE / 'state' / 'thesis-research-packet.json'
CUSTOM_METRICS = FINANCE / 'state' / 'custom-metrics' / 'thesis-spine-metrics.json'
SCENARIO_CARDS = FINANCE / 'state' / 'scenario-cards.json'
DOSSIER_DIR = FINANCE / 'state' / 'thesis-dossiers'
REPORT = FINANCE / 'state' / 'thesis-research-sidecar-report.json'
STEPS = [
    'thesis_research_packet.py',
    'custom_metric_compiler.py',
    'scenario_card_builder.py',
    'capital_graph_compiler.py',
    'scenario_exposure_compiler.py',
    'displacement_case_builder.py',
    'capital_agenda_compiler.py',
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


def compile_dossiers(research_packet: dict[str, Any], custom_metrics: dict[str, Any], scenario_cards: dict[str, Any]) -> list[dict[str, Any]]:
    metrics_by_target = {
        item.get('target_id'): item
        for item in custom_metrics.get('metrics', [])
        if isinstance(item, dict) and item.get('target_id')
    }
    scenarios = [
        item for item in scenario_cards.get('scenarios', [])
        if isinstance(item, dict)
    ]
    dossiers = []
    for item in research_packet.get('selected_opportunities', []):
        if not isinstance(item, dict) or not item.get('candidate_id'):
            continue
        dossier = {
            'generated_at': now_iso(),
            'dossier_id': f"dossier:{item['candidate_id']}",
            'target_type': 'opportunity',
            'target_id': item['candidate_id'],
            'instrument': item.get('instrument'),
            'theme': item.get('theme'),
            'status': item.get('status'),
            'promotion_reason': item.get('promotion_reason'),
            'metric_ref': metrics_by_target.get(item['candidate_id'], {}),
            'scenario_refs': [scenario.get('scenario_id') for scenario in scenarios if scenario.get('title') == item.get('theme')],
            'review_only': True,
            'forbidden_actions': research_packet.get('forbidden_actions', []),
        }
        dossiers.append(dossier)
    for item in research_packet.get('selected_theses', []):
        if not isinstance(item, dict) or not item.get('thesis_id'):
            continue
        dossier = {
            'generated_at': now_iso(),
            'dossier_id': f"dossier:{item['thesis_id']}",
            'target_type': 'thesis',
            'target_id': item['thesis_id'],
            'instrument': item.get('instrument'),
            'status': item.get('status'),
            'maturity': item.get('maturity'),
            'metric_ref': metrics_by_target.get(item['thesis_id'], {}),
            'scenario_refs': item.get('scenario_refs', []),
            'review_only': True,
            'forbidden_actions': research_packet.get('forbidden_actions', []),
        }
        dossiers.append(dossier)
    return dossiers


def main() -> int:
    results = []
    ok = True
    for script in STEPS:
        result = run_step(script)
        results.append(result)
        if result.get('returncode') != 0:
            ok = False
            break

    dossiers: list[dict[str, Any]] = []
    if ok:
        DOSSIER_DIR.mkdir(parents=True, exist_ok=True)
        dossiers = compile_dossiers(
            load(RESEARCH_PACKET, {}) or {},
            load(CUSTOM_METRICS, {}) or {},
            load(SCENARIO_CARDS, {}) or {},
        )
        for dossier in dossiers:
            target_id = str(dossier.get('target_id') or 'unknown').replace(':', '-')
            write(DOSSIER_DIR / f'{target_id}.json', dossier)

    report = {
        'generated_at': now_iso(),
        'status': 'pass' if ok else 'fail',
        'sidecar_scope': 'bounded_research_artifacts_only',
        'dossier_count': len(dossiers),
        'steps': results,
        'forbidden_actions': ['no_user_delivery', 'no_execution', 'no_threshold_mutation', 'no_live_authority_change'],
    }
    write(REPORT, report)
    print(json.dumps({'status': report['status'], 'dossier_count': len(dossiers), 'out': str(REPORT)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
