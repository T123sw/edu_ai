"""Load the trusted teaching workflow before every new answer snapshot."""
import hashlib
from pathlib import Path

from .turn_contracts import AgentFailure


SKILLS_ROOT = Path(__file__).parent / 'skills'
SKILL_NAME = 'teach-current-topic'


def load_teaching_skill(material_type):
    # Resource data can select a known mode, never a filesystem path.
    mode = {'classroom': 'classroom', 'quiz': 'quiz'}.get(material_type, 'document')
    root = SKILLS_ROOT / SKILL_NAME
    try:
        source = (root / 'SKILL.md').read_text(encoding='utf-8')
        if not source.startswith('---\n'):
            raise ValueError('missing frontmatter')
        _, header, body = source.split('---', 2)
        # These local files use plain, single-line frontmatter values, matching
        # the preparation workflow loader; no YAML runtime dependency is needed.
        metadata = dict(line.split(':', 1) for line in header.splitlines() if ':' in line)
        metadata = {key.strip(): value.strip() for key, value in metadata.items()}
        if metadata.get('name') != SKILL_NAME or not metadata.get('description') or not body.strip():
            raise ValueError('invalid teaching skill')
        reference = (root / 'references' / f'{mode}.md').read_text(encoding='utf-8').strip()
        if not reference:
            raise ValueError('empty teaching reference')
    except (OSError, UnicodeError, ValueError) as exc:
        raise AgentFailure('TEACHING_SKILL_UNAVAILABLE') from exc
    version = hashlib.sha256((source + '\n' + mode + '\n' + reference).encode()).hexdigest()
    return {
        'name': SKILL_NAME, 'version': version, 'mode': mode,
        'instructions': f'<teaching_skill name="{SKILL_NAME}" mode="{mode}">\n{body.strip()}\n\n{reference}\n</teaching_skill>',
    }
