#!/usr/bin/env python3
"""Weekend/offhours emergency news scanner.

Deterministic RSS-based emergency lane. It is intentionally narrow: emit only
high-severity market-moving headlines so weekend monitoring can run without
turning into a noisy news feed.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import json
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
OPS_STATE = Path('/Users/leofitz/.openclaw/workspace/ops/state')
BUFFER_DIR = FINANCE / 'buffer'
STATE_DIR = FINANCE / 'state'
REPORT_PATH = OPS_STATE / 'finance-native-emergency-news-report.json'
TZ_CHI = ZoneInfo('America/Chicago')
MAX_HEADLINE_AGE_HOURS = 18
DEFAULT_QUERIES = [
    'Iran Hormuz oil tanker attack',
    'nuclear threat market oil',
    'declaration of war market oil',
    'assassination president market',
    'Federal Reserve emergency meeting markets',
    'stock market crash futures',
    'Israel Iran ceasefire collapse oil',
    'US sanctions emergency market',
]
EMERGENCY_PATTERNS = {
    'assassination': 10.0,
    'nuclear': 10.0,
    'declaration of war': 10.0,
    'declares war': 10.0,
    'missile attack': 9.5,
    'airstrike': 9.2,
    'drone attack': 9.0,
    'strait of hormuz': 9.2,
    'hormuz': 9.0,
    'oil tanker': 9.0,
    'emergency meeting': 9.0,
    'market crash': 9.2,
    'trading halt': 9.0,
    'ceasefire collapses': 9.0,
    'ceasefire collapse': 9.0,
    'sanctions': 8.8,
    'invasion': 9.5,
}

LOW_QUALITY_TITLE_PATTERNS = [
    re.compile(r'\bcrash\s+or\s+rally\b', re.I),
    re.compile(r'\b(crash|rally)\?\b', re.I),
    re.compile(r'\b[a-z]+\s+vs\s+[a-z]+\b', re.I),
    re.compile(r'\([A-Za-z0-9_-]{8,}\)'),
]

LOW_QUALITY_SOURCES = {'mshale'}
TRUSTED_SOURCES = {
    'reuters', 'associated press', 'ap news', 'bloomberg', 'financial times', 'the wall street journal',
    'wsj', 'cnbc', 'bbc', 'al jazeera', 'the times of india', 'marketwatch', "barron's",
    'federal reserve', 'sec', 'u.s. securities and exchange commission', 'white house',
}

CONFIRMED_EVENT_PATTERNS = [
    re.compile(r'\b(attacked|attack|strikes?|struck|hit|killed|explosion|halted|suspended|closed|blocked|collapses|collapsed|declares?|announces?)\b', re.I),
    re.compile(r'\bdown\s+\d+(?:\.\d+)?%\b', re.I),
    re.compile(r'\bup\s+\d+(?:\.\d+)?%\b', re.I),
]

QUESTION_OR_SPECULATION_PATTERNS = [
    re.compile(r'\?$'),
    re.compile(r'\b(could|may|might|what if|will .*\?)\b', re.I),
]


def low_quality_title_reason(title: str, source: str) -> str | None:
    source_norm = source.strip().lower()
    if source_norm in LOW_QUALITY_SOURCES:
        return f'low-quality source: {source}'
    for pattern in LOW_QUALITY_TITLE_PATTERNS:
        if pattern.search(title):
            return f'title noise pattern: {pattern.pattern}'
    return None


def is_trusted_source(source: str) -> bool:
    source_norm = source.strip().lower()
    return any(source_norm == trusted or trusted in source_norm for trusted in TRUSTED_SOURCES)


def has_confirmed_event_language(title: str) -> bool:
    return any(pattern.search(title) for pattern in CONFIRMED_EVENT_PATTERNS)


def is_speculative_title(title: str) -> bool:
    return any(pattern.search(title.strip()) for pattern in QUESTION_OR_SPECULATION_PATTERNS)


def confidence_reject_reason(title: str, source: str, score: float) -> str | None:
    if score < 9.0:
        return 'score below immediate-alert emergency floor'
    if is_speculative_title(title) and not has_confirmed_event_language(title):
        return 'speculative/question title without confirmed event language'
    if not is_trusted_source(source) and not has_confirmed_event_language(title):
        return f'untrusted source without confirmed event language: {source}'
    return None


def current_window(now_chicago: datetime) -> str:
    if now_chicago.weekday() >= 5:
        return 'weekend'
    hm = now_chicago.hour * 60 + now_chicago.minute
    if hm >= 19 * 60 or hm < 3 * 60 + 30:
        return 'overnight'
    if 3 * 60 + 30 <= hm < 8 * 60 + 30:
        return 'pre'
    if 8 * 60 + 30 <= hm < 11 * 60 + 30:
        return 'open'
    if 11 * 60 + 30 <= hm < 14 * 60:
        return 'mid'
    if 14 * 60 <= hm < 15 * 60:
        return 'late'
    return 'post'


def fetch_feed(query: str, timeout: float) -> list[dict]:
    encoded = urllib.parse.quote_plus(query)
    url = f'https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en'
    req = urllib.request.Request(url, headers={'User-Agent': 'OpenClawFinanceEmergencyScanner/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    items = []
    for item in root.findall('.//item')[:10]:
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        pub = (item.findtext('pubDate') or '').strip()
        source_el = item.find('source')
        source = source_el.text.strip() if source_el is not None and source_el.text else 'Google News'
        published = None
        if pub:
            try:
                published = parsedate_to_datetime(pub).astimezone(timezone.utc)
            except Exception:
                published = None
        items.append({'title': title, 'link': link, 'source': source, 'published_at': published})
    return items


def score_headline(title: str) -> float | None:
    lowered = title.lower()
    hits = [score for pattern, score in EMERGENCY_PATTERNS.items() if pattern in lowered]
    if not hits:
        return None
    return max(hits)


def build_observation(item: dict, query: str, scan_dt: datetime) -> dict | None:
    title = item.get('title') or ''
    source = item.get('source') or ''
    if low_quality_title_reason(title, source):
        return None
    score = score_headline(title)
    if score is None:
        return None
    if confidence_reject_reason(title, source, score):
        return None
    published = item.get('published_at')
    if published is not None:
        age_hours = (scan_dt - published).total_seconds() / 3600
        if age_hours < -0.25 or age_hours > MAX_HEADLINE_AGE_HOURS:
            return None
    uid_base = f"{title}|{item.get('source')}|{item.get('published_at')}"
    uid = hashlib.sha1(uid_base.encode('utf-8')).hexdigest()[:16]
    ts = (published or scan_dt).isoformat()
    return {
        'id': f'emergency-news-{uid}',
        'ts': ts,
        'theme': title[:160],
        'summary': title,
        'sources': ['native-emergency-news', item.get('source') or 'Google News', item.get('link') or '', f'query:{query}'],
        'urgency': score,
        'importance': min(10.0, score),
        'novelty': 8.0,
        'cumulative_value': min(10.0, max(8.0, score - 0.5)),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--weekend-only', action='store_true')
    parser.add_argument('--skip-downstream', action='store_true')
    parser.add_argument('--timeout', type=float, default=6.0)
    parser.add_argument('--query', action='append', default=[])
    parser.add_argument('--report', default=str(REPORT_PATH))
    parser.add_argument('--output-dir', default=str(BUFFER_DIR))
    args = parser.parse_args(argv)

    scan_dt = datetime.now(timezone.utc)
    now_chi = scan_dt.astimezone(TZ_CHI)
    if args.weekend_only and now_chi.weekday() < 5:
        report = {
            'generated_at': scan_dt.isoformat(),
            'status': 'skipped',
            'reason': 'weekday; weekend-only lane skipped',
            'as_of_chicago': now_chi.strftime('%Y-%m-%d %H:%M:%S %Z'),
        }
        atomic_write_json(Path(args.report), report)
        print(json.dumps({'status': 'skipped', 'reason': report['reason']}, ensure_ascii=False))
        return 0

    queries = args.query or DEFAULT_QUERIES
    observations = []
    fetch_errors = []
    rejected_items = []
    seen = set()
    for query in queries:
        try:
            items = fetch_feed(query, args.timeout)
        except Exception as exc:
            fetch_errors.append({'query': query, 'error': str(exc)[:240]})
            continue
        for item in items:
            title = item.get('title') or ''
            source = item.get('source') or ''
            reject_reason = low_quality_title_reason(title, source)
            score = score_headline(title)
            if reject_reason is None and score is not None:
                reject_reason = confidence_reject_reason(title, source, score)
            if reject_reason:
                rejected_items.append({
                    'query': query,
                    'title': title,
                    'source': source,
                    'score': score,
                    'reason': reject_reason,
                })
                continue
            obs = build_observation(item, query, scan_dt)
            if not obs or obs['id'] in seen:
                continue
            seen.add(obs['id'])
            observations.append(obs)

    observations.sort(key=lambda o: (-float(o.get('urgency', 0)), o.get('theme', '')))
    observations = observations[:6]
    output = {
        'scan_time': scan_dt.isoformat(),
        'window': current_window(now_chi),
        'model': 'native-emergency-news-rss-v1',
        'observations': observations,
        'market_state': {},
        'aggregate_scores': {
            'weighted_urgency': round(sum(o['urgency'] for o in observations), 2),
            'weighted_importance': round(sum(o['importance'] for o in observations), 2),
        },
        'decision': 'watch' if observations else 'hold',
        'decision_reason': 'emergency RSS scan; only high-severity headlines are emitted',
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{now_chi.strftime('%Y-%m-%d')}-emergency-{now_chi.strftime('%H%M')}.json"
    atomic_write_json(out_path, output)

    downstream = {'worker_rc': None, 'gate_rc': None}
    if not args.skip_downstream:
        worker = subprocess.run([sys.executable, str(FINANCE / 'scripts' / 'finance_worker.py')], cwd=str(FINANCE / 'scripts'), timeout=60)
        gate = subprocess.run([sys.executable, str(FINANCE / 'scripts' / 'gate_evaluator.py')], cwd=str(FINANCE / 'scripts'), timeout=90)
        downstream = {'worker_rc': worker.returncode, 'gate_rc': gate.returncode}

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pass' if not fetch_errors or observations else 'degraded',
        'as_of_chicago': now_chi.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'output_path': str(out_path),
        'query_count': len(queries),
        'observation_count': len(observations),
        'fetch_error_count': len(fetch_errors),
        'fetch_errors': fetch_errors[:10],
        'rejected_item_count': len(rejected_items),
        'rejected_items': rejected_items[:20],
        'downstream': downstream,
    }
    atomic_write_json(Path(args.report), report)
    print(json.dumps({k: report[k] for k in ['status', 'observation_count', 'fetch_error_count', 'output_path']}, ensure_ascii=False))
    return 0 if report['status'] in {'pass', 'degraded'} else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
