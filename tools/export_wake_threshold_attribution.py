#!/usr/bin/env python3
"""Export latest wake-vs-threshold attribution for reviewer visibility."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINANCE = Path(__file__).resolve().parents[1]
STATE = FINANCE / 'state'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'wake-threshold-attribution.json'


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def attribution(gate: dict[str, Any], wake: dict[str, Any], dispatch: dict[str, Any], orchestrator: dict[str, Any]) -> dict[str, Any]:
    bridge = gate.get('legacyThresholdDispatch') if isinstance(gate.get('legacyThresholdDispatch'), dict) else {}
    bridge_present = bool(bridge)
    wake_class = wake.get('wake_class') or dispatch.get('wake_class')
    report_class = orchestrator.get('report_class') if isinstance(orchestrator, dict) else None
    if dispatch.get('dispatched') is True and wake_class == 'ISOLATED_JUDGMENT_WAKE':
        source = 'canonical_wake_dispatch'
    elif bridge_present and bridge.get('dispatched') is True:
        source = 'legacy_threshold_bridge'
    elif wake_class == 'PACKET_UPDATE_ONLY':
        source = 'packet_update_only'
    elif gate.get('shouldSend') is False:
        source = 'hold_no_send'
    else:
        source = 'blocked_or_failed'
    return {
        'attribution': source,
        'gate_evaluated_at': gate.get('evaluatedAt'),
        'gate_should_send': gate.get('shouldSend'),
        'gate_recommended_report_type': gate.get('recommendedReportType'),
        'wake_class': wake_class,
        'wake_dispatch_action': dispatch.get('action'),
        'wake_dispatched': dispatch.get('dispatched'),
        'legacy_threshold_bridge_present': bridge_present,
        'legacy_threshold_bridge_status': bridge.get('status') if bridge_present else None,
        'legacy_threshold_bridge_action': bridge.get('action') if bridge_present else None,
        'legacy_threshold_bridge_dispatched': bridge.get('dispatched') if bridge_present else None,
        'report_class': report_class,
    }


def main() -> int:
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pass',
        'latest': attribution(
            load_json(STATE / 'report-gate-state.json', {}) or {},
            load_json(STATE / 'latest-wake-decision.json', {}) or {},
            load_json(STATE / 'wake-dispatch-state.json', {}) or {},
            load_json(STATE / 'report-orchestrator-input.json', {}) or {},
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'attribution': report['latest']['attribution'], 'out': str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
