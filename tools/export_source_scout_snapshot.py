#!/usr/bin/env python3
"""Export source scout candidates into reviewer-visible OpenClaw runtime docs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FINANCE = Path(__file__).resolve().parents[1]
SCRIPTS = FINANCE / 'scripts'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'source-scout-candidates.json'
sys.path.insert(0, str(SCRIPTS))

from source_scout import build_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Export review-only source scout candidates for remote reviewers.')
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    report['export_boundary'] = 'reviewer-visible metadata only; no source activation and no raw vendor payloads'
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'candidate_count': report['summary']['candidate_count'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
