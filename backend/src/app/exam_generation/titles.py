"""Stable display titles from the original request and frozen source names."""
import re

DEFAULT_REQUIREMENTS = {
    '保持原卷题型、题数和考点，生成一套新的模拟试卷。',
    '根据上传的学习资料，生成一套覆盖主要知识点的习题。',
}


def paper_title(request, sources=()):
    requirement = str(request.get('requirement') or '').strip()
    if requirement and requirement not in DEFAULT_REQUIREMENTS:
        return requirement
    mimic = request.get('mode') == 'mimic'
    sources = sources or []
    selected = [s for s in sources if s.get('role') == 'template'] if mimic else sources
    names = []
    for source in selected:
        filename = str(source.get('filename') or '').replace('\\', '/').rsplit('/', 1)[-1]
        name = re.sub(r'\.(pdf|txt|md|markdown|docx?|pptx?|png|jpe?g)$', '', filename, flags=re.I)
        name = ' '.join(re.sub(r'[\x00-\x1f\x7f]', ' ', name).split()).strip(' .')
        if name:
            names.append(name)
    suffix = '模拟试卷' if mimic else '练习题'
    if not names:
        return suffix
    name = names[0]
    if len(name) > 60:
        name = name[:59] + '…'
    count = f'等 {len(sources)} 份资料' if not mimic and len(sources) > 1 else ''
    return f'{name}{count} · {suffix}'
