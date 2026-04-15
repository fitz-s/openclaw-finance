#!/usr/bin/env python3
"""Shared helpers for finance thesis-spine scripts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
POLICY_VERSION = 'finance-thesis-spine-v1'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def stable_id(prefix: str, *parts: Any) -> str:
    material = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(material.encode('utf-8')).hexdigest()[:16]


def clean_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper().replace('/', '-')
    if not symbol or len(symbol) > 16 or not any(ch.isalpha() for ch in symbol):
        return None
    return symbol


def load(path: Path, default: Any = None) -> Any:
    return load_json_safe(path, default)


def write(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def symbol_set(payload: dict[str, Any]) -> set[str]:
    out = set()
    for item in payload.get('tickers', []) if isinstance(payload.get('tickers'), list) else []:
        if isinstance(item, dict):
            sym = clean_symbol(item.get('symbol'))
            if sym:
                out.add(sym)
    return out


def source_refs(*paths: Path) -> list[str]:
    return [str(path) for path in paths]


def merge_unique(*values: list[Any]) -> list[Any]:
    seen = set()
    merged = []
    for seq in values:
        if not isinstance(seq, list):
            continue
        for item in seq:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged
