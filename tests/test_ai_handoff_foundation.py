from __future__ import annotations

import re
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
REQUIRED = [
    'START_HERE.md',
    'docs/01_reality_check.md',
    'docs/02_end_to_end_workflow.md',
    'docs/ai-handoff-current-repo-config.md',
    'docs/ai-handoff-starter-AGENTS.md',
    'prompts/01_claude_code_requirements.txt',
    'prompts/02_chatgpt_pro_finalize.txt',
    'templates/PROJECT_BRIEF.md',
    'templates/PRD.md',
    'templates/ARCHITECTURE.md',
    'templates/IMPLEMENTATION_PLAN.md',
    'templates/TASK_PACKET.md',
    'templates/VERIFICATION_PLAN.md',
    'templates/DECISIONS.md',
    'templates/NOT_NOW.md',
    'OPEN_QUESTIONS.md',
    'RISKS.md',
    '.agents/skills/requirements-tribunal/SKILL.md',
    '.agents/skills/handoff-packager/SKILL.md',
    'scripts/build_handoff_zip.py',
    'scripts/sync_gstack_plan.sh',
]


def test_ai_handoff_required_files_exist() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).exists()]
    assert missing == []


def test_ai_handoff_truth_docs_have_no_template_placeholders() -> None:
    placeholder = re.compile(r'\{\{[A-Z0-9_]+\}\}')
    docs = list((ROOT / 'templates').glob('*.md')) + [ROOT / 'OPEN_QUESTIONS.md', ROOT / 'RISKS.md', ROOT / 'docs/ai-handoff-current-repo-config.md']
    offenders = []
    for path in docs:
        text = path.read_text(encoding='utf-8')
        if placeholder.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_root_agents_points_to_handoff_overlay_without_replacing_finance_contract() -> None:
    text = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    assert 'OpenClaw-embedded finance subsystem' in text
    assert 'AI Handoff Exoskeleton' in text
    assert 'docs/ai-handoff-current-repo-config.md' in text
    assert 'docs/ai-handoff-starter-AGENTS.md' in text
