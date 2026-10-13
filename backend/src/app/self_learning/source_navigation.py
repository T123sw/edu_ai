"""Version-local question resolution and bounded report passage retrieval."""
import re
from fastapi import HTTPException
from .report_document import normalize_report, report_markdown, report_fingerprint, anchored_report


def quiz_question(material, locator):
    if material.get('material_type') != 'quiz':
        raise HTTPException(409, '题目位置不属于习题资料')
    content = material.get('content')
    questions = material.get('questions') or (content.get('questions') if isinstance(content, dict) else []) or []
    index = locator.get('question_index')
    if type(index) is not int or not 0 <= index < len(questions) or not isinstance(questions[index], dict):
        raise HTTPException(409, '题目位置无效，请重新打开习题')
    return questions[index]


def search_report(material, query, max_chars):
    """Lexical paragraph retrieval only; no match is explicitly reported."""
    source = normalize_report(report_markdown(material))
    words = re.findall(r'[a-zA-Z0-9_]{2,}|[\u4e00-\u9fff]+', query.lower())
    terms = set()
    for word in words:
        if re.search(r'[\u4e00-\u9fff]', word):
            terms.update(word[i:i + 2] for i in range(len(word) - 1))
        else:
            terms.add(word)
    terms -= {'什么', '怎么', '如何', '这个', '这段', '请问', '解释', '一下', '文中', '资料', '内容', '为什么', '为何'}
    candidates = []
    for match in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', source):
        passage = match.group().lower()
        score = sum(len(term) for term in terms if term in passage)
        if score:
            candidates.append((score, match.start(), match.end()))
    if not candidates:
        return None
    _, start, end = max(candidates, key=lambda item: (item[0], -item[1]))
    # A long paragraph is bounded around the first matching term.
    if end - start > max_chars // 2:
        passage = source[start:end].lower()
        hit = min(passage.index(term) for term in terms if term in passage)
        start += max(0, hit - 200)
        end = min(end, start + max(1, max_chars // 2))
    block_id = f'report-v1:{start}:{end}:{report_fingerprint(source)}'
    return {**anchored_report(material, block_id, max_chars), 'retrieval': 'lexical_passage', 'search_matched': True}
