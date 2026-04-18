#!/usr/bin/env python3
"""Finance gate evaluator — continuous decay + threshold gate + event-driven dispatch."""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional, Dict
from atomic_io import atomic_write_json, load_json_safe
from gate_calibration import save_gate_calibration, GATE_CALIBRATION_SUMMARY_JSON, GATE_CALIBRATION_SUMMARY_MD

OPENCLAW = '/Users/leofitz/.npm-global/bin/openclaw'
REPORT_ORCHESTRATOR_IDS = {
    'short': 'b2c3d4e5-f6a7-8901-bcde-f01234567890',
    'core': 'b2c3d4e5-f6a7-8901-bcde-f01234567890',
    'immediate_alert': 'b2c3d4e5-f6a7-8901-bcde-f01234567890',
}

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
STATE_DIR = FINANCE / 'state'
GATE_STATE = STATE_DIR / 'report-gate-state.json'
SCAN_STATE = STATE_DIR / 'intraday-open-scan-state.json'
GATE_CONFIG = STATE_DIR / 'intraday-gate-config.json'
DECAY_CONFIG = STATE_DIR / 'decay-config.json'
SERVICE_STATE = WORKSPACE / 'services' / 'market-ingest' / 'state'
LIVE_EVIDENCE = SERVICE_STATE / 'live-evidence-records.jsonl'
LIVE_EVIDENCE_REPORT = SERVICE_STATE / 'live-evidence-report.json'
TEMPORAL_ALIGNMENT_REPORT = SERVICE_STATE / 'temporal-alignment-report.json'
LATEST_CONTEXT_PACKET = SERVICE_STATE / 'latest-context-packet.json'
LIVE_PACKET_REPORT = SERVICE_STATE / 'live-packet-report.json'
WAKE_REPORT = SERVICE_STATE / 'wake-report.json'
LATEST_WAKE = STATE_DIR / 'latest-wake-decision.json'
WAKE_DISPATCH_STATE = STATE_DIR / 'wake-dispatch-state.json'
ORCHESTRATOR_INPUT = STATE_DIR / 'report-orchestrator-input.json'
REPORT_PACKET_SCRIPT = FINANCE / 'scripts' / 'finance_report_packet.py'

LIVE_ADAPTER_SCRIPT = WORKSPACE / 'services' / 'market-ingest' / 'adapters' / 'live_finance_adapter.py'
ALIGNMENT_SCRIPT = WORKSPACE / 'services' / 'market-ingest' / 'temporal_alignment' / 'alignment.py'
PACKET_COMPILER_SCRIPT = WORKSPACE / 'services' / 'market-ingest' / 'packet_compiler' / 'compiler.py'
WAKE_POLICY_SCRIPT = WORKSPACE / 'services' / 'market-ingest' / 'wake_policy' / 'policy.py'
WAKE_DISPATCHER_SCRIPT = FINANCE / 'scripts' / 'wake_dispatcher.py'
THESIS_STATE_REDUCER_SCRIPT = FINANCE / 'scripts' / 'thesis_state_reducer.py'
SEC_DISCOVERY_SCRIPT = FINANCE / 'scripts' / 'sec_discovery_fetcher.py'
SEC_SEMANTICS_SCRIPT = FINANCE / 'scripts' / 'sec_filing_semantics.py'
BROAD_MARKET_SCRIPT = FINANCE / 'scripts' / 'broad_market_proxy_fetcher.py'
OPTIONS_FLOW_SCRIPT = FINANCE / 'scripts' / 'options_flow_proxy_fetcher.py'
SEC_DISCOVERY_STATE = STATE_DIR / 'sec-discovery.json'
SEC_SEMANTICS_STATE = STATE_DIR / 'sec-filing-semantics.json'
BROAD_MARKET_STATE = STATE_DIR / 'broad-market-proxy.json'
OPTIONS_FLOW_STATE = STATE_DIR / 'options-flow-proxy.json'

TZ_CHICAGO = ZoneInfo('America/Chicago')
TZ_ET = ZoneInfo('America/New_York')

WINDOWS = {
    'overnight': (19 * 60, 3 * 60 + 30),
    'pre': (3 * 60 + 30, 8 * 60 + 30),
    'open': (8 * 60 + 30, 11 * 60 + 30),
    'mid': (11 * 60 + 30, 14 * 60),
    'late': (14 * 60, 15 * 60),
    'post': (15 * 60, 19 * 60),
}

DEFAULT_THRESHOLDS = {
    'market_hours': {
        'immediate_alert_urgency': 9,
        'alert_min_minutes_since_last': 120,
        'short_cumulative_value': 20,
        'short_min_minutes_since_last': 45,
        'core_importance': 30,
        'core_min_minutes_since_last': 180,
    },
    'off_hours': {
        'immediate_alert_urgency': 9,
        'alert_min_minutes_since_last': 240,
        'short_cumulative_value': 40,
        'short_min_minutes_since_last': 60,
        'core_importance': 50,
        'core_min_minutes_since_last': 240,
    },
    'weekend': {
        'immediate_alert_urgency': 9,
        'alert_min_minutes_since_last': 240,
        'short_cumulative_value': 90,
        'short_min_minutes_since_last': 360,
        'core_importance': 120,
        'core_min_minutes_since_last': 720,
    },
}

DEFAULT_DECAY = {
    'decay_factor': 0.9,
    'post_report_decay_factor': 0.7,
    'min_threshold': 1.5,
    'exempt_keywords': [
        'assassination', 'nuclear', 'declaration of war', 'declares war',
        'missile attack', 'airstrike', 'drone attack', 'attacked', 'attack',
        '暗杀', '核打击', '宣战',
    ],
}


def current_window(now_chicago: datetime) -> str:
    if now_chicago.weekday() >= 5:
        return 'weekend'
    hm = now_chicago.hour * 60 + now_chicago.minute
    if hm >= 19 * 60 or hm < 3 * 60 + 30:
        return 'overnight'
    for name, (start, end) in WINDOWS.items():
        if name != 'overnight' and start <= hm < end:
            return name
    return 'post'


def is_market_hours(window: str) -> bool:
    return window in ('open', 'mid', 'late', 'post')


def get_thresholds(window: str, config: Optional[Dict], now_chicago: Optional[datetime] = None) -> Dict:
    now_chicago = now_chicago or datetime.now(TZ_CHICAGO)
    if config and 'thresholds' in config:
        if now_chicago.weekday() >= 5 and 'weekend' in config['thresholds']:
            return dict(config['thresholds']['weekend'])
        if is_market_hours(window) and 'market_hours' in config['thresholds']:
            return dict(config['thresholds']['market_hours'])
        if not is_market_hours(window) and 'off_hours' in config['thresholds']:
            return dict(config['thresholds']['off_hours'])
    if now_chicago.weekday() >= 5:
        return dict(DEFAULT_THRESHOLDS['weekend'])
    return dict(DEFAULT_THRESHOLDS['market_hours' if is_market_hours(window) else 'off_hours'])


def apply_gate_calibration(window: str, thresholds: Dict, calibration: Optional[Dict]) -> Dict:
    """Blend deterministic calibration adjustments into the active thresholds."""
    if not calibration:
        return thresholds

    cal_key = 'market_hours' if is_market_hours(window) else 'off_hours'
    win = calibration.get('windows', {}).get(cal_key, {}) if isinstance(calibration, dict) else {}
    multipliers = win.get('multipliers', {}) if isinstance(win, dict) else {}
    offsets = win.get('offsets', {}) if isinstance(win, dict) else {}

    adjusted = dict(thresholds)
    for key, base in list(adjusted.items()):
        if not isinstance(base, (int, float)):
            continue
        mult = multipliers.get(key, 1.0)
        off = offsets.get(key, 0.0)
        try:
            adjusted[key] = round(float(base) * float(mult) + float(off), 2)
        except Exception:
            adjusted[key] = base
    return adjusted


def minutes_since(iso_str: Optional[str], now: datetime) -> float:
    if not iso_str:
        return 9999.0
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return (now - dt).total_seconds() / 60.0
    except Exception:
        return 9999.0


def parse_iso_dt(iso_str: Optional[str]) -> datetime | None:
    if not iso_str:
        return None
    try:
        parsed = datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_jsonl_safe(path: Path, limit: int = 500) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def event_time_for_record(record: dict) -> datetime | None:
    for key in ('observed_at', 'published_at', 'effective_from', 'ingested_at', 'detected_at'):
        parsed = parse_iso_dt(record.get(key))
        if parsed is not None:
            return parsed
    return None


def latest_iso(values: list[datetime]) -> str | None:
    if not values:
        return None
    return max(values).isoformat().replace('+00:00', 'Z')


def live_evidence_freshness(now_utc: datetime, *, freshness_minutes: int = 120) -> dict:
    """Summarize parent market-ingest freshness for the legacy gate.

    This does not grant wake authority. It only prevents the legacy scanner
    stale guard from hiding the fact that parent ContextPacket evidence moved.
    """
    rows = load_jsonl_safe(LIVE_EVIDENCE)
    event_times: list[datetime] = []
    ingested_times: list[datetime] = []
    fresh_records: list[dict] = []
    support_count = 0
    wake_count = 0
    context_only_count = 0
    support_needs_primary_count = 0
    fresh_support_count = 0
    fresh_context_only_count = 0
    fresh_non_support_context_count = 0

    for row in rows:
        q = row.get('quarantine') if isinstance(row.get('quarantine'), dict) else {}
        sf = row.get('structured_facts') if isinstance(row.get('structured_facts'), dict) else {}
        event_time = event_time_for_record(row)
        ingested = parse_iso_dt(row.get('ingested_at') or row.get('detected_at'))
        if event_time:
            event_times.append(event_time)
        if ingested:
            ingested_times.append(ingested)
        is_fresh = bool(event_time and (now_utc - event_time).total_seconds() <= freshness_minutes * 60)
        if is_fresh:
            fresh_records.append(row)
        support_allowed = q.get('allowed_for_judgment_support') is True
        wake_allowed = q.get('allowed_for_wake') is True
        context_only = str(q.get('disposition') or '').upper() == 'CONTEXT_ONLY'
        needs_primary = (
            q.get('support_requires_primary_confirmation') is True
            or sf.get('support_requires_primary_confirmation') is True
        )
        support_count += int(support_allowed)
        wake_count += int(wake_allowed)
        context_only_count += int(context_only)
        support_needs_primary_count += int(needs_primary)
        fresh_support_count += int(is_fresh and support_allowed)
        fresh_context_only_count += int(is_fresh and context_only)
        fresh_non_support_context_count += int(is_fresh and context_only and not support_allowed)

    latest_event = max(event_times) if event_times else None
    latest_ingested = max(ingested_times) if ingested_times else None
    latest_age_min = round((now_utc - latest_event).total_seconds() / 60.0, 1) if latest_event else None
    status = 'missing'
    if rows:
        if fresh_support_count:
            status = 'fresh_support'
        elif fresh_context_only_count:
            status = 'fresh_context_only'
        elif latest_age_min is not None and latest_age_min <= freshness_minutes:
            status = 'fresh_non_support'
        else:
            status = 'stale'
    warnings: list[str] = []
    if rows and wake_count == 0:
        warnings.append('no_wake_eligible_live_evidence')
    if fresh_non_support_context_count:
        warnings.append('fresh_context_only_without_judgment_support')
    if support_needs_primary_count:
        warnings.append('fresh_support_requires_primary_confirmation')
    if status in {'missing', 'stale'}:
        warnings.append('live_evidence_not_fresh')
    return {
        'status': status,
        'freshness_window_minutes': freshness_minutes,
        'record_count': len(rows),
        'latest_event_at': latest_iso(event_times),
        'latest_ingested_at': latest_iso(ingested_times),
        'latest_event_age_minutes': latest_age_min,
        'support_count': support_count,
        'wake_allowed_count': wake_count,
        'context_only_count': context_only_count,
        'fresh_record_count': len(fresh_records),
        'fresh_support_count': fresh_support_count,
        'fresh_context_only_count': fresh_context_only_count,
        'fresh_non_support_context_count': fresh_non_support_context_count,
        'support_requires_primary_confirmation_count': support_needs_primary_count,
        'clears_legacy_stale': fresh_support_count > 0,
        'warnings': warnings,
        'source': str(LIVE_EVIDENCE),
    }


def apply_decay(candidates: list, decay_cfg: dict) -> list:
    """Continuous decay: reduce all scores, remove items below threshold.
    Exempt keywords bypass decay entirely (nuclear/assassination/war events persist).
    An item survives if ANY of its core scores (urgency, importance, cumulative_value)
    remains above the threshold — not just importance alone.
    """
    factor = decay_cfg['decay_factor']
    threshold = decay_cfg['min_threshold']
    exempt_kws = decay_cfg['exempt_keywords']

    result = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        summary = c.get('summary', '').lower()
        obs_id = str(c.get('id', '')).lower()
        sources = ' '.join(str(s) for s in c.get('sources', []) if s).lower()
        if any(kw.lower() in summary for kw in exempt_kws) or (
            obs_id.startswith('emergency-news-') and c.get('urgency', 0) >= 9
        ) or (
            'native-emergency-news' in sources and c.get('urgency', 0) >= 9
        ):
            result.append(c)
            continue

        for key in ('urgency', 'importance', 'cumulative_value'):
            c[key] = round(c.get(key, 0) * factor, 2)

        best_score = max(c.get('urgency', 0), c.get('importance', 0), c.get('cumulative_value', 0))
        if best_score >= threshold:
            result.append(c)

    return result


def apply_post_report_decay(candidates: list, decay_cfg: dict) -> list:
    """Aggressive decay after a report is sent — prevents same signals from re-triggering."""
    factor = decay_cfg['post_report_decay_factor']
    for c in candidates:
        for key in ('urgency', 'importance', 'cumulative_value'):
            c[key] = round(c.get(key, 0) * factor, 2)
    return candidates


def run_json_step(args: list[str], timeout: int = 90) -> dict:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {
            'returncode': 124,
            'status': 'timeout',
            'stdout_preview': (exc.stdout or '')[:500] if isinstance(exc.stdout, str) else '',
            'stderr_preview': (exc.stderr or '')[:500] if isinstance(exc.stderr, str) else '',
            'error': f'timed out after {timeout}s',
            'command': ' '.join(str(part) for part in args[:3]),
        }
    except OSError as exc:
        return {
            'returncode': 127,
            'status': 'os_error',
            'stderr_preview': str(exc)[:500],
            'command': ' '.join(str(part) for part in args[:3]),
        }
    payload = {}
    if result.stdout.strip():
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
        except Exception:
            payload = {'stdout_preview': result.stdout.strip()[:500]}
    payload['returncode'] = result.returncode
    if result.stderr.strip():
        payload['stderr_preview'] = result.stderr.strip()[:500]
    return payload


def run_wake_pipeline() -> dict:
    steps = [
        (
            'thesis_state_reducer',
            [
                sys.executable,
                str(THESIS_STATE_REDUCER_SCRIPT),
            ],
            True,
            60,
        ),
        (
            'sec_discovery_fetcher',
            [
                sys.executable,
                str(SEC_DISCOVERY_SCRIPT),
                '--count', '8',
                '--out', str(SEC_DISCOVERY_STATE),
            ],
            True,
            45,
        ),
        (
            'sec_filing_semantics',
            [
                sys.executable,
                str(SEC_SEMANTICS_SCRIPT),
                '--discovery', str(SEC_DISCOVERY_STATE),
                '--out', str(SEC_SEMANTICS_STATE),
            ],
            True,
            45,
        ),
        (
            'broad_market_proxy',
            [
                sys.executable,
                str(BROAD_MARKET_SCRIPT),
                '--out', str(BROAD_MARKET_STATE),
            ],
            True,
            45,
        ),
        (
            'options_flow_proxy',
            [
                sys.executable,
                str(OPTIONS_FLOW_SCRIPT),
                '--out', str(OPTIONS_FLOW_STATE),
            ],
            True,
            45,
        ),
        (
            'live_evidence_adapter',
            [
                sys.executable,
                str(LIVE_ADAPTER_SCRIPT),
                '--report', str(LIVE_EVIDENCE_REPORT),
                '--evidence-jsonl', str(LIVE_EVIDENCE),
                '--limit', '20',
            ],
            False,
            90,
        ),
        (
            'temporal_alignment',
            [
                sys.executable,
                str(ALIGNMENT_SCRIPT),
                '--evidence-jsonl', str(LIVE_EVIDENCE),
                '--report', str(TEMPORAL_ALIGNMENT_REPORT),
            ],
            False,
            90,
        ),
        (
            'context_packet',
            [
                sys.executable,
                str(PACKET_COMPILER_SCRIPT),
                '--evidence-jsonl', str(LIVE_EVIDENCE),
                '--alignment-report', str(TEMPORAL_ALIGNMENT_REPORT),
                '--report', str(LIVE_PACKET_REPORT),
                '--latest-packet', str(LATEST_CONTEXT_PACKET),
            ],
            False,
            90,
        ),
        (
            'wake_policy',
            [
                sys.executable,
                str(WAKE_POLICY_SCRIPT),
                '--packet', str(LATEST_CONTEXT_PACKET),
                '--evidence-jsonl', str(LIVE_EVIDENCE),
                '--report', str(WAKE_REPORT),
                '--latest-wake', str(LATEST_WAKE),
            ],
            False,
            90,
        ),
        (
            'wake_dispatcher',
            [
                sys.executable,
                str(WAKE_DISPATCHER_SCRIPT),
                '--wake-decision', str(LATEST_WAKE),
            ],
            False,
            90,
        ),
    ]
    report = {
        'attempted': True,
        'ok': True,
        'optional_failed_steps': [],
        'steps': {},
        'wake_decision_path': str(LATEST_WAKE),
        'wake_dispatch_state_path': str(WAKE_DISPATCH_STATE),
    }
    for name, args, optional, timeout in steps:
        payload = run_json_step(args, timeout=timeout)
        payload['optional'] = optional
        report['steps'][name] = payload
        if payload.get('returncode') != 0:
            if optional:
                report['optional_failed_steps'].append(name)
                continue
            report['ok'] = False
            report['failed_step'] = name
            break
    report['wake_decision'] = load_json_safe(LATEST_WAKE, {}) or {}
    report['wake_dispatch'] = load_json_safe(WAKE_DISPATCH_STATE, {}) or {}
    return report


def dispatch_legacy_threshold_report(report_type: str, reason: str, gate_state: dict, wake_pipeline: dict) -> dict:
    """Bridge legacy threshold gates into the active OpenClaw report orchestrator.

    The canonical wake policy may correctly classify the packet as PACKET_UPDATE_ONLY
    when all evidence is support-only. Legacy threshold gates are still the intraday
    report-rate contract, so a passed short/core/immediate threshold must enqueue the
    active report orchestrator instead of silently persisting.
    """
    orchestrator_id = REPORT_ORCHESTRATOR_IDS.get(report_type)
    if not orchestrator_id:
        return {
            'status': 'blocked',
            'action': 'blocked',
            'blocking_reasons': [f'unknown_report_type:{report_type}'],
        }
    wake_decision = wake_pipeline.get('wake_decision') if isinstance(wake_pipeline.get('wake_decision'), dict) else {}
    generated_at = datetime.now(timezone.utc)
    payload = {
        'generated_at': generated_at.isoformat().replace('+00:00', 'Z'),
        'expires_at': (generated_at + timedelta(minutes=30)).isoformat().replace('+00:00', 'Z'),
        'one_shot': True,
        'report_class': 'legacy_threshold',
        'legacy_report_type': report_type,
        'legacy_reason': reason,
        'gate_evaluated_at': gate_state.get('evaluatedAt'),
        'packet_id': wake_decision.get('packet_id'),
        'packet_hash': wake_decision.get('packet_hash'),
        'wake_id': wake_decision.get('wake_id'),
        'wake_class': wake_decision.get('wake_class'),
        'wake_reason': wake_decision.get('wake_reason'),
        'evidence_refs': wake_decision.get('evidence_refs', []),
        'policy_version': wake_decision.get('policy_version'),
    }
    atomic_write_json(ORCHESTRATOR_INPUT, payload)
    try:
        result = subprocess.run(
            [OPENCLAW, 'cron', 'run', orchestrator_id],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        return {
            'status': 'fail',
            'action': 'dispatch_failed',
            'blocking_reasons': ['openclaw_cron_run_exception'],
            'error': str(exc)[:500],
        }
    action = 'dispatched' if result.returncode == 0 else 'dispatch_failed'
    return {
        'status': 'pass' if result.returncode == 0 else 'fail',
        'action': action,
        'dispatched': result.returncode == 0,
        'orchestrator_id': orchestrator_id,
        'orchestrator_input': str(ORCHESTRATOR_INPUT),
        'run_result': {
            'returncode': result.returncode,
            'stdout_preview': result.stdout.strip()[:500],
            'stderr_preview': result.stderr.strip()[:500],
        },
        'blocking_reasons': [] if result.returncode == 0 else ['openclaw_cron_run_failed'],
    }


def parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def clear_stale_orchestrator_input(now_utc: datetime) -> dict:
    """Remove expired one-shot report inputs so scheduled reports are not misrouted."""
    if not ORCHESTRATOR_INPUT.exists():
        return {'status': 'pass', 'action': 'absent'}
    payload = load_json_safe(ORCHESTRATOR_INPUT, {}) or {}
    report_class = payload.get('report_class') if isinstance(payload, dict) else None
    if report_class not in {'legacy_threshold', 'event_wake', 'ops_escalation'}:
        return {'status': 'pass', 'action': 'kept_non_one_shot', 'report_class': report_class}
    expires_at = parse_iso(payload.get('expires_at'))
    if expires_at is None:
        generated_at = parse_iso(payload.get('generated_at'))
        expires_at = generated_at + timedelta(minutes=30) if generated_at is not None else now_utc
    if expires_at > now_utc:
        return {
            'status': 'pass',
            'action': 'kept_fresh_one_shot',
            'report_class': report_class,
            'expires_at': expires_at.isoformat(),
        }
    try:
        ORCHESTRATOR_INPUT.unlink()
    except FileNotFoundError:
        pass
    return {
        'status': 'pass',
        'action': 'cleared_expired_one_shot',
        'report_class': report_class,
        'expires_at': expires_at.isoformat(),
    }


def refresh_compat_report_input_packet() -> dict:
    """Keep deprecated report-input-packet.json aligned with current gate state.

    The active report path does not use this packet as cognition input, but old
    validators and audits still read it. Leaving it stale creates a second truth
    surface that looks authoritative while describing a prior market window.
    """
    try:
        result = run_json_step([sys.executable, str(REPORT_PACKET_SCRIPT)], timeout=60)
    except Exception as exc:
        return {
            'status': 'fail',
            'action': 'compat_packet_refresh_failed',
            'blocking_reasons': ['finance_report_packet_exception'],
            'error': str(exc)[:500],
        }
    return {
        'status': 'pass' if result.get('returncode') == 0 else 'fail',
        'action': 'compat_packet_refreshed' if result.get('returncode') == 0 else 'compat_packet_refresh_failed',
        'result': result,
    }


def main():
    now_utc = datetime.now(timezone.utc)
    now_chi = now_utc.astimezone(TZ_CHICAGO)
    window = current_window(now_chi)

    config = load_json_safe(GATE_CONFIG, {})
    thresholds = get_thresholds(window, config, now_chi)
    calibration = save_gate_calibration()
    print(f"📝 Gate calibration summary: {GATE_CALIBRATION_SUMMARY_MD}")
    thresholds = apply_gate_calibration(window, thresholds, calibration.to_json())

    raw_decay = load_json_safe(DECAY_CONFIG, {})
    decay_cfg = {k: raw_decay.get(k, v) for k, v in DEFAULT_DECAY.items()}

    scan = load_json_safe(SCAN_STATE, {})
    candidates = scan.get('accumulated', [])

    # --- Step 0: Data freshness check ---
    # Legacy scanner observations remain the threshold substrate, but parent
    # market-ingest may have fresher support-only evidence after source cutover.
    last_scan = scan.get('last_scan_time')
    legacy_data_stale = False
    legacy_scan_age_min = None
    data_stale = False
    if last_scan:
        scan_age_min = minutes_since(last_scan, now_utc)
        legacy_scan_age_min = round(scan_age_min, 1)
        if scan_age_min > 120:
            legacy_data_stale = True
            print(f"⚠️ Data stale: last scan was {scan_age_min:.0f} min ago (>{120} min threshold)")
    live_freshness = live_evidence_freshness(now_utc)
    data_stale = legacy_data_stale and not live_freshness.get('clears_legacy_stale')
    if legacy_data_stale and not data_stale:
        print("ℹ️ Legacy scan stale, but parent live evidence has fresh judgment-supporting context.")

    # --- Step 1: Continuous decay (runs every evaluation) ---
    before_count = len(candidates)
    candidates = apply_decay(candidates, decay_cfg)
    removed = before_count - len(candidates)

    # --- Step 2: Evaluate thresholds on decayed signals ---
    last_short = scan.get('last_short_report_sent')
    last_core = scan.get('last_core_report_sent')
    last_alert = scan.get('last_alert_sent')
    last_any = scan.get('last_any_report_sent')

    total_urgency = sum(c.get('urgency', 0) for c in candidates)
    total_importance = sum(c.get('importance', 0) for c in candidates)
    total_novelty = sum(c.get('novelty', 0) for c in candidates)
    total_cv = sum(c.get('cumulative_value', 0) for c in candidates)
    max_urgency = max((c.get('urgency', 0) for c in candidates), default=0)

    m_short = minutes_since(last_short, now_utc)
    m_core = minutes_since(last_core, now_utc)
    m_alert = minutes_since(last_alert, now_utc)
    m_any = minutes_since(last_any, now_utc)

    # Global cooldown: no report of ANY type within 60 minutes of the last report
    # Exception: immediate_alert (urgency >= 9) can override global cooldown
    global_cooldown_min = thresholds.get('global_min_minutes_between_any_report', 60)
    global_cooldown_ok = m_any >= global_cooldown_min

    # Quiet hours: short and core reports only during reasonable hours (07:00-22:00 Chicago)
    # immediate_alert can fire at any time (urgency >= 9 = genuine emergency)
    hour_chi = now_chi.hour
    in_quiet_hours = (hour_chi < 7 or hour_chi >= 22) and not is_market_hours(window)

    short_passed = (total_cv >= thresholds['short_cumulative_value'] and
                    m_short >= thresholds['short_min_minutes_since_last'] and
                    global_cooldown_ok and
                    not in_quiet_hours)
    core_passed = (total_importance >= thresholds['core_importance'] and
                   m_core >= thresholds['core_min_minutes_since_last'] and
                   global_cooldown_ok and
                   not in_quiet_hours)

    # UX floor: a trading day with non-trivial accumulated candidates should not
    # stay silent until late afternoon just because calibrated thresholds tightened.
    # This is still review-only and still uses the same safety-gated report path.
    midday_floor_start_minute = thresholds.get('midday_floor_start_minute', 11 * 60 + 30)
    midday_floor_candidate_count = thresholds.get('midday_floor_candidate_count', 3)
    midday_floor_cumulative_value = thresholds.get('midday_floor_cumulative_value', 10)
    midday_floor_min_minutes_since_any = thresholds.get('midday_floor_min_minutes_since_any', 120)
    minutes_now = now_chi.hour * 60 + now_chi.minute
    midday_floor_passed = (
        now_chi.weekday() < 5
        and window in {'mid', 'late'}
        and minutes_now >= midday_floor_start_minute
        and len(candidates) >= midday_floor_candidate_count
        and total_cv >= midday_floor_cumulative_value
        and m_any >= midday_floor_min_minutes_since_any
        and global_cooldown_ok
        and not in_quiet_hours
    )
    if midday_floor_passed:
        short_passed = True
    alert_passed = (max_urgency >= thresholds['immediate_alert_urgency'] and
                    m_alert >= thresholds.get('alert_min_minutes_since_last', 120))
    # immediate_alert intentionally checks NEITHER global_cooldown NOR quiet_hours

    should_send = (short_passed or core_passed or alert_passed) and not data_stale

    rec_type = 'hold'
    reason = 'thresholds not met'

    if data_stale:
        reason = f"data stale ({minutes_since(last_scan, now_utc):.0f} min since last scan)"
    elif alert_passed:
        rec_type = 'immediate_alert'
        reason = f"single_observation_urgency={max_urgency} >= {thresholds['immediate_alert_urgency']}"
    elif short_passed and core_passed:
        rec_type = 'core'
        reason = f"short+core both passed; core fires to avoid perpetual short-only loop (cv={total_cv}, importance={total_importance})"
    elif midday_floor_passed:
        rec_type = 'short'
        reason = (
            f"midday_floor: no market-hours report for {m_any:.0f}m; "
            f"candidate_count={len(candidates)} >= {midday_floor_candidate_count}; "
            f"total_cumulative_value={total_cv} >= {midday_floor_cumulative_value}"
        )
    elif short_passed:
        rec_type = 'short'
        reason = f"total_cumulative_value={total_cv} >= {thresholds['short_cumulative_value']}"
    elif core_passed:
        rec_type = 'core'
        reason = f"total_importance={total_importance} >= {thresholds['core_importance']}"

    state = {
        "evaluator": "gate_evaluator.py",
        "evaluatedAt": now_utc.isoformat(),
        "asOfChicago": now_chi.strftime('%Y-%m-%d %H:%M:%S %Z'),
        "asOfET": now_utc.astimezone(TZ_ET).strftime('%Y-%m-%d %H:%M:%S %Z'),
        "window": window,
        "isMarketHours": is_market_hours(window),
        "dataStale": data_stale,
        "legacyDataStale": legacy_data_stale,
        "legacyScanAgeMinutes": legacy_scan_age_min,
        "liveEvidenceFreshness": live_freshness,
        "candidateCount": len(candidates),
        "decayedRemoved": removed,
        "totalUrgency": round(total_urgency, 2),
        "totalImportance": round(total_importance, 2),
        "totalNovelty": total_novelty,
        "totalCumulativeValue": round(total_cv, 2),
        "maxSingleUrgency": max_urgency,
        "minutesSinceLastShort": round(m_short, 1),
        "minutesSinceLastCore": round(m_core, 1),
        "minutesSinceLastAlert": round(m_alert, 1),
        "thresholdsUsed": thresholds,
        "gateCalibration": calibration.to_json(),
        "gateCalibrationSummaryPath": str(GATE_CALIBRATION_SUMMARY_JSON),
        "shortThresholdPassed": short_passed,
        "coreThresholdPassed": core_passed,
        "immediateAlertPassed": alert_passed,
        "middayFloorPassed": midday_floor_passed,
        "shouldSend": should_send,
        "recommendedReportType": rec_type,
        "decisionReason": reason,
        "pending_report": rec_type if should_send else None,
    }

    atomic_write_json(GATE_STATE, state)
    print(json.dumps(state, indent=2))

    # --- Step 3: Canonical WakeDecision pipeline and dispatch ---
    wake_pipeline = run_wake_pipeline()
    state['legacyThresholdGate'] = {
        'shouldSend': should_send,
        'recommendedReportType': rec_type,
        'decisionReason': reason,
    }
    state['wakePipeline'] = wake_pipeline
    state['wakeDecision'] = wake_pipeline.get('wake_decision')
    state['wakeDispatch'] = wake_pipeline.get('wake_dispatch')
    state['rendererDispatch'] = wake_pipeline.get('wake_dispatch')
    legacy_dispatch = None
    if should_send:
        wake_action = (wake_pipeline.get('wake_dispatch') or {}).get('action')
        if wake_pipeline.get('ok') is not True:
            legacy_dispatch = {
                'status': 'blocked',
                'action': 'blocked',
                'dispatched': False,
                'blocking_reasons': ['wake_pipeline_failed'],
                'failed_step': wake_pipeline.get('failed_step'),
            }
            state['legacyThresholdDispatch'] = legacy_dispatch
        elif wake_action != 'dispatched':
            legacy_dispatch = dispatch_legacy_threshold_report(rec_type, reason, state, wake_pipeline)
            state['legacyThresholdDispatch'] = legacy_dispatch
    else:
        state['orchestratorInputMaintenance'] = clear_stale_orchestrator_input(now_utc)
    atomic_write_json(GATE_STATE, state)

    dispatch_action = (legacy_dispatch or wake_pipeline.get('wake_dispatch') or {}).get('action')
    if dispatch_action == 'dispatched':
        # Post-report decay and cooldown timestamps only mean "successfully handed to OpenClaw orchestrator".
        candidates = apply_post_report_decay(candidates, decay_cfg)
        ts_now = now_utc.isoformat()
        scan['last_any_report_sent'] = ts_now
        if rec_type == 'immediate_alert':
            scan['last_alert_sent'] = ts_now
        elif rec_type == 'short':
            scan['last_short_report_sent'] = ts_now
        elif rec_type == 'core':
            scan['last_core_report_sent'] = ts_now

    # --- Step 4: Auto-create event watchers for high-value signals ---
    try:
        from event_watcher import create_watcher, load_json as _ew_load
        existing = _ew_load(Path('/Users/leofitz/.openclaw/workspace/finance/state/event-watchers.json'))
        existing_themes = {w.get('theme', '').lower()[:30] for w in existing.get('watchers', []) if w.get('status') == 'active'}
        for c in candidates:
            imp = c.get('importance', 0)
            urg = c.get('urgency', 0)
            if imp >= 7 or urg >= 8:
                theme = c.get('theme', '')
                if theme.lower()[:30] not in existing_themes:
                    # Extract tickers from theme
                    import re
                    tickers = sorted(set(re.findall(r'\b[A-Z]{2,5}\b', theme)) & {'SPY','QQQ','AAPL','MSFT','NVDA','TSLA','GOOG','AMZN','META','NFLX','AMD','ORCL','BTC','SMR','HIMS'})
                    ttl = 3 if urg >= 9 else 7
                    w = create_watcher(theme, tickers, f"auto: importance={imp} urgency={urg}", ttl)
                    print(f"📡 Watcher created: {w['id']} — {theme[:60]}")
                    existing_themes.add(theme.lower()[:30])
    except Exception as e:
        print(f"⚠️ Watcher creation skipped: {e}")

    # --- Step 5: Persist decayed state ---
    scan['accumulated'] = candidates
    scan['last_decay_time'] = now_utc.isoformat()
    atomic_write_json(SCAN_STATE, scan)
    state['compatReportInputPacketRefresh'] = refresh_compat_report_input_packet()
    atomic_write_json(GATE_STATE, state)
    if removed:
        print(f"📉 Decay: {removed} items removed below threshold.")


if __name__ == '__main__':
    main()
