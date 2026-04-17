from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path('/Users/leofitz/.openclaw/workspace/finance/tools')
sys.path.insert(0, str(TOOLS))

from export_ingestion_fabric_closeout import build_closeout


def test_ingestion_fabric_closeout_tracks_all_phases() -> None:
    report = build_closeout()
    assert report['contract'] == 'ingestion-fabric-closeout-v1'
    assert report['phase_summary']['phase_count'] == 14
    assert 13 in report['phase_summary']['pending_phases'] or report['phase_summary']['all_completed'] is True
    assert report['no_execution'] is True


def test_ingestion_fabric_closeout_has_monitoring_and_rollback() -> None:
    report = build_closeout()
    assert 'source_health_status' in report['monitoring']
    assert 'reader_bundle_has_slice_index' in report['monitoring']
    assert report['rollback']['fallback_primary'] == 'complete_readable_discord_primary_report'
    assert report['rollback']['forbidden_fallback'] == 'route_card_only_primary'
    assert 'FINANCE_FOLLOWUP_SLICE_REHYDRATION_ENABLED' in report['rollback']['disable_flags']


def test_ingestion_fabric_closeout_records_parent_runtime_residual_risk() -> None:
    report = build_closeout()
    text = json.dumps(report, ensure_ascii=False)
    assert 'Parent market-ingest runtime is not mutated' in text
    assert 'Active Discord thread listener' in text


def test_ingestion_fabric_closeout_has_orr_and_operational_handoff() -> None:
    report = build_closeout()
    assert report['orr_readiness_checklist']['runbook_required_before_parent_cutover'] is True
    assert report['rollout_monitoring']['strategy'] == 'feature_flagged_shadow_then_canary_then_parent_activation'
    assert 'stale_reuse_guard' in report['rollout_monitoring']['go_no_go_metrics']
    assert report['operational_handoff']['runbook_required'] is True
