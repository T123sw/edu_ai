"""Read uploaded content before intent normalization, one durable chunk per step."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import Field, ValidationError
from .schemas import Contract, ShortText, SourcePolicy
from .research_agent import ResearchError
from .adapters.documents import DocumentUnreadable
from .intake_references import document_passages, reference_id, with_references

CHUNK_CHARS = 12000


class InputPoint(Contract):
    text: ShortText
    source_quote: str = Field(default="", max_length=400, description="使用 source_ref 时由程序回填，无需抄写")
    source_ref: str | None = Field(default=None, max_length=100, description="从 document.passages 选择 source_ref")


class DocumentUnderstanding(Contract):
    kind: Literal['job_description', 'learner_background', 'syllabus', 'learning_material', 'other']
    summary: ShortText
    relevant_points: tuple[InputPoint, ...] = Field(default=(), max_length=6)
    material_gaps: tuple[ShortText, ...] = Field(default=(), max_length=8)


def effective_request(request, checkpoint):
    """A model can narrow network scope, never relax the submitted restriction."""
    inferred = (checkpoint.get('brief') or {}).get('source_policy') or {}
    mode = 'uploaded_only' if request.source_policy.mode == 'uploaded_only' or inferred.get('mode') == 'uploaded_only' else request.source_policy.mode
    return request.model_copy(update={'source_policy': SourcePolicy(mode=mode)})


def validate_brief(brief, request, documents):
    texts = [request.goal, *request.requested_changes]
    quotes = {doc['document_id']: [p['source_quote'] for part in doc['parts'] for p in part['relevant_points']] for doc in documents}
    for requirement in brief.requirements:
        if requirement.source_document_id:
            if requirement.source_quote not in quotes.get(requirement.source_document_id, []):
                raise ValueError(f'{requirement.requirement_id}: 附件引用不匹配；使用 input_documents 对应要点的 source_ref，不从摘要编写 source_quote')
        elif not requirement.source_quote.strip() or not any(requirement.source_quote in text for text in texts):
            raise ValueError(f'{requirement.requirement_id}: 要求原话必须在本次用户需求中实际出现；source_quote={requirement.source_quote!r} 不匹配。请逐字截取用户原话子串，保留分号、句号等标点；附件依据需指定 source_document_id')
    if brief.source_policy and brief.source_policy.mode == 'uploaded_only':
        if not request.uploads:
            raise ValueError('仅使用上传资料需要至少一份附件')
        if request.source_policy.mode != 'uploaded_only' and (not brief.source_policy_quote or not any(brief.source_policy_quote in text for text in texts)):
            raise ValueError('禁止网络的要求必须来自用户本次原话，不能来自附件指令')
    if request.overrides.depth and brief.depth != request.overrides.depth:
        raise ValueError('必须遵守本次明确设置的学习深度')


def understand_next_document(stages, context, checkpoint, request):
    documents = with_references(checkpoint.get('input_documents', []))
    # Reauthorize completed references on resume as well as new input.
    for ref in request.uploads:
        stages.documents.authorize(context.owner_user_id, ref)
    pending = next((ref for ref in request.uploads if not any(
        doc['document_id'] == ref.document_id and doc['version'] == ref.version and doc['complete'] for doc in documents)), None)
    if pending is None:
        return {**checkpoint, 'input_documents': documents}, False
    parsed = stages.documents.parse(context.owner_user_id, pending)
    if parsed['defects'] and pending.usage in ('auto', 'primary', 'coverage'):
        raise DocumentUnreadable('CORE_SOURCE_UNREADABLE', parsed['defects'])
    text = parsed['content']
    if not text.strip():
        raise DocumentUnreadable('DOCUMENT_EMPTY')
    metadata = stages.documents.authorize(context.owner_user_id, pending)
    doc = next((d for d in documents if d['document_id'] == pending.document_id), None)
    if doc is None:
        doc = {'document_id': pending.document_id, 'version': pending.version, 'filename': metadata['filename'],
               'source_hash': parsed['source_hash'], 'characters': len(text), 'offset': 0,
               'complete': False, 'defects': parsed['defects'], 'parts': []}
        documents.append(doc)
    if doc['source_hash'] != parsed['source_hash']:
        raise PermissionError('DOCUMENT_VERSION_CHANGED')
    offset = doc['offset']
    content = text[offset:offset + CHUNK_CHARS]
    spans = document_passages(doc, offset, content)
    model = stages.agent_factory(context, request, checkpoint).model
    tool = {'type': 'function', 'function': {'name': 'record_input_document',
            'description': '根据当前文件原文理解用途和与学习需求相关的信息，要点使用 document.passages 的 source_ref，程序回填原文；资料缺失写入 material_gaps。',
            'parameters': DocumentUnderstanding.model_json_schema()}}
    remaining = (datetime.fromisoformat(context.deadline) - datetime.now(timezone.utc)).total_seconds()
    name, raw = model.decide({'phase': 'input_document', 'goal': request.goal,
        'document': {'document_id': pending.document_id, 'filename': doc['filename'], 'offset': offset,
                     'total_chars': len(text), 'content': content, 'passages': spans},
        'last_error': checkpoint.get('input_document_error')}, [tool], timeout=max(1, min(90, remaining)))
    try:
        if name != 'record_input_document': raise ValueError('必须调用文件理解工具')
        analysis = DocumentUnderstanding.model_validate(raw)
        registry = {span['source_ref']: span['text'] for span in spans}
        points = []
        for index, point in enumerate(analysis.relevant_points):
            if point.source_ref:
                if point.source_ref not in registry:
                    raise ValueError(f'relevant_points[{index}]: 未知 source_ref={point.source_ref}；只选当前 document.passages 的 ID')
                point = point.model_copy(update={'source_quote': registry[point.source_ref]})
            elif not point.source_quote.strip() or point.source_quote not in content:
                raise ValueError(f'relevant_points[{index}]: 引用不在当前原文中；请改用 document.passages 的 source_ref，勿改写或拼接原文')
            points.append(point.model_copy(update={'source_ref': reference_id(doc, offset, point.source_quote)}))
        analysis = analysis.model_copy(update={'relevant_points': tuple(points)})
    except (ValueError, ValidationError) as exc:
        retries = checkpoint.get('input_document_retries', 0) + 1
        if retries > 2: raise ResearchError('INPUT_DOCUMENT_INVALID', '附件理解未通过原文校验') from exc
        return {**checkpoint, 'input_documents': documents, 'input_document_retries': retries,
                'input_document_error': str(exc)[:1000]}, True
    stages.documents.authorize(context.owner_user_id, pending)
    doc['parts'].append({'offset': offset, **analysis.model_dump(mode='json')})
    doc['offset'] += len(content)
    doc['complete'] = doc['offset'] >= len(text)
    checkpoint = {**checkpoint, 'input_documents': documents}
    checkpoint.pop('input_document_error', None)
    checkpoint.pop('input_document_retries', None)
    return checkpoint, True
