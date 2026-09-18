"""Snapshot the single intake workflow for native Harness loading and audit."""
import hashlib
from pathlib import Path

SKILL_NAME = 'understand-learning-request'
SKILL_PATH = Path(__file__).parent / 'skills' / SKILL_NAME / 'SKILL.md'
INTAKE_PHASES = frozenset(('input_document', 'intent'))


def load_intake_skill():
    text = SKILL_PATH.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        raise ValueError('INTAKE_SKILL_INVALID: missing frontmatter')
    _, header, body = text.split('---', 2)
    if f'name: {SKILL_NAME}' not in (line.strip() for line in header.splitlines()) or not body.strip():
        raise ValueError('INTAKE_SKILL_INVALID: invalid name or empty instructions')
    return {'name': SKILL_NAME, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
            'text': text, 'body': body.strip()}


def skill_is_loaded(messages, skill):
    """The native plugin adds an instruction block, not just a catalog entry."""
    for message in messages:
        content = message.get('content', '')
        if isinstance(content, list):
            content = '\n'.join(block.get('text', '') for block in content if block.get('type') == 'text')
        if (isinstance(content, str) and f'<skill_content name="{skill["name"]}">' in content
                and '<skill_instructions>\n' + skill['body'] + '\n</skill_instructions>' in content):
            return True
    return False
