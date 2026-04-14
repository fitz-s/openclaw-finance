#!/usr/bin/env python3
"""Deterministic gate calibration for finance report gating.

This module reads the current finance state and turns noisy signals into
window-specific threshold adjustments.

The calibration is intentionally conservative: it only shifts thresholds when
there is evidence that the gate is too permissive or too brittle.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
STATE_DIR = FINANCE / 'state'
SCAN_STATE = STATE_DIR / 'intraday-open-scan-state.json'
GATE_STATE = STATE_DIR / 'report-gate-state.json'
SIGNAL_WEIGHTS = STATE_DIR / 'signal-weights.json'
CALIBRATION_ANCHORS = STATE_DIR / 'calibration-anchors.json'
GATE_CALIBRATION_HISTORY = STATE_DIR / 'gate-calibration-history.jsonl'
GATE_CALIBRATION_SUMMARY_JSON = STATE_DIR / 'gate-calibration-summary.json'
GATE_CALIBRATION_SUMMARY_MD = STATE_DIR / 'gate-calibration-summary.md'
OUT_PATH = STATE_DIR / 'gate-calibration.json'

WINDOW_KEYS = ('market_hours', 'off_hours')
THRESHOLD_KEYS = (
    'immediate_alert_urgency',
    'alert_min_minutes_since_last',
    'short_cumulative_value',
    'short_min_minutes_since_last',
    'core_importance',
    'core_min_minutes_since_last',
)


def load_json(path: Path, default: Any = None) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding='utf-8', errors='ignore'))
    except Exception:
        return default


@dataclass
class GateWindowCalibration:
    multipliers: dict[str, float]
    offsets: dict[str, float]
    reasons: list[str]


@dataclass
class GateCalibration:
    version: str
    generatedAt: str
    sourceSummary: dict[str, Any]
    trendSummary: dict[str, Any]
    windows: dict[str, GateWindowCalibration]

    def to_json(self) -> dict[str, Any]:
        return {
            'version': self.version,
            'generatedAt': self.generatedAt,
            'sourceSummary': self.sourceSummary,
            'trendSummary': self.trendSummary,
            'windows': {
                name: asdict(window)
                for name, window in self.windows.items()
            },
        }


def _theme_concentration(candidates: list[dict]) -> float:
    if not candidates:
        return 0.0
    counts: dict[str, int] = {}
    for c in candidates:
        theme = str(c.get('theme', '')).strip().lower()
        if not theme:
            continue
        counts[theme] = counts.get(theme, 0) + 1
    if not counts:
        return 0.0
    return max(counts.values()) / max(len(candidates), 1)


def _suppression_pressure(signal_weights: dict[str, Any]) -> float:
    total_clusters = float(signal_weights.get('totalClusters', 0) or 0)
    suppressed = float(signal_weights.get('suppressedThemes', 0) or 0)
    if total_clusters <= 0:
        return 0.0
    return suppressed / total_clusters


def _anchor_bias(anchors: dict[str, Any]) -> float:
    summary = anchors.get('calibration_summary', {}) if isinstance(anchors, dict) else {}
    over = float(summary.get('over_scored', 0) or 0)
    under = float(summary.get('under_scored', 0) or 0)
    return over - under


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _load_history(limit: int = 5) -> list[dict[str, Any]]:
    if not GATE_CALIBRATION_HISTORY.exists():
        return []
    try:
        lines = GATE_CALIBRATION_HISTORY.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    for raw in lines[-limit:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            items.append(json.loads(raw))
        except Exception:
            continue
    return items


def _trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return 'insufficient-data'
    delta = values[-1] - values[0]
    if abs(delta) < 0.05:
        return 'flat'
    return 'rising' if delta > 0 else 'falling'


def _summarize_trend(history: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    recent_noise = [float(h.get('sourceSummary', {}).get('noisePressure', 0) or 0) for h in history if isinstance(h, dict)]
    recent_bias = [float(h.get('sourceSummary', {}).get('anchorBias', 0) or 0) for h in history if isinstance(h, dict)]
    recent_fresh = [1.0 if h.get('sourceSummary', {}).get('freshnessOk', False) else 0.0 for h in history if isinstance(h, dict)]

    trend = {
        'historyCount': len(history),
        'noisePressureTrend': _trend_direction(recent_noise),
        'anchorBiasTrend': _trend_direction(recent_bias),
        'freshnessTrend': _trend_direction(recent_fresh),
        'noisePressureRising': len(recent_noise) >= 3 and recent_noise[-1] > recent_noise[-2] > recent_noise[-3],
        'anchorBiasPersistentlyHigh': len(recent_bias) >= 3 and all(b >= 2 for b in recent_bias[-3:]),
        'freshnessDegrading': len(recent_fresh) >= 3 and recent_fresh[-1] < recent_fresh[-2] < recent_fresh[-3],
        'judgment': 'steady',
        'reasons': [],
    }

    if trend['noisePressureRising']:
        trend['judgment'] = 'tighten'
        trend['reasons'].append('noise pressure has risen for 3 consecutive calibrations')
    if trend['anchorBiasPersistentlyHigh']:
        trend['judgment'] = 'tighten'
        trend['reasons'].append('anchor bias stays high across the last 3 calibrations')
    if trend['freshnessDegrading']:
        trend['judgment'] = 'tighten'
        trend['reasons'].append('freshness is degrading across the last 3 calibrations')

    if not trend['reasons']:
        trend['reasons'].append('no persistent drift detected; preserve conservative baseline')

    # Include a simple snapshot for explainability.
    trend['current'] = {
        'noisePressure': source_summary.get('noisePressure'),
        'anchorBias': source_summary.get('anchorBias'),
        'freshnessOk': source_summary.get('freshnessOk'),
    }
    return trend


def _compare_payloads(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    if not previous:
        return []
    changes: list[dict[str, Any]] = []
    prev_windows = previous.get('windows', {}) if isinstance(previous, dict) else {}
    curr_windows = current.get('windows', {}) if isinstance(current, dict) else {}
    for window in WINDOW_KEYS:
        prev_win = prev_windows.get(window, {}) if isinstance(prev_windows, dict) else {}
        curr_win = curr_windows.get(window, {}) if isinstance(curr_windows, dict) else {}
        prev_mult = prev_win.get('multipliers', {}) if isinstance(prev_win, dict) else {}
        curr_mult = curr_win.get('multipliers', {}) if isinstance(curr_win, dict) else {}
        for key in THRESHOLD_KEYS:
            pv = float(prev_mult.get(key, 1.0) or 1.0)
            cv = float(curr_mult.get(key, 1.0) or 1.0)
            if abs(cv - pv) >= 0.02:
                changes.append({
                    'window': window,
                    'key': key,
                    'previous': round(pv, 4),
                    'current': round(cv, 4),
                    'delta': round(cv - pv, 4),
                })
    return changes


def _render_summary_md(current: dict[str, Any], previous: dict[str, Any] | None, changes: list[dict[str, Any]]) -> str:
    ss = current.get('sourceSummary', {})
    tr = current.get('trendSummary', {})
    lines = [
        '# Gate Calibration Summary',
        '',
        f"- Generated at: {current.get('generatedAt', '?')}",
        f"- Candidate count: {ss.get('candidateCount', '?')}",
        f"- Noise pressure: {ss.get('noisePressure', '?')} | Theme concentration: {ss.get('themeConcentration', '?')} | Anchor bias: {ss.get('anchorBias', '?')}",
        f"- Freshness OK: {ss.get('freshnessOk', '?')}",
        f"- Trend judgment: {tr.get('judgment', '?')} ({'; '.join(tr.get('reasons', []))})",
        '',
        '## What changed',
    ]
    if not previous:
        lines.append('- Initial calibration snapshot; no previous calibration to diff against.')
    elif not changes:
        lines.append('- No threshold multiplier changed enough to report a material delta.')
    else:
        for ch in changes[:12]:
            direction = 'up' if ch['delta'] > 0 else 'down'
            lines.append(f"- {ch['window']}.{ch['key']}: {ch['previous']} → {ch['current']} ({direction} {abs(ch['delta']):.4f})")
    lines.extend([
        '',
        '## Why',
    ])
    reasons = []
    for w in current.get('windows', {}).values():
        if isinstance(w, dict):
            reasons.extend(w.get('reasons', []))
    if reasons:
        for reason in reasons[:8]:
            lines.append(f'- {reason}')
    else:
        lines.append('- No strong calibration pressure detected.')
    return '\n'.join(lines) + '\n'


def _make_window_calibration(base: dict[str, float], *, noise_pressure: float, concentration: float, anchor_bias: float, freshness_ok: bool, trend: dict[str, Any]) -> GateWindowCalibration:
    multipliers = {k: 1.0 for k in THRESHOLD_KEYS}
    offsets = {k: 0.0 for k in THRESHOLD_KEYS}
    reasons: list[str] = []

    # Conservative selectivity control.
    if noise_pressure >= 0.8 or concentration >= 0.30:
        bump = 1.0 + _clamp((noise_pressure - 0.75) * 0.30 + max(0.0, concentration - 0.25) * 0.50, 0.0, 0.25)
        multipliers['short_cumulative_value'] *= bump
        multipliers['core_importance'] *= bump
        multipliers['short_min_minutes_since_last'] *= 1.0 + min(0.15, (noise_pressure - 0.75) * 0.10)
        multipliers['core_min_minutes_since_last'] *= 1.0 + min(0.15, (noise_pressure - 0.75) * 0.10)
        reasons.append(f'noise pressure={noise_pressure:.2f}, concentration={concentration:.2f} → tighter short/core thresholds')

    # If scoring looks systematically over/under-shifted relative to price moves,
    # nudge the gate a little. This keeps the gate aligned with the scanner.
    if anchor_bias >= 2:
        down = 1.0 + min(0.15, anchor_bias * 0.03)
        multipliers['short_cumulative_value'] *= down
        multipliers['core_importance'] *= down
        reasons.append(f'calibration anchors suggest over-scoring (bias={anchor_bias:+.0f}) → raise gate thresholds')
    elif anchor_bias <= -2:
        down = 1.0 - min(0.12, abs(anchor_bias) * 0.02)
        multipliers['short_cumulative_value'] *= down
        multipliers['core_importance'] *= down
        reasons.append(f'calibration anchors suggest under-scoring (bias={anchor_bias:+.0f}) → lower gate thresholds')

    # If freshness is poor, hold a slightly stronger line to avoid stale noise.
    if not freshness_ok:
        multipliers['short_cumulative_value'] *= 1.08
        multipliers['core_importance'] *= 1.08
        reasons.append('freshness is weak → slight defensive tightening')

    # Emergency alerts stay mostly static, but cooldowns can be a bit more defensive in noisy regimes.
    if noise_pressure >= 0.85:
        multipliers['alert_min_minutes_since_last'] *= 1.10
        reasons.append('noisy regime → extend alert cooldown modestly')

    # Trend judgment: if the last few calibrations all point the same way,
    # apply a tiny extra step so the gate converges instead of oscillating.
    if trend.get('judgment') == 'tighten':
        multipliers['short_cumulative_value'] *= 1.05
        multipliers['core_importance'] *= 1.05
        multipliers['short_min_minutes_since_last'] *= 1.02
        multipliers['core_min_minutes_since_last'] *= 1.02
        if trend.get('noisePressureRising'):
            multipliers['alert_min_minutes_since_last'] *= 1.03
        reasons.append('trend judgment = tighten → apply small convergence step')

    # Apply final clamps so calibration never becomes extreme.
    for k in THRESHOLD_KEYS:
        multipliers[k] = _clamp(multipliers[k], 0.80, 1.35)
        offsets[k] = _clamp(offsets[k], -6.0, 12.0)

    if not reasons:
        reasons.append('no strong calibration pressure detected; preserve defaults')

    return GateWindowCalibration(multipliers=multipliers, offsets=offsets, reasons=reasons)


def build_gate_calibration() -> GateCalibration:
    scan = load_json(SCAN_STATE, {}) or {}
    gate = load_json(GATE_STATE, {}) or {}
    signal_weights = load_json(SIGNAL_WEIGHTS, {}) or {}
    anchors = load_json(CALIBRATION_ANCHORS, {}) or {}

    candidates = scan.get('accumulated', []) or []
    candidate_count = len(candidates)
    total_importance = float(gate.get('totalImportance', 0) or 0)
    total_urgency = float(gate.get('totalUrgency', 0) or 0)
    freshness_ok = not bool(gate.get('dataStale', False))

    noise_pressure = _suppression_pressure(signal_weights)
    concentration = _theme_concentration(candidates)
    anchor_bias = _anchor_bias(anchors)

    # Keep one summary object for transparency.
    source_summary = {
        'candidateCount': candidate_count,
        'totalImportance': round(total_importance, 2),
        'totalUrgency': round(total_urgency, 2),
        'noisePressure': round(noise_pressure, 3),
        'themeConcentration': round(concentration, 3),
        'anchorBias': round(anchor_bias, 2),
        'freshnessOk': freshness_ok,
    }

    history = _load_history(limit=5)
    trend = _summarize_trend(history, source_summary)

    windows = {}
    for window_name in WINDOW_KEYS:
        # Slightly different stance between market/off-hours.
        if window_name == 'market_hours':
            factor = 1.0
        else:
            # Off-hours should be a little more selective.
            factor = 1.03

        cal = _make_window_calibration(
            {},
            noise_pressure=noise_pressure * factor,
            concentration=concentration,
            anchor_bias=anchor_bias,
            freshness_ok=freshness_ok,
            trend=trend,
        )
        windows[window_name] = cal

    return GateCalibration(
        version='2026-04-07.v1',
        generatedAt=datetime.now(timezone.utc).isoformat(),
        sourceSummary=source_summary,
        trendSummary=trend,
        windows=windows,
    )


def save_gate_calibration(path: Path = OUT_PATH) -> GateCalibration:
    previous = _load_history(limit=1)
    previous_payload = previous[-1] if previous else None
    calibration = build_gate_calibration()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = calibration.to_json()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    changes = _compare_payloads(previous_payload, payload)
    summary_md = _render_summary_md(payload, previous_payload, changes)
    GATE_CALIBRATION_SUMMARY_JSON.write_text(json.dumps({
        'generatedAt': calibration.generatedAt,
        'previousAt': previous_payload.get('generatedAt') if isinstance(previous_payload, dict) else None,
        'sourceSummary': calibration.sourceSummary,
        'trendSummary': calibration.trendSummary,
        'changes': changes,
        'summaryPath': str(GATE_CALIBRATION_SUMMARY_MD),
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    GATE_CALIBRATION_SUMMARY_MD.write_text(summary_md, encoding='utf-8')

    GATE_CALIBRATION_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with GATE_CALIBRATION_HISTORY.open('a', encoding='utf-8') as f:
        f.write(json.dumps({
            'generatedAt': calibration.generatedAt,
            'sourceSummary': calibration.sourceSummary,
            'trendSummary': calibration.trendSummary,
            'windows': payload['windows'],
        }, ensure_ascii=False) + '\n')

    return calibration


if __name__ == '__main__':
    cal = save_gate_calibration()
    print(json.dumps(cal.to_json(), indent=2, ensure_ascii=False))
