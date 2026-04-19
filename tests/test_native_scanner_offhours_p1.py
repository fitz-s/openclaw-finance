from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')


def test_native_scanner_offhours_report_carries_aperture_metadata() -> None:
    out_dir = FINANCE / 'state' / 'test-native-offhours-buffer'
    report = FINANCE / 'state' / 'test-native-offhours-report.json'
    proc = subprocess.run([
        sys.executable,
        'scripts/native_scanner_offhours.py',
        '--scan-time', '2026-04-18T16:00:00Z',
        '--output-dir', str(out_dir),
        '--report', str(report),
        '--skip-downstream',
    ], cwd=str(FINANCE), capture_output=True, text=True, timeout=60)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(report.read_text(encoding='utf-8'))
    assert payload['calendar_aware_offhours'] is True
    assert payload['session_aperture']['session_class'] == 'weekend_aperture'
    assert payload['window'] == 'weekend'
