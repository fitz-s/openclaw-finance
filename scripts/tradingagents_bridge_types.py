#!/usr/bin/env python3
"""Shared constants and helpers for TradingAgents sidecar bridge."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
SERVICE_STATE = FINANCE.parent / 'services' / 'market-ingest' / 'state'
TRADINGAGENTS_STATE = STATE / 'tradingagents'
TRADINGAGENTS_RUNS = TRADINGAGENTS_STATE / 'runs'
TRADINGAGENTS_RUNTIME = TRADINGAGENTS_STATE / 'runtime'
TRADINGAGENTS_RUNTIME_CACHE = TRADINGAGENTS_RUNTIME / 'cache'
TRADINGAGENTS_RUNTIME_LOGS = TRADINGAGENTS_RUNTIME / 'logs'
TRADINGAGENTS_LATEST = TRADINGAGENTS_STATE / 'latest.json'
TRADINGAGENTS_STATUS = TRADINGAGENTS_STATE / 'status.json'
TRADINGAGENTS_CONTEXT_DIGEST = TRADINGAGENTS_STATE / 'latest-context-digest.json'
TRADINGAGENTS_READER_AUGMENTATION = TRADINGAGENTS_STATE / 'latest-reader-augmentation.json'
TRADINGAGENTS_DEFAULTS = FINANCE / 'ops' / 'tradingagents-sidecar.defaults.json'
TRADINGAGENTS_SUBMODULE = FINANCE / 'third_party' / 'tradingagents'
THESIS_RESEARCH_PACKET = STATE / 'thesis-research-packet.json'
REPORT_ENVELOPE = STATE / 'finance-decision-report-envelope.json'
DECISION_LOG = STATE / 'finance-decision-log-report.json'
PACKET = SERVICE_STATE / 'latest-context-packet.json'

DEFAULT_FORBIDDEN_ACTIONS = [
    'no_user_delivery',
    'no_execution',
    'no_threshold_mutation',
    'no_live_authority_change',
]

ENGLISH_EXECUTION_PATTERNS = [
    r'\bbuy\b',
    r'\bsell\b',
    r'\bexecute\b',
    r'place order',
    r'market order',
    r'limit order',
    r'stop loss',
    r'take profit',
    r'position size',
    r'allocation',
    r'entry price',
    r'exit price',
    r'final transaction proposal',
    r'execution_adapter',
    r'live_authority',
]

CHINESE_EXECUTION_PATTERNS = [
    r'买入',
    r'卖出',
    r'下单',
    r'执行交易',
    r'市价单',
    r'限价单',
    r'止损',
    r'止盈',
    r'仓位',
    r'加仓',
    r'减仓',
    r'开仓',
    r'平仓',
    r'目标价',
    r'入场',
    r'出场',
    r'交易建议',
    r'自动执行',
    r'实盘权限',
]

SECRET_PATTERNS = [
    r'OPENAI_API_KEY',
    r'ANTHROPIC_API_KEY',
    r'GOOGLE_API_KEY',
    r'ALPHA_VANTAGE_API_KEY',
    r'sk-[A-Za-z0-9_-]+',
    r'accountId',
    r'acctId',
    r'acctAlias',
    r'FlexQueryResponse',
    r'Bearer\s+[A-Za-z0-9._-]+',
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def age_hours(value: str | None) -> float | None:
    dt = parse_iso(value)
    if not dt:
        return None
    return max((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 0.0)


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def clean_instrument(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().upper().replace('/', '-')
    if not text or len(text) > 24:
        return None
    if not any(ch.isalpha() for ch in text):
        return None
    return text


def ensure_within(root: Path, path: Path) -> None:
    resolved_root = root.resolve(strict=False)
    resolved = path.resolve(strict=False)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f'path escapes root: {path} not within {root}')


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path, default: Any = None) -> Any:
    return load_json_safe(path, default)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def path_artifact(path: Path, *, required: bool = False) -> dict[str, Any]:
    return {
        'path': str(path),
        'exists': path.exists(),
        'hash': canonical_hash(load_json_safe(path, {})) if path.exists() and path.suffix == '.json' else None,
        'required': required,
    }


def load_defaults() -> dict[str, Any]:
    payload = load_json(TRADINGAGENTS_DEFAULTS, {}) or {}
    if not isinstance(payload, dict):
        raise ValueError('invalid TradingAgents defaults')
    return payload


def make_run_id(instrument: str, analysis_date: str, mode: str) -> str:
    return stable_id('ta', mode, instrument, analysis_date, now_iso())


def normalize_line(value: Any, limit: int = 220) -> str:
    text = ' '.join(str(value or '').split())
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + '...'


def split_text_lines(value: Any) -> list[str]:
    text = str(value or '')
    parts = re.split(r'[\n\r]+|(?<=[.!?])\s+|(?<=[。！？])', text)
    lines = [normalize_line(part, 240) for part in parts if str(part).strip()]
    out: list[str] = []
    for line in lines:
        if line not in out:
            out.append(line)
    return out


def matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def redact_text(text: str) -> tuple[str, int]:
    redactions = 0
    output = text
    for pattern in SECRET_PATTERNS:
        output, count = re.subn(pattern, '[REDACTED]', output, flags=re.I)
        redactions += count
    return output, redactions


def redact_payload(payload: Any) -> tuple[Any, dict[str, Any]]:
    report = {'redaction_count': 0}

    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            redacted, count = redact_text(value)
            report['redaction_count'] += count
            return redacted
        return value

    return walk(payload), report
