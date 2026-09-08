"""Private iterative previews. Only saving a shown draft creates a new document."""
from copy import deepcopy
from difflib import SequenceMatcher
import json
import re
from uuid import uuid4

from .adapters import apply_edits, validate, content_updates, editable_paths
from .storage import RevisionConflict


def readable_content(content):
    if isinstance(content, str):
        return content
    labels = {'questions': '习题', 'stem': '题目', 'answer': '答案', 'explanation': '解析', 'options': '选项',
              'title': '标题', 'objectives': '教学目标', 'process': '教学过程', 'front': '正面', 'back': '背面',
              'cards': '闪卡', 'summary': '说明', 'children': '分支', 'root': '主题', 'text': '内容'}
    def render(value, depth=2):
        if isinstance(value, dict):
            return '\n\n'.join('#' * min(depth, 6) + ' ' + labels.get(k, k) + '\n\n' + render(v, depth+1)
                               for k, v in value.items() if k not in {'id', 'audioId', 'audioUrl'})
        if isinstance(value, list):
            return '\n\n'.join(render(v, depth) for v in value)
        return str(value) if value is not None else ''
    return render(content)


def blocks(text):
    result, current, fence = [], [], None
    for line in text.splitlines(keepends=True):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            marker = match[1][0]
            fence = None if fence == marker else marker if fence is None else fence
        current.append(line)
        if not line.strip() and fence is None:
            result.append(''.join(current)); current = []
    if current:
        result.append(''.join(current))
    return result


def segments(original, updated):
    before, after = blocks(readable_content(original)), blocks(readable_content(updated))
    operations = SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
    result = []
    for index, (kind, a, b, c, d) in enumerate(operations):
        if kind == 'equal':
            for offset, text in enumerate(before[a:b]):
                nearby = (index > 0 and offset == 0) or (index + 1 < len(operations) and offset == b-a-1)
                result.append({'kind': 'focus' if nearby else 'same', 'text': text})
        else:
            if kind in {'delete', 'replace'}:
                result.append({'kind': 'delete', 'text': ''.join(before[a:b])})
            if kind in {'insert', 'replace'}:
                result.append({'kind': 'insert', 'text': ''.join(after[c:d])})
    return result


def preview(state, original):
    draft = state['draft']
    return {'draft_id': draft['draft_id'], 'revision': draft['revision'],
            'reference': state['reference'], 'focus': draft['focus'],
            'reason': draft['reason'], 'benefit': draft['benefit'],
            'segments': segments(original, draft['content'])}


def run_draft_turn(service, *, state, source, original, kind, question, pending, fingerprint, draft_action=None):
    previous = (pending or {}).get('draft')
    current = deepcopy(previous['content'] if previous else original)
    if draft_action:
        if not previous or draft_action.draft_id != previous['draft_id'] or draft_action.revision != previous['revision']:
            raise RevisionConflict('修改稿已变化，请查看当前修改稿后再操作')
        output = {draft_action.action: True}
    else:
        if service.llm is None:
            raise ValueError('资料处理暂不可用，原文未改变')
        system = service.skills.extract_section('edu-artifact-revision', 'DRAFT_PROMPT')
        if not system:
            raise ValueError('资料修改技能未加载，原文未改变')
        prompt = [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps({
            'draft_mode': True, 'source': current, 'reference': state['reference'], 'artifact_type': kind,
            'draft_revision': previous['revision'] if previous else None,
            'instruction': state['question'], 'current_question': question, 'editable_paths': editable_paths(current)
        }, ensure_ascii=False)}]
        for attempt in range(2):
            response = service.llm.invoke(prompt)
            raw = getattr(response, 'content', response)
            try:
                output = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip()))
                actions = [k for k in ('answer', 'question', 'edits', 'save', 'discard') if k in output]
                if len(actions) != 1:
                    raise ValueError('每轮只能选择一个动作')
                if 'save' in output and (output['save'] is not True or not previous):
                    raise ValueError('没有已展示的修改稿，不能保存；请先生成修改预览')
                if 'discard' in output and output['discard'] is not True:
                    raise ValueError('discard 必须为 true')
                if 'edits' in output:
                    if not all(isinstance(output.get(k), str) and output[k].strip() for k in ('focus', 'reason', 'benefit')):
                        raise ValueError('修改预览必须包含定位范围 focus、修改原因 reason 与优势 benefit')
                    updated = apply_edits(current, output['edits'])
                    validate(kind, updated)
                    if kind == 'classroom' and updated['stage']['id'] != original['stage']['id']:
                        raise ValueError('不能更换课堂 ID')
                for key in ('answer', 'question'):
                    if key in output and (not isinstance(output[key], str) or not output[key].strip()):
                        raise ValueError('回答或追问不能为空')
                break
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                if attempt:
                    raise ValueError('修改预览未通过原文匹配或结构校验，原文未改变') from exc
                prompt.extend([{'role': 'assistant', 'content': str(raw)}, {'role': 'user', 'content': '尚未保存，请修正：' + str(exc)}])
    if output.get('discard') is True:
        return {'status': 'discarded', 'message': '已放弃本次修改稿，原文保持不变。', 'artifact_reference': state['reference']}
    if output.get('save') is True:
        if not previous:
            raise ValueError('没有可保存的修改稿')
        validate(kind, current)
        updates = content_updates(source, kind, current)
        if kind == 'game':
            updates = service._render_game(source, current, state['operation_id'])
        service.before_save()
        if service.is_cancel_requested():
            raise ValueError('操作已取消，原文未改变')
        changes = [{'path': [], 'before': readable_content(original), 'after': readable_content(current)}]
        saved = service.storage.save_copy(source, updates, owner=state['owner_user_id'], operation_id=state['operation_id'],
                                     fingerprint=fingerprint, summary=previous['reason'], changes=changes)
        result = service._completed(saved, kind)
        result['message'] = f'已将修改稿保存为新文档《{saved["title"]}》，原文档已保留。'
        return result
    if 'edits' in output:
        state['draft'] = {'draft_id': previous['draft_id'] if previous else uuid4().hex,
                          'revision': previous['revision'] + 1 if previous else 1,
                          'content': updated, 'focus': output['focus'], 'reason': output['reason'], 'benefit': output['benefit']}
        return {'status': 'preview', 'pending': state, 'draft': preview(state, original), 'artifact_reference': state['reference'],
                'message': output['reason'] + '\n\n' + output['benefit'] + '\n\n修改稿已在右侧标出，尚未保存。要保存当前修改稿，还是继续调整？'}
    text = output.get('answer') or output.get('question')
    result = {'status': 'answered' if 'answer' in output else 'needs_clarification', 'message': text, 'artifact_reference': state['reference']}
    if previous:
        # A read-only interlude must not become another editing instruction.
        retained = deepcopy(pending) if 'answer' in output else state
        result.update(pending=retained, draft=preview(retained, original), awaiting_clarification=True)
    elif 'question' in output:
        result['pending'] = state
    return result
