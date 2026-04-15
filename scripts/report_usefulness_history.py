#!/usr/bin/env python3
"""Persist report usefulness history for delivered and candidate finance reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from atomic_io import load_json_safe
from thesis_spine_util import FINANCE, now_iso
from wake_attribution_logger import append_unique


TOOLS = FINANCE / 'tools'
sys.path.insert(0, str(TOOLS))

from score_report_usefulness import score_text  # noqa: E402


REPORT = FINANCE / 'state' / 'finance-decision-report-envelope.json'
PRODUCT_VALIDATION = FINANCE / 'state' / 'finance-report-product-validation.json'
DELIVERY_SAFETY = FINANCE / 'state' / 'report-delivery-safety-check.json'
OUT = FINANCE / 'state' / 'report-usefulness-history.jsonl'


def event_id(report_hash: str | None, generated_at: str | None) -> str:
    raw = f'{report_hash or ""}|{generated_at or ""}'
    return 'report-usefulness:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def delta_density(markdown: str) -> float:
    lines = [line for line in markdown.splitlines() if line.startswith('- ')]
    if not lines:
        return 0.0
    delta_lines = [
        line for line in lines
        if any(token in line for token in ['结构变化', '机会队列', '未知', '反证', '下一步', '等待确认'])
    ]
    return round(len(delta_lines) / len(lines), 4)


def build_row(report: dict[str, Any], product_validation: dict[str, Any], delivery_safety: dict[str, Any]) -> dict[str, Any]:
    markdown = str(report.get('markdown') or '')
    quality = score_text(markdown)
    return {
        'event_id': event_id(report.get('report_hash'), report.get('generated_at')),
        'logged_at': now_iso(),
        'report_hash': report.get('report_hash'),
        'report_renderer': report.get('renderer_id'),
        'product_status': product_validation.get('status'),
        'delivery_safety_status': delivery_safety.get('status'),
        'delivery_blocking_reasons': delivery_safety.get('blocking_reasons', []),
        'usefulness_score': quality.get('score'),
        'noise_tokens': quality.get('noise_tokens', []),
        'line_count': quality.get('line_count'),
        'char_count': quality.get('char_count'),
        'delta_density': delta_density(markdown),
        'thesis_ref_count': len(report.get('thesis_refs') or []),
        'opportunity_ref_count': len(report.get('opportunity_candidate_refs') or []),
        'invalidator_ref_count': len(report.get('invalidator_refs') or []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default=str(REPORT))
    parser.add_argument('--product-validation', default=str(PRODUCT_VALIDATION))
    parser.add_argument('--delivery-safety', default=str(DELIVERY_SAFETY))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    row = build_row(
        load_json_safe(Path(args.report), {}) or {},
        load_json_safe(Path(args.product_validation), {}) or {},
        load_json_safe(Path(args.delivery_safety), {}) or {},
    )
    appended = append_unique(Path(args.out), row)
    print(json.dumps({'status': 'pass', 'appended': appended, 'usefulness_score': row['usefulness_score'], 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
