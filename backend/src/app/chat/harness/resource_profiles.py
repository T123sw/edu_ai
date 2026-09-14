"""Resource contracts share the exact application Skill text used by the planner."""
from pathlib import Path

SKILL = Path(__file__).parent / 'skills' / 'edu-resources' / 'SKILL.md'


def resource_contract(kind: str, stage: str = 'final') -> str:
    if kind == 'report':
        return ''
    text = SKILL.read_text(encoding='utf-8')
    accuracy = text.split('## 通用准确性标准\n', 1)[1].split('\n## ', 1)[0].strip()
    if stage == 'organization':
        return text.split('## 内容组织阶段\n', 1)[1].split('\n## ', 1)[0].strip() + '\n\n' + accuracy
    marker = '### ' + kind + '\n'
    if marker not in text:
        raise ValueError('unknown_resource_contract')
    section = text.split(marker, 1)[1].split('\n### ', 1)[0].split('\n## ', 1)[0].strip()
    phase = '#### 方案阶段\n' if stage == 'plan' else '#### 成品阶段\n'
    return (section.split(phase, 1)[1].split('\n#### ', 1)[0].strip() if phase in section else section) + '\n\n' + accuracy
