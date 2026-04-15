#!/usr/bin/env python3
"""Report quality gate — validates renderer output before Discord delivery.
Run after renderer produces text, before sending to user.
Returns exit code 0 if report passes, 1 if rejected.
Rejected reports are logged to state/rejected-reports/.
"""
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from atomic_io import atomic_write_json

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
REJECTED_DIR = FINANCE / 'state' / 'rejected-reports'


def check_none_values(text: str) -> list[str]:
    """Detect raw None/null values that indicate API failures leaked into output."""
    issues = []
    # Match patterns like "涨跌=None" or "pct=None" or "None%"
    none_matches = re.findall(r'(?:=|: ?)None[%\s,|]', text)
    if none_matches:
        issues.append(f"发现 {len(none_matches)} 个 None 值泄漏到报告中")
    # Match "null" in data fields
    null_matches = re.findall(r'(?:=|: ?)null[%\s,|]', text, re.IGNORECASE)
    if null_matches:
        issues.append(f"发现 {len(null_matches)} 个 null 值泄漏到报告中")
    return issues


def check_corrupted_numbers(text: str) -> list[str]:
    """Detect LLM text injection into numeric fields (like 'pct=-1.主模型32')."""
    issues = []
    # Numbers with Chinese/non-numeric characters injected
    corrupt = re.findall(r'(?:pct|change|涨跌幅|价格)[\s=:]*-?\d+\.[\u4e00-\u9fff]+', text)
    if corrupt:
        issues.append(f"发现数值污染: {corrupt[:3]}")
    return issues


def check_timestamp_freshness(text: str, now: datetime | None = None) -> list[str]:
    """Check if report contains timestamps that are too old."""
    issues = []
    now = now or datetime.now(timezone.utc)
    # Match ISO timestamps or date patterns without pinning the validator to one year.
    dates = re.findall(r'\b20\d{2}-\d{2}-\d{2}\b', text)
    today_str = now.strftime('%Y-%m-%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')

    old_dates = [d for d in dates if d < yesterday_str]
    if old_dates and len(old_dates) > len(dates) * 0.5:
        issues.append(f"超过 50% 的日期引用是两天前或更早: {set(old_dates)}")
    return issues


def check_report_length(text: str) -> list[str]:
    """Report should have reasonable length."""
    issues = []
    if len(text.strip()) < 50:
        issues.append(f"报告过短 ({len(text.strip())} 字符), 可能是空报告或错误输出")
    if len(text.strip()) > 10000:
        issues.append(f"报告过长 ({len(text.strip())} 字符), 可能包含 debug 输出")
    return issues


def check_internal_diagnostics(text: str) -> list[str]:
    """Block internal diagnostic leaking into user-facing output."""
    issues = []
    blocked = [
        'shouldSend=false', 'recommendedReportType=hold', 'gate_decision',
        'HEARTBEAT_OK', 'NO_REPLY', 'Silent exit', 'Silently ended',
    ]
    for kw in blocked:
        if kw in text:
            issues.append(f"内部诊断信息泄漏: '{kw}'")
    return issues


def check_language(text: str) -> list[str]:
    """Soft check: warn if report appears to be all-English when it should be Chinese."""
    issues = []
    # Count Chinese characters vs ASCII
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    ascii_chars = len(re.findall(r'[a-zA-Z]', text))
    total = chinese_chars + ascii_chars
    if total > 100 and chinese_chars < total * 0.1:
        issues.append(f"报告疑似全英文输出 (中文占比 {chinese_chars}/{total} = {chinese_chars/total:.0%})")
    return issues


def validate(text: str) -> tuple[bool, list[str]]:
    """Run all checks. Returns (passed, issues)."""
    all_issues = []
    all_issues.extend(check_none_values(text))
    all_issues.extend(check_corrupted_numbers(text))
    all_issues.extend(check_timestamp_freshness(text))
    all_issues.extend(check_report_length(text))
    all_issues.extend(check_internal_diagnostics(text))
    all_issues.extend(check_language(text))

    # Hard fail on critical issues
    critical = [i for i in all_issues if any(kw in i for kw in ['None 值', 'null 值', '数值污染', '内部诊断'])]
    # Warnings don't block
    warnings = [i for i in all_issues if i not in critical]

    passed = len(critical) == 0
    return passed, critical + warnings


def main():
    if len(sys.argv) < 2:
        # Read from stdin
        text = sys.stdin.read()
    else:
        text = Path(sys.argv[1]).read_text()

    passed, issues = validate(text)

    if passed and not issues:
        print("✅ 质量门控通过")
        sys.exit(0)
    elif passed and issues:
        print("⚠️ 质量门控通过（有警告）:")
        for i in issues:
            print(f"  - {i}")
        sys.exit(0)
    else:
        print("❌ 质量门控拒绝:")
        for i in issues:
            print(f"  - {i}")
        # Archive rejected report
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        rejected_path = REJECTED_DIR / f'{ts}-rejected.json'
        atomic_write_json(rejected_path, {
            'rejected_at': datetime.now(timezone.utc).isoformat(),
            'issues': issues,
            'text_preview': text[:2000],
        })
        print(f"  → 已归档到 {rejected_path}")
        sys.exit(1)


if __name__ == '__main__':
    main()
