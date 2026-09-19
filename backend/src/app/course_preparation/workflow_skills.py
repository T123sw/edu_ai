"""Versioned, stage-scoped workflows loaded by the native Harness skill plugins."""
import hashlib
from pathlib import Path

SKILLS_ROOT = Path(__file__).parent / 'skills'
PHASE_SKILLS = {
    'learning_path': 'build-learning-path',
    'input_document': 'understand-learning-request',
    'intent': 'understand-learning-request',
    'research': 'research-learning-sources',
    'plan': 'plan-learning-path',
    'route_adjustment': 'plan-learning-path',
    'review': 'review-learning-path',
    'research_nodes': 'review-learning-path',
}
HARNESS_PHASES = frozenset(PHASE_SKILLS)


def load_workflow_skill(phase):
    name = PHASE_SKILLS[phase]
    text = (SKILLS_ROOT / name / 'SKILL.md').read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        raise ValueError('WORKFLOW_SKILL_INVALID: missing frontmatter')
    _, header, body = text.split('---', 2)
    if f'name: {name}' not in (line.strip() for line in header.splitlines()) or not body.strip():
        raise ValueError('WORKFLOW_SKILL_INVALID: invalid name or empty instructions')
    return {'name': name, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
            'text': text, 'body': body.strip()}


def skill_is_loaded(messages, skill):
    """Require the full native instruction block, not just a catalog entry."""
    for message in messages:
        content = message.get('content', '')
        if isinstance(content, list):
            content = '\n'.join(block.get('text', '') for block in content if block.get('type') == 'text')
        if (isinstance(content, str) and f'<skill_content name="{skill["name"]}">' in content
                and '<skill_instructions>\n' + skill['body'] + '\n</skill_instructions>' in content):
            return True
    return False
