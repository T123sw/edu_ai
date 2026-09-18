"""Compatibility entrypoint for the original intake Skill."""
from .workflow_skills import SKILLS_ROOT, load_workflow_skill, skill_is_loaded

SKILL_NAME = 'understand-learning-request'
SKILL_PATH = SKILLS_ROOT / SKILL_NAME / 'SKILL.md'
INTAKE_PHASES = frozenset(('input_document', 'intent'))


def load_intake_skill():
    return load_workflow_skill('intent')
