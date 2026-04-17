from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_discord_campaign_board_package import build_package


def _board() -> dict:
    return {
        'discord_live_board_markdown': 'Finance｜Live Board\n\n1) TSLA risk | review',
        'discord_scout_board_markdown': 'Finance｜Peacetime Board\n\n1) Scout | accumulating',
        'discord_risk_board_markdown': 'Finance｜Risk / Undercurrent Board\n\n1) Risk | review',
    }


def _threads() -> dict:
    return {'status': 'pass', 'thread_count': 1, 'thread_is_ui_not_memory': True, 'threads': {'thread:a': {'thread_status': 'unbound'}}}


def _report() -> dict:
    return {'discord_primary_markdown': 'Finance｜资本议程\n\nFact\n- x\n\nInterpretation\n- y', 'discord_thread_seed_markdown': 'R1｜深挖入口'}


def test_board_package_contains_live_scout_risk_and_fallback() -> None:
    package = build_package(campaign_board=_board(), campaign_threads=_threads(), report_envelope=_report(), safety={'status': 'pass'}, generated_at='2026-04-17T00:00:00Z')
    assert package['status'] == 'pass'
    assert package['live_board_markdown'].startswith('Finance｜Live Board')
    assert package['scout_board_markdown'].startswith('Finance｜Peacetime Board')
    assert package['risk_board_markdown'].startswith('Finance｜Risk')
    assert package['primary_fallback_markdown'].startswith('Finance｜资本议程')


def test_board_package_has_no_external_side_effects() -> None:
    package = build_package(campaign_board=_board(), campaign_threads=_threads(), report_envelope=_report(), safety={'status': 'pass'})
    assert package['no_external_side_effects'] is True
    assert package['no_discord_api_calls'] is True
    assert package['no_thread_creation'] is True
    assert package['no_cron_or_gateway_mutation'] is True
    assert package['no_execution'] is True


def test_board_package_preserves_primary_fallback_when_boards_missing() -> None:
    package = build_package(campaign_board={}, campaign_threads={}, report_envelope=_report(), safety={'status': 'pass'})
    assert package['status'] == 'pass'
    assert package['live_board_markdown'] == ''
    assert package['primary_fallback_markdown'].startswith('Finance｜资本议程')
    assert package['delivery_instructions']['fallback_floor'] == 'primary_fallback_markdown_not_route_card_only'


def test_board_package_references_thread_registry_but_does_not_create_threads() -> None:
    package = build_package(campaign_board=_board(), campaign_threads=_threads(), report_envelope=_report(), safety={'status': 'pass'})
    assert package['thread_registry_summary']['thread_is_ui_not_memory'] is True
    assert package['delivery_instructions']['thread_creation'] == 'parent_runtime_only'


def test_board_package_cli_rejects_unsafe_output(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / 'finance_discord_campaign_board_package.py'), '--out', str(tmp_path / 'package.json')],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert 'unsafe_out_path' in result.stdout
