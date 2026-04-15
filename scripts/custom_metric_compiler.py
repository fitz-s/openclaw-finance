#!/usr/bin/env python3
"""Compile deterministic custom metrics for Thesis Spine sidecar artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, write


RESEARCH_PACKET = FINANCE / 'state' / 'thesis-research-packet.json'
PRICES = FINANCE / 'state' / 'prices.json'
OPTIONS_FLOW = FINANCE / 'state' / 'options-flow-proxy.json'
OUT = FINANCE / 'state' / 'custom-metrics' / 'thesis-spine-metrics.json'


def price_snapshot(symbol: str | None, prices: dict[str, Any]) -> dict[str, Any]:
    quotes = prices.get('quotes') if isinstance(prices.get('quotes'), dict) else {}
    quote = quotes.get(symbol or '') if isinstance(quotes, dict) else None
    if not isinstance(quote, dict):
        return {'status': 'unavailable'}
    return {
        'status': quote.get('status', 'unknown'),
        'price': quote.get('price'),
        'pct_change': quote.get('pct_change') if quote.get('pct_change') is not None else quote.get('change_pct'),
        'volume': quote.get('volume'),
    }


def option_flow_snapshot(symbol: str | None, options_flow: dict[str, Any]) -> dict[str, Any]:
    rows = [item for item in options_flow.get('top_events', []) if isinstance(item, dict)]
    for item in rows:
        if symbol and item.get('symbol') == symbol:
            return {
                'status': 'available',
                'call_put': item.get('call_put'),
                'expiry': item.get('expiry'),
                'strike': item.get('strike'),
                'volume_oi_ratio': item.get('volume_oi_ratio'),
                'score': item.get('score'),
            }
    return {'status': 'unavailable'}


def compile_metrics(research_packet: dict[str, Any], prices: dict[str, Any], options_flow: dict[str, Any]) -> dict[str, Any]:
    metrics = []
    for item in research_packet.get('selected_opportunities', []):
        if not isinstance(item, dict):
            continue
        symbol = item.get('instrument')
        metrics.append({
            'target_type': 'opportunity',
            'target_id': item.get('candidate_id'),
            'instrument': symbol,
            'opportunity_score': item.get('score'),
            'price_snapshot': price_snapshot(symbol, prices),
            'option_flow_snapshot': option_flow_snapshot(symbol, options_flow),
        })
    for item in research_packet.get('selected_theses', []):
        if not isinstance(item, dict):
            continue
        symbol = item.get('instrument')
        metrics.append({
            'target_type': 'thesis',
            'target_id': item.get('thesis_id'),
            'instrument': symbol,
            'status': item.get('status'),
            'maturity': item.get('maturity'),
            'price_snapshot': price_snapshot(symbol, prices),
            'option_flow_snapshot': option_flow_snapshot(symbol, options_flow),
        })
    return {
        'generated_at': now_iso(),
        'policy_version': POLICY_VERSION,
        'metric_scope': 'sidecar_research_only',
        'metrics': metrics,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--research-packet', default=str(RESEARCH_PACKET))
    parser.add_argument('--prices', default=str(PRICES))
    parser.add_argument('--options-flow', default=str(OPTIONS_FLOW))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = compile_metrics(
        load(Path(args.research_packet), {}) or {},
        load(Path(args.prices), {}) or {},
        load(Path(args.options_flow), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({'status': 'pass', 'metric_count': len(payload['metrics']), 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
