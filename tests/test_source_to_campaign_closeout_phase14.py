from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path('/Users/leofitz/.openclaw/workspace/finance/tools')
sys.path.insert(0, str(TOOLS))

from export_source_to_campaign_closeout import campaign_metrics, followup_metrics, iv_metrics, phase_summary, raw_snippet_export_count


def test_closeout_report_computes_monitoring_metrics(tmp_path) -> None:
    reviewer = tmp_path / 'reviewer'
    reviewer.mkdir()
    (reviewer / 'packet.json').write_text(json.dumps({'raw_snippet_included': False}), encoding='utf-8')
    assert raw_snippet_export_count(reviewer) == 0
    assert campaign_metrics({'campaigns': [{'source_diversity': 2, 'known_unknowns': [{}]}, {'source_diversity': 0, 'known_unknowns': []}]})['source_diversity_per_campaign'] == 1.0
    assert followup_metrics({'status': 'pass', 'insufficient_data': True, 'evidence_slice_coverage': {}})['followup_grounding_failure_rate'] == 1.0
    assert iv_metrics({'status': 'pass', 'summary': {'symbol_count': 4, 'stale_or_unknown_chain_count': 2, 'proxy_only_count': 4}})['iv_signal_staleness_rate'] == 0.5
    assert phase_summary({'phases': [{'status': 'completed'}, {'status': 'pending', 'phase': 2}]})['pending'] == [2]
