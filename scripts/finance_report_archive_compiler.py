#!/usr/bin/env python3
"""Archive report-time finance artifacts for exact local replay.

The archive lives under state/report-archive and is intentionally ignored by git.
Reviewer packets may later derive sanitized views from these artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
WORKSPACE = FINANCE.parent
STATE = FINANCE / 'state'
DEFAULT_OUT_ROOT = STATE / 'report-archive'
ENVELOPE = STATE / 'finance-decision-report-envelope.json'
READER_DIR = STATE / 'report-reader'
SOURCE_ATOMS_REPORT = STATE / 'source-atoms' / 'latest-report.json'
CLAIM_GRAPH = STATE / 'claim-graph.json'
CONTEXT_GAPS = STATE / 'context-gaps.json'
SOURCE_HEALTH = WORKSPACE / 'services' / 'market-ingest' / 'state' / 'source-health.json'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
OPTIONS_IV_SURFACE = STATE / 'options-iv-surface.json'
CONTRACT = 'report-time-archive-v1'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def safe_state_dir(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def copy_artifact(src: Path, dest_dir: Path, name: str) -> dict[str, Any]:
    if not src.exists():
        return {'name': name, 'available': False, 'source': str(src)}
    dest = dest_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {
        'name': name,
        'available': True,
        'source': str(src),
        'path': str(dest),
        'sha256': file_hash(dest),
        'bytes': dest.stat().st_size,
    }


def text_lines(*values: Any) -> list[str]:
    lines: list[str] = []
    for value in values:
        text = str(value or '').strip()
        if not text:
            continue
        lines.extend(text.splitlines())
    return lines


def build_line_to_claim_refs(envelope: dict[str, Any], claim_graph: dict[str, Any]) -> dict[str, Any]:
    claims = [claim for claim in claim_graph.get('claims', []) if isinstance(claim, dict)]
    lines = text_lines(
        envelope.get('discord_primary_markdown'),
        envelope.get('discord_live_board_markdown'),
        envelope.get('discord_scout_board_markdown'),
        envelope.get('discord_risk_board_markdown'),
        envelope.get('markdown'),
    )
    refs: list[dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        clean = ' '.join(line.split())
        if not clean:
            continue
        matched: list[str] = []
        for claim in claims:
            subject = str(claim.get('subject') or '').strip()
            if subject and subject.lower() in clean.lower():
                matched.append(str(claim.get('claim_id')))
        if matched:
            refs.append({
                'line_no': idx,
                'line_preview': clean[:240],
                'claim_ids': sorted(set(matched)),
                'match_method': 'heuristic_subject_match',
            })
    return {
        'generated_at': now_iso(),
        'contract': 'line-to-claim-refs-v1-heuristic',
        'line_count': len(lines),
        'matched_line_count': len(refs),
        'refs': refs,
        'coverage_note': 'Heuristic subject matching only; future phases should produce explicit line-to-claim bindings during rendering.',
        'no_execution': True,
    }


def archive_report(*, out_root: Path = DEFAULT_OUT_ROOT, envelope_path: Path = ENVELOPE) -> dict[str, Any]:
    if not safe_state_dir(out_root):
        return {'status': 'blocked', 'blocking_reasons': ['unsafe_out_root'], 'out_root': str(out_root)}
    envelope = load_json_safe(envelope_path, {}) or {}
    report_id = str(envelope.get('report_id') or '').strip()
    if not report_id:
        return {'status': 'blocked', 'blocking_reasons': ['missing_report_id'], 'envelope': str(envelope_path)}
    dest_dir = out_root / report_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    reader_bundle = READER_DIR / f'{report_id}.json'
    artifacts = {
        'envelope': copy_artifact(envelope_path, dest_dir, 'envelope.json'),
        'reader_bundle': copy_artifact(reader_bundle, dest_dir, 'reader-bundle.json'),
        'source_atoms': copy_artifact(SOURCE_ATOMS_REPORT, dest_dir, 'source-atoms.json'),
        'claim_graph': copy_artifact(CLAIM_GRAPH, dest_dir, 'claim-graph.json'),
        'context_gaps': copy_artifact(CONTEXT_GAPS, dest_dir, 'context-gaps.json'),
        'source_health': copy_artifact(SOURCE_HEALTH, dest_dir, 'source-health.json'),
        'campaign_board': copy_artifact(CAMPAIGN_BOARD, dest_dir, 'campaign-board.json'),
        'options_iv_surface': copy_artifact(OPTIONS_IV_SURFACE, dest_dir, 'options-iv-surface.json'),
    }
    claim_graph = load_json_safe(CLAIM_GRAPH, {}) or {}
    line_refs = build_line_to_claim_refs(envelope, claim_graph)
    line_refs_path = dest_dir / 'line-to-claim-refs.json'
    atomic_write_json(line_refs_path, line_refs)
    artifacts['line_to_claim_refs'] = {
        'name': 'line-to-claim-refs.json',
        'available': True,
        'path': str(line_refs_path),
        'sha256': file_hash(line_refs_path),
        'bytes': line_refs_path.stat().st_size,
    }
    required = ['envelope', 'reader_bundle', 'source_atoms', 'claim_graph', 'context_gaps', 'source_health', 'campaign_board', 'line_to_claim_refs']
    exact = all(artifacts[name].get('available') for name in required)
    manifest = {
        'generated_at': now_iso(),
        'contract': CONTRACT,
        'report_id': report_id,
        'exact_replay_available': exact,
        'missing_required_artifacts': [name for name in required if not artifacts[name].get('available')],
        'artifacts': artifacts,
        'line_to_claim_refs': 'line-to-claim-refs.json',
        'archive_dir': str(dest_dir),
        'no_execution': True,
    }
    atomic_write_json(dest_dir / 'manifest.json', manifest)
    return {'status': 'pass' if exact else 'degraded', 'report_id': report_id, 'archive_dir': str(dest_dir), 'exact_replay_available': exact}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Archive report-time finance artifacts for exact replay.')
    parser.add_argument('--out-root', default=str(DEFAULT_OUT_ROOT))
    parser.add_argument('--envelope', default=str(ENVELOPE))
    args = parser.parse_args(argv)
    report = archive_report(out_root=Path(args.out_root), envelope_path=Path(args.envelope))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get('status') in {'pass', 'degraded'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
