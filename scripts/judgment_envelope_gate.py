#!/usr/bin/env python3
"""Gate OpenClaw-produced JudgmentEnvelope candidates before report use."""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


ROOT = Path('/Users/leofitz/.openclaw')
WORKSPACE = ROOT / 'workspace'
FINANCE = WORKSPACE / 'finance'
SERVICE = WORKSPACE / 'services' / 'market-ingest'
VALIDATOR_PATH = SERVICE / 'validator' / 'judgment_validator.py'
PACKET = SERVICE / 'state' / 'latest-context-packet.json'
CANDIDATE = FINANCE / 'state' / 'judgment-envelope-candidate.json'
SELECTED = FINANCE / 'state' / 'judgment-envelope.json'
VALIDATION = FINANCE / 'state' / 'judgment-validation.json'
REPORT = FINANCE / 'state' / 'judgment-envelope-gate-report.json'
POLICY_VERSION = 'finance-semantic-v1'
ADJUDICATION_MODES = {'scheduled_context', 'event_wake', 'ops_escalation', 'auto'}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def safe_finance_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to((FINANCE / 'state').resolve(strict=False))
        return True
    except ValueError:
        return False


def deterministic_no_trade_judgment(packet: dict[str, Any], model_id: str) -> dict[str, Any]:
    support_records = []
    for record in packet.get('accepted_evidence_records', []):
        if (
            isinstance(record, dict)
            and record.get('evidence_id')
            and record.get('quarantine', {}).get('allowed_for_judgment_support') is True
        ):
            support_records.append(record)

    def pct_abs(record: dict[str, Any]) -> float:
        text = str(record.get('normalized_summary') or '')
        import re
        match = re.search(r'([+-]?\d+(?:\.\d+)?)%', text)
        try:
            return abs(float(match.group(1))) if match else 0.0
        except ValueError:
            return 0.0

    def support_rank(record: dict[str, Any]) -> tuple[int, float, str]:
        kind = str(record.get('source_kind') or '')
        layer = str(record.get('layer') or '')
        if kind in {'option_risk_status', 'portfolio_source_status'}:
            return (3, 0.0, str(record.get('evidence_id')))
        if layer == 'L0_raw_observation':
            return (2, pct_abs(record), str(record.get('evidence_id')))
        return (1, float(record.get('source_reliability') or 0), str(record.get('evidence_id')))

    support_records = sorted(support_records, key=support_rank, reverse=True)
    support_refs = [str(record['evidence_id']) for record in support_records]
    evidence_refs = support_refs[:5] or [ref for ref in packet.get('evidence_refs', []) if ref != 'none'][:1] or ['none']
    if support_records:
        why_now = ['本轮有可信本地证据更新 packet，但没有触发 isolated judgment wake。']
        why_not = ['当前没有 wake-eligible 证据；support-only 证据只能约束上下文，不能单独支持交易 thesis。']
        required_confirmations = ['等待 wake-eligible 证据或人工确认的 catalyst 后，再改变 thesis。']
    else:
        why_now = ['当前没有可用于唤醒或判断支持的有效证据。']
        why_not = ['本轮证据均为低权限上下文或数据不可用，不能支持交易 thesis。']
        required_confirmations = ['先完成 source-backed evidence promotion，再进入市场判断。']
    return {
        'judgment_id': f"judgment:{packet.get('packet_id', 'unknown')}:no-trade",
        'packet_id': packet.get('packet_id'),
        'packet_hash': packet.get('packet_hash'),
        'instrument': str(packet.get('instrument') or 'SPY'),
        'thesis_state': 'no_trade',
        'actionability': 'none',
        'confidence': 0.0,
        'why_now': why_now,
        'why_not': why_not,
        'invalidators': packet.get('candidate_invalidators', []),
        'required_confirmations': required_confirmations,
        'evidence_refs': evidence_refs,
        'policy_version': packet.get('policy_version') or POLICY_VERSION,
        'model_id': model_id,
    }


def risk_state_for_mode(mode: str) -> dict[str, Any]:
    if mode == 'event_wake':
        return {
            'max_actionability': 'review',
            'live_authority': False,
            'allowed_thesis_states': ['watch', 'lean_long', 'lean_short', 'no_trade', 'reduce', 'exit'],
        }
    if mode == 'ops_escalation':
        return {
            'max_actionability': 'none',
            'live_authority': False,
            'allowed_thesis_states': ['no_trade'],
        }
    return {
        'max_actionability': 'review',
        'live_authority': False,
        'allowed_thesis_states': ['no_trade', 'watch'],
    }


def gate_candidate(
    *,
    packet_path: Path = PACKET,
    candidate_path: Path = CANDIDATE,
    selected_path: Path = SELECTED,
    validation_path: Path = VALIDATION,
    allow_fallback: bool = False,
    model_id: str = 'openclaw-adjudicator',
    adjudication_mode: str = 'scheduled_context',
) -> dict[str, Any]:
    packet = load_json_safe(packet_path, {}) or {}
    candidate = load_json_safe(candidate_path, {}) or {}
    validator = load_module(VALIDATOR_PATH, 'judgment_gate_validator')
    blocking_reasons: list[str] = []
    selected = None
    selected_source = None

    if not candidate:
        blocking_reasons.append('candidate_judgment_missing')
    else:
        result = validator.validate(candidate, packet, risk_state_for_mode(adjudication_mode))
        atomic_write_json(validation_path, result)
        if result['errors']:
            blocking_reasons.extend(result['errors'])
        else:
            selected = candidate
            selected_source = 'candidate'

    if selected is None and allow_fallback:
        fallback = deterministic_no_trade_judgment(packet, model_id='deterministic-no-trade-fallback')
        result = validator.validate(fallback, packet, risk_state_for_mode(adjudication_mode))
        atomic_write_json(validation_path, result)
        if not result['errors']:
            selected = fallback
            selected_source = 'deterministic_no_trade_fallback'
        else:
            blocking_reasons.extend(result['errors'])

    if selected is not None:
        atomic_write_json(selected_path, selected)

    return {
        'generated_at': now_iso(),
        'status': 'pass' if selected is not None and selected_source == 'candidate' else 'fallback' if selected is not None else 'blocked',
        'blocking_reasons': sorted(set(blocking_reasons)),
        'packet_path': str(packet_path),
        'candidate_path': str(candidate_path),
        'selected_judgment_path': str(selected_path) if selected is not None else None,
        'validation_path': str(validation_path),
        'selected_source': selected_source,
        'packet_hash': packet.get('packet_hash'),
        'model_id': model_id,
        'adjudication_mode': adjudication_mode,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', default=str(PACKET))
    parser.add_argument('--candidate', default=str(CANDIDATE))
    parser.add_argument('--selected', default=str(SELECTED))
    parser.add_argument('--validation', default=str(VALIDATION))
    parser.add_argument('--out', default=str(REPORT))
    parser.add_argument('--allow-fallback', action='store_true')
    parser.add_argument('--model-id', default='openclaw-adjudicator')
    parser.add_argument('--adjudication-mode', default='scheduled_context', choices=sorted(ADJUDICATION_MODES))
    args = parser.parse_args(argv)
    for path in [Path(args.candidate), Path(args.selected), Path(args.validation), Path(args.out)]:
        if not safe_finance_state_path(path):
            print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_finance_state_path']}, ensure_ascii=False))
            return 2
    report = gate_candidate(
        packet_path=Path(args.packet),
        candidate_path=Path(args.candidate),
        selected_path=Path(args.selected),
        validation_path=Path(args.validation),
        allow_fallback=args.allow_fallback,
        model_id=args.model_id,
        adjudication_mode=args.adjudication_mode if args.adjudication_mode != 'auto' else 'scheduled_context',
    )
    atomic_write_json(Path(args.out), report)
    print(json.dumps({'status': report['status'], 'blocking_reasons': report['blocking_reasons'], 'selected_source': report['selected_source'], 'out': str(args.out)}, ensure_ascii=False))
    return 0 if report['status'] in {'pass', 'fallback'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
