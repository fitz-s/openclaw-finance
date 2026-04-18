#!/usr/bin/env python3
"""Fetch normalized, derived-only options IV provider observations.

Provider rows are source context only. They cannot wake, mutate thresholds,
support execution, or become JudgmentEnvelope primary authority in this phase.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from options_flow_proxy_fetcher import watchlist_symbols


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'options-iv-provider-snapshot.json'
FETCH_RECORDS = STATE / 'options-iv-fetch-records.jsonl'
CONTRACT = 'options-iv-provider-snapshot-v1'
FETCH_CONTRACT = 'source-fetch-record-v1'
DEFAULT_SYMBOL_LIMIT = 12
DEFAULT_TIMEOUT = 8
PROVIDERS = ('thetadata', 'polygon', 'tradier')


PROVIDER_META = {
    'thetadata': {
        'source_id': 'source:thetadata_options_iv',
        'endpoint': 'thetadata/option/snapshot/greeks/implied_volatility',
        'base_env': 'THETADATA_BASE_URL',
        'default_base': 'http://127.0.0.1:25510',
        'rights_policy': 'derived_only',
        'latency_class': 'intraday',
        'point_in_time_replay_supported': True,
        'provider_confidence_base': 0.82,
    },
    'polygon': {
        'source_id': 'source:polygon_options_iv',
        'endpoint': 'polygon/options/snapshot',
        'key_env': 'POLYGON_API_KEY',
        'rights_policy': 'derived_only',
        'latency_class': 'intraday',
        'point_in_time_replay_supported': False,
        'provider_confidence_base': 0.72,
    },
    'tradier': {
        'source_id': 'source:tradier_options_iv',
        'endpoint': 'tradier/markets/options/chains',
        'key_env': 'TRADIER_ACCESS_TOKEN',
        'rights_policy': 'derived_only',
        'latency_class': 'intraday',
        'point_in_time_replay_supported': False,
        'provider_confidence_base': 0.58,
        'confidence_penalties': ['courtesy_orats_greeks_hourly'],
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows), encoding='utf-8')
    tmp.replace(path)


def append_jsonl(path: Path, rows: list[dict[str, Any]], *, keep: int = 500) -> None:
    existing = []
    if path.exists():
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                existing.append(item)
    write_jsonl(path, (existing + rows)[-keep:])


def number(value: Any) -> float | None:
    try:
        if value is None or value != value:
            return None
        return float(str(value).replace(',', '').replace('%', '').strip())
    except (TypeError, ValueError):
        return None


def int_number(value: Any) -> int | None:
    n = number(value)
    return int(n) if n is not None else None


def source_fetch_record(
    *,
    provider: str,
    symbol: str,
    status: str,
    fetched_at: str,
    result_count: int = 0,
    error_class: str | None = None,
    application_error_code: str | None = None,
    request_params: dict[str, Any] | None = None,
    quota_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = PROVIDER_META[provider]
    params = request_params or {}
    return {
        'contract': FETCH_CONTRACT,
        'fetch_id': stable_id('fetch', meta['endpoint'], symbol, fetched_at, status, error_class, application_error_code),
        'pack_id': None,
        'source_id': meta['source_id'],
        'lane': 'market_structure',
        'source_sublane': 'market_structure.options_iv',
        'endpoint': meta['endpoint'],
        'request_params': params,
        'fetched_at': fetched_at,
        'status': status,
        'quota_state': quota_state or {},
        'result_count': result_count,
        'watermark_key': f"market_structure.options_iv:{provider}:{symbol}",
        'error_code': application_error_code,
        'application_error_code': application_error_code,
        'error_class': error_class,
        'raw_response_persisted': False,
        'raw_payload_retained': False,
        'derived_only': True,
        'no_execution': True,
    }


def observation(
    *,
    provider: str,
    symbol: str,
    expiration: str | None = None,
    strike: float | None = None,
    call_put: str | None = None,
    observed_at: str | None = None,
    implied_volatility: float | None = None,
    delta: float | None = None,
    gamma: float | None = None,
    theta: float | None = None,
    vega: float | None = None,
    open_interest: int | None = None,
    volume: int | None = None,
    iv_rank: float | None = None,
    iv_percentile: float | None = None,
    raw_ref: str | None = None,
) -> dict[str, Any]:
    meta = PROVIDER_META[provider]
    observed = observed_at or now_iso()
    return {
        'observation_id': stable_id('options-iv', provider, symbol, expiration, strike, call_put, observed, implied_volatility),
        'symbol': symbol.upper(),
        'expiration': expiration,
        'strike': strike,
        'call_put': call_put,
        'observed_at': observed,
        'provider': provider,
        'source_id': meta['source_id'],
        'source_sublane': 'market_structure.options_iv',
        'rights_policy': meta['rights_policy'],
        'latency_class': meta['latency_class'],
        'point_in_time_replay_supported': meta['point_in_time_replay_supported'],
        'provider_confidence_base': meta['provider_confidence_base'],
        'confidence_penalties': list(meta.get('confidence_penalties', [])),
        'implied_volatility': implied_volatility,
        'delta': delta,
        'gamma': gamma,
        'theta': theta,
        'vega': vega,
        'open_interest': open_interest,
        'volume': volume,
        'volume_oi_ratio': round(volume / open_interest, 4) if volume is not None and open_interest and open_interest > 0 else None,
        'iv_rank': iv_rank,
        'iv_percentile': iv_percentile,
        'raw_ref': raw_ref,
        'derived_only': True,
        'raw_payload_retained': False,
        'no_execution': True,
    }


def normalize_polygon(symbol: str, payload: dict[str, Any], *, observed_at: str) -> list[dict[str, Any]]:
    results = payload.get('results') if isinstance(payload.get('results'), list) else []
    rows: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        details = item.get('details') if isinstance(item.get('details'), dict) else {}
        greeks = item.get('greeks') if isinstance(item.get('greeks'), dict) else {}
        rows.append(observation(
            provider='polygon',
            symbol=symbol,
            expiration=details.get('expiration_date'),
            strike=number(details.get('strike_price')),
            call_put=details.get('contract_type'),
            observed_at=item.get('last_quote', {}).get('sip_timestamp') if isinstance(item.get('last_quote'), dict) else observed_at,
            implied_volatility=number(item.get('implied_volatility')),
            delta=number(greeks.get('delta')),
            gamma=number(greeks.get('gamma')),
            theta=number(greeks.get('theta')),
            vega=number(greeks.get('vega')),
            open_interest=int_number(item.get('open_interest')),
            volume=int_number(item.get('day', {}).get('volume') if isinstance(item.get('day'), dict) else item.get('volume')),
            raw_ref=item.get('ticker') or details.get('ticker'),
        ))
    return [row for row in rows if row.get('implied_volatility') is not None]


def normalize_thetadata(symbol: str, payload: Any, *, observed_at: str) -> list[dict[str, Any]]:
    rows = payload.get('response') if isinstance(payload, dict) else payload
    if isinstance(rows, dict):
        rows = rows.get('data') or rows.get('rows') or [rows]
    out: list[dict[str, Any]] = []
    for item in rows if isinstance(rows, list) else []:
        if not isinstance(item, dict):
            continue
        out.append(observation(
            provider='thetadata',
            symbol=symbol,
            expiration=item.get('expiration') or item.get('expiration_date'),
            strike=number(item.get('strike')),
            call_put=item.get('right') or item.get('call_put') or item.get('type'),
            observed_at=item.get('ms_of_day') or item.get('timestamp') or observed_at,
            implied_volatility=number(item.get('implied_volatility') or item.get('iv')),
            delta=number(item.get('delta')),
            gamma=number(item.get('gamma')),
            theta=number(item.get('theta')),
            vega=number(item.get('vega')),
            open_interest=int_number(item.get('open_interest') or item.get('openInterest')),
            volume=int_number(item.get('volume')),
            raw_ref=item.get('contract') or item.get('root') or symbol,
        ))
    return [row for row in out if row.get('implied_volatility') is not None]


def normalize_tradier(symbol: str, payload: dict[str, Any], *, observed_at: str) -> list[dict[str, Any]]:
    options = (((payload.get('options') or {}).get('option')) if isinstance(payload, dict) else [])
    if isinstance(options, dict):
        options = [options]
    out: list[dict[str, Any]] = []
    for item in options if isinstance(options, list) else []:
        if not isinstance(item, dict):
            continue
        greeks = item.get('greeks') if isinstance(item.get('greeks'), dict) else {}
        out.append(observation(
            provider='tradier',
            symbol=symbol,
            expiration=item.get('expiration_date'),
            strike=number(item.get('strike')),
            call_put=item.get('option_type'),
            observed_at=observed_at,
            implied_volatility=number(greeks.get('mid_iv') or greeks.get('smv_vol') or greeks.get('iv')),
            delta=number(greeks.get('delta')),
            gamma=number(greeks.get('gamma')),
            theta=number(greeks.get('theta')),
            vega=number(greeks.get('vega')),
            open_interest=int_number(item.get('open_interest')),
            volume=int_number(item.get('volume')),
            raw_ref=item.get('symbol'),
        ))
    return [row for row in out if row.get('implied_volatility') is not None]


def get_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, dict[str, Any], dict[str, str]]:
    request = urllib.request.Request(url, headers=headers or {'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode('utf-8', errors='replace')
        payload = json.loads(body) if body else {}
        return response.status, payload if isinstance(payload, dict) else {}, dict(response.headers.items())


def fetch_polygon(symbol: str, *, timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    key = os.environ.get('POLYGON_API_KEY')
    fetched = now_iso()
    if not key:
        return [], source_fetch_record(provider='polygon', symbol=symbol, status='failed', fetched_at=fetched, error_class='missing_credentials', application_error_code='missing_api_key')
    url = f"https://api.polygon.io/v3/snapshot/options/{urllib.parse.quote(symbol)}?limit=250&apiKey={urllib.parse.quote(key)}"
    try:
        status, payload, headers = get_json(url, timeout=timeout)
    except urllib.error.HTTPError as exc:
        code = 'rate_limited' if exc.code in {402, 429} else 'failed'
        err = 'quota_limited' if code == 'rate_limited' else 'application_error'
        return [], source_fetch_record(provider='polygon', symbol=symbol, status=code, fetched_at=fetched, error_class=err, application_error_code=str(exc.code), quota_state={'status_code': exc.code})
    except Exception as exc:
        return [], source_fetch_record(provider='polygon', symbol=symbol, status='failed', fetched_at=fetched, error_class='network_error', application_error_code=exc.__class__.__name__)
    rows = normalize_polygon(symbol, payload, observed_at=fetched)
    return rows, source_fetch_record(provider='polygon', symbol=symbol, status='ok' if rows else 'partial', fetched_at=fetched, result_count=len(rows), quota_state={'status_code': status, 'x_ratelimit_remaining': headers.get('X-RateLimit-Remaining')})


def fetch_thetadata(symbol: str, *, timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = os.environ.get('THETADATA_BASE_URL', 'http://127.0.0.1:25510').rstrip('/')
    fetched = now_iso()
    url = f"{base}/v3/option/snapshot/greeks/implied_volatility?root={urllib.parse.quote(symbol)}&expiration=*&use_csv=false"
    try:
        status, payload, _headers = get_json(url, timeout=timeout)
    except Exception as exc:
        return [], source_fetch_record(provider='thetadata', symbol=symbol, status='failed', fetched_at=fetched, error_class='network_error', application_error_code=exc.__class__.__name__, request_params={'base_url': base, 'root': symbol, 'expiration': '*'})
    rows = normalize_thetadata(symbol, payload, observed_at=fetched)
    return rows, source_fetch_record(provider='thetadata', symbol=symbol, status='ok' if rows else 'partial', fetched_at=fetched, result_count=len(rows), quota_state={'status_code': status}, request_params={'base_url': base, 'root': symbol, 'expiration': '*'})


def fetch_tradier(symbol: str, *, timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    token = os.environ.get('TRADIER_ACCESS_TOKEN')
    fetched = now_iso()
    if not token:
        return [], source_fetch_record(provider='tradier', symbol=symbol, status='failed', fetched_at=fetched, error_class='missing_credentials', application_error_code='missing_api_key')
    base = os.environ.get('TRADIER_BASE_URL', 'https://api.tradier.com/v1').rstrip('/')
    url = f"{base}/markets/options/chains?symbol={urllib.parse.quote(symbol)}&greeks=true"
    headers = {'Accept': 'application/json', 'Authorization': f'Bearer {token}'}
    try:
        status, payload, headers_out = get_json(url, headers=headers, timeout=timeout)
    except urllib.error.HTTPError as exc:
        code = 'rate_limited' if exc.code in {402, 429} else 'failed'
        err = 'quota_limited' if code == 'rate_limited' else 'subscription_denied' if exc.code in {401, 403} else 'application_error'
        return [], source_fetch_record(provider='tradier', symbol=symbol, status=code, fetched_at=fetched, error_class=err, application_error_code=str(exc.code), quota_state={'status_code': exc.code})
    except Exception as exc:
        return [], source_fetch_record(provider='tradier', symbol=symbol, status='failed', fetched_at=fetched, error_class='network_error', application_error_code=exc.__class__.__name__)
    rows = normalize_tradier(symbol, payload, observed_at=fetched)
    return rows, source_fetch_record(provider='tradier', symbol=symbol, status='ok' if rows else 'partial', fetched_at=fetched, result_count=len(rows), quota_state={'status_code': status, 'x_ratelimit_remaining': headers_out.get('X-RateLimit-Remaining')})


def fetch_provider(provider: str, symbol: str, *, timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if provider == 'polygon':
        return fetch_polygon(symbol, timeout=timeout)
    if provider == 'thetadata':
        return fetch_thetadata(symbol, timeout=timeout)
    if provider == 'tradier':
        return fetch_tradier(symbol, timeout=timeout)
    fetched = now_iso()
    return [], source_fetch_record(provider='polygon', symbol=symbol, status='failed', fetched_at=fetched, error_class='application_error', application_error_code='unknown_provider')


def build_snapshot(symbols: list[str], providers: list[str], *, timeout: int = DEFAULT_TIMEOUT) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    generated = now_iso()
    observations: list[dict[str, Any]] = []
    fetch_records: list[dict[str, Any]] = []
    for provider in providers:
        for symbol in symbols:
            rows, record = fetch_provider(provider, symbol, timeout=timeout)
            observations.extend(rows)
            fetch_records.append(record)
    status = 'pass' if observations else 'degraded'
    return {
        'generated_at': generated,
        'status': status,
        'contract': CONTRACT,
        'providers_requested': providers,
        'provider_set': sorted({row['provider'] for row in observations}),
        'symbol_count': len(set(row['symbol'] for row in observations)),
        'observation_count': len(observations),
        'observations': sorted(observations, key=lambda row: (row['symbol'], row.get('expiration') or '', row.get('strike') or 0, row.get('call_put') or '')),
        'fetch_record_count': len(fetch_records),
        'fetch_record_status_counts': {
            status: sum(1 for row in fetch_records if row.get('status') == status)
            for status in sorted({str(row.get('status')) for row in fetch_records})
        },
        'derived_only': True,
        'raw_payload_retained': False,
        'shadow_only': True,
        'no_execution': True,
    }, fetch_records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Fetch normalized derived-only options IV provider observations.')
    parser.add_argument('--symbols', default=None)
    parser.add_argument('--providers', default='polygon,thetadata,tradier')
    parser.add_argument('--symbol-limit', type=int, default=DEFAULT_SYMBOL_LIMIT)
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--fetch-records', default=str(FETCH_RECORDS))
    args = parser.parse_args(argv)
    out = Path(args.out)
    fetch_records_path = Path(args.fetch_records)
    if not safe_state_path(out) or not safe_state_path(fetch_records_path):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    symbols = [item.strip().upper() for item in args.symbols.split(',') if item.strip()] if args.symbols else watchlist_symbols(limit=args.symbol_limit)
    providers = [item.strip().lower() for item in args.providers.split(',') if item.strip()]
    providers = [provider for provider in providers if provider in PROVIDERS]
    snapshot, records = build_snapshot(symbols, providers, timeout=args.timeout)
    atomic_write_json(out, snapshot)
    append_jsonl(fetch_records_path, records)
    print(json.dumps({'status': snapshot['status'], 'observation_count': snapshot['observation_count'], 'fetch_record_count': len(records), 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
