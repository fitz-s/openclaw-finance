#!/usr/bin/env python3
"""Translate raw TradingAgents output into advisory-only normalized artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tradingagents_bridge_types import (
    CHINESE_EXECUTION_PATTERNS,
    ENGLISH_EXECUTION_PATTERNS,
    canonical_hash,
    load_json,
    matches_any,
    normalize_line,
    now_iso,
    split_text_lines,
    write_json,
)


def _safe_lines(value: Any, *, limit: int = 4) -> list[str]:
    out: list[str] = []
    for line in split_text_lines(value):
        lowered = line.lower()
        if matches_any(lowered, ENGLISH_EXECUTION_PATTERNS):
            continue
        if matches_any(line, CHINESE_EXECUTION_PATTERNS):
            continue
        if len(line) < 18:
            continue
        if line not in out:
            out.append(normalize_line(line, 220))
        if len(out) >= limit:
            break
    return out


def _fallback_list(*values: str) -> list[str]:
    return [value for value in values if value]


def _rating_posture(signal: str | None) -> str:
    if signal in {'BUY', 'OVERWEIGHT'}:
        return 'supportive_but_non_authoritative'
    if signal in {'UNDERWEIGHT', 'SELL'}:
        return 'cautious_but_non_authoritative'
    return 'neutral_non_authoritative'


def translate_run(run_root: Path) -> dict[str, Any]:
    raw_dir = run_root / 'raw'
    normalized_dir = run_root / 'normalized'
    normalized_dir.mkdir(parents=True, exist_ok=True)

    raw_artifact = load_json(raw_dir / 'run-artifact.json', {}) or {}
    final_state = load_json(Path(str(raw_artifact.get('final_state_path') or raw_dir / 'redacted-final-state.json')), {}) or {}
    instrument = str(raw_artifact.get('instrument') or final_state.get('company_of_interest') or '')
    analysis_date = str(raw_artifact.get('analysis_date') or final_state.get('trade_date') or '')
    signal = str(raw_artifact.get('signal') or '').upper() or None

    analyst_bundle = {
        'generated_at': now_iso(),
        'instrument': instrument,
        'analysis_date': analysis_date,
        'market': _safe_lines(final_state.get('market_report')),
        'sentiment': _safe_lines(final_state.get('sentiment_report')),
        'news': _safe_lines(final_state.get('news_report')),
        'fundamentals': _safe_lines(final_state.get('fundamentals_report')),
        'review_only': True,
        'no_execution': True,
    }

    debate_bundle = {
        'generated_at': now_iso(),
        'instrument': instrument,
        'analysis_date': analysis_date,
        'investment_judge_summary': _safe_lines((final_state.get('investment_debate_state') or {}).get('judge_decision')),
        'investment_current_response': _safe_lines((final_state.get('investment_debate_state') or {}).get('current_response')),
        'investment_plan_summary': _safe_lines(final_state.get('investment_plan')),
        'review_only': True,
        'no_execution': True,
    }

    trader_machine = {
        'generated_at': now_iso(),
        'instrument': instrument,
        'analysis_date': analysis_date,
        'hypothetical_action': signal,
        'raw_ref': str(raw_dir / 'redacted-final-state.json'),
        'contains_execution_language': True,
        'surface_policy': 'machine_only',
        'review_only': True,
        'no_execution': True,
    }

    risk_flags = _safe_lines((final_state.get('risk_debate_state') or {}).get('judge_decision'))
    risk_review = {
        'generated_at': now_iso(),
        'instrument': instrument,
        'analysis_date': analysis_date,
        'risk_flags': risk_flags or _fallback_list('TradingAgents risk discussion must be independently validated before any thesis change.'),
        'missing_confirmations': _fallback_list(
            'Confirm deterministic source freshness before using this sidecar in review.',
            'Confirm valuation, liquidity, and catalyst timing outside TradingAgents output.',
        ),
        'display_severity': 'medium',
        'review_only': True,
        'no_execution': True,
    }

    advisory_decision = {
        'generated_at': now_iso(),
        'instrument': instrument,
        'analysis_date': analysis_date,
        'hypothetical_rating': signal,
        'posture': _rating_posture(signal),
        'summary_title_safe': f'TradingAgents sidecar | {instrument}',
        'why_now_safe': (
            _safe_lines(final_state.get('market_report'), limit=2)
            + _safe_lines(final_state.get('news_report'), limit=2)
        )[:4] or _fallback_list('TradingAgents surfaced a research case that still requires deterministic validation.'),
        'why_not_now_safe': _safe_lines((final_state.get('risk_debate_state') or {}).get('judge_decision'), limit=3) or _fallback_list(
            'TradingAgents output is review-only and cannot directly change judgment or execution state.'
        ),
        'invalidators_safe': _safe_lines(final_state.get('sentiment_report'), limit=2) or _fallback_list(
            'If deterministic source freshness or capital competition data disagrees, treat the sidecar as non-decisive.'
        ),
        'required_confirmations_safe': _fallback_list(
            'Validate source freshness and rights before promoting any claim.',
            'Require independent thesis, invalidator, and capital graph confirmation before using this in review.',
        ),
        'source_gaps_safe': _fallback_list(
            'No deterministic citation promotion is implemented in this phase.',
            'Generated prose remains sidecar commentary until converted into deterministic source fetches.',
        ),
        'risk_flags_safe': risk_review['risk_flags'],
        'execution_readiness': 'disabled',
        'review_only': True,
        'no_execution': True,
        'raw_refs': {
            'run_artifact': str(raw_dir / 'run-artifact.json'),
            'final_state': str(raw_dir / 'redacted-final-state.json'),
        },
    }

    outputs = {
        'analyst-bundle.json': analyst_bundle,
        'debate-bundle.json': debate_bundle,
        'trader-proposal-machine.json': trader_machine,
        'risk-review.json': risk_review,
        'advisory-decision.json': advisory_decision,
    }
    for name, payload in outputs.items():
        payload['content_hash'] = canonical_hash(payload)
        write_json(normalized_dir / name, payload)

    return {
        'status': 'pass',
        'normalized_dir': str(normalized_dir),
        'instrument': instrument,
        'analysis_date': analysis_date,
        'review_only': True,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Translate raw TradingAgents run to advisory artifacts.')
    parser.add_argument('--run-root', required=True)
    args = parser.parse_args(argv)
    result = translate_run(Path(args.run_root))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
