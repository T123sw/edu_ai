"""Report rendering source for version-bound paragraph anchors.

Keep rendering parity with courseMaterialToMarkdown/normalizeKnowledgeMarkdown.
Offsets count Unicode code points; the fingerprint detects rendering drift and
is not an authorization token. Access and exact versions are checked separately.
"""
import re
from fastapi import HTTPException


def report_markdown(material):
    content = material.get('content')
    nested = content if isinstance(content, dict) else {}
    candidates = [material.get(k) for k in ('final_markdown', 'content', 'content_markdown', 'markdown', 'report', 'report_content', 'text')]
    candidates += [nested.get(k) for k in ('content_markdown', 'markdown', 'report', 'report_content', 'content', 'text')]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value
    report = material.get('report') if isinstance(material.get('report'), dict) else {}
    text = lambda value: str(value).strip() if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ''
    join = lambda parts: '\n\n'.join(filter(None, parts))
    sections = report.get('mainContent', material.get('mainContent', []))
    body = []
    for section in sections if isinstance(sections, list) else []:
        if not isinstance(section, dict):
            section = {}
        subs = [join(['### ' + (text(s.get('title')) or '小节'), text(s.get('content'))])
                for s in section.get('subsections', []) if isinstance(s, dict)]
        body.append(join(['## ' + (text(section.get('title')) or '章节'), text(section.get('content')), join(subs)]))
    def listing(title, values):
        items = [text(v) for v in values] if isinstance(values, list) else []
        items = [v for v in items if v]
        return '## ' + title + '\n\n' + '\n'.join('- ' + v for v in items) if items else ''
    summary = text(report.get('summary')) or material.get('summary', '')
    introduction, conclusions = text(report.get('introduction')), text(report.get('conclusions'))
    parts = [summary, '## 引言\n\n' + introduction if introduction else '', join(body),
             listing('关键结论', report.get('keyFindings')), '## 结论\n\n' + conclusions if conclusions else '',
             listing('建议', report.get('recommendations'))]
    if not any(parts):
        return '# ' + (material.get('title') or material.get('material_id', '')) + '\n\n当前资源暂无可直接渲染的 Markdown 内容。'
    return join(['# ' + (text(report.get('title')) or material.get('title') or material.get('topic') or material.get('material_id', '')), *parts])


def normalize_report(source):
    source = re.sub(r'\r\n?', '\n', source)
    source = re.sub(r'<br\s*/?>', '\n', source, flags=re.I)
    source = re.sub(r'</?(?:u|ins)>', '', source, flags=re.I)
    for tag, delimiter in [('sub', '~'), ('sup', '^')]:
        source = re.sub(fr'<{tag}>([\s\S]*?)</{tag}>', lambda m: delimiter + m[1] + delimiter, source, flags=re.I)
    source = re.sub(r'''<img\b[^>]*?src=["']([^"']+)["'][^>]*?alt=["']([^"']*)["'][^>]*>''', lambda m: f'![{m[2]}]({m[1]})', source, flags=re.I)
    source = re.sub(r'''<img\b[^>]*?alt=["']([^"']*)["'][^>]*?src=["']([^"']+)["'][^>]*>''', lambda m: f'![{m[1]}]({m[2]})', source, flags=re.I)
    source = re.sub(r'''<img\b[^>]*?src=["']([^"']+)["'][^>]*>''', lambda m: f'![]({m[1]})', source, flags=re.I)
    source = re.sub(r'\\\[([\s\S]*?)\\\]', lambda m: '\n$$\n' + m[1].strip() + '\n$$\n', source)
    source = re.sub(r'\\\((.+?)\\\)', lambda m: '$' + m[1].strip() + '$', source)
    labels = dict(abstract='摘要', note='说明', info='说明', tip='提示', success='要点', question='思考', warning='注意', danger='警告', failure='易错点', example='示例', quote='引用')
    output, in_fence = [], False
    for line in source.split('\n'):
        if re.match(r'^\s*```', line):
            in_fence = not in_fence
        match = re.match(r'''^\s*!!!\s+([\w-]+)(?:\s+["']?(.+?)["']?)?\s*$''', line, flags=re.I) if not in_fence else None
        output.append('> **' + ((match[2] or '').strip() or labels.get(match[1].lower(), '说明')) + '**' if match else line)
    return re.sub(r'\n{4,}', '\n\n\n', '\n'.join(output)).strip()


def report_fingerprint(source):
    value = 2166136261
    for byte in source.encode('utf-8'):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f'{value:08x}'


def anchored_report(material, block_id, max_chars):
    match = re.fullmatch(r'report-v1:(\d+):(\d+):([0-9a-f]{8})', block_id)
    source = normalize_report(report_markdown(material))
    if not match or match[3] != report_fingerprint(source):
        raise HTTPException(409, '报告段落已变化，请重新选择后提问')
    start, end = int(match[1]), int(match[2])
    if not 0 <= start < end <= len(source):
        raise HTTPException(409, '报告段落位置无效，请重新选择后提问')
    focus = source[start:end]
    # Put the focus first: trimming surrounding prose must not discard it.
    context = source[max(0, start - 500):start] + '\n' + source[end:end + 1000]
    result = '当前引用段落（Markdown 原文）：\n' + focus + '\n前后文：\n' + context
    return {'excerpt': result[:max_chars], 'resolved_locator': {'kind': 'document', 'block_id': block_id},
            'location_quality': 'exact', 'anchor_verified': True, 'truncated': len(result) > max_chars}
