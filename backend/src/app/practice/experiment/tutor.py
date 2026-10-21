"""Read-only, evidence-bound experiment teaching; no experiment mutations."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from app.services.tutoring_response_policy import TUTORING_RESPONSE_POLICY
from .contracts import Contract
from .repository import Conflict, ExperimentRepository, Missing, RunView
from .teaching import EvidenceRequest, read_evidence

LEASE_SECONDS = 120
SKILL = Path(__file__).resolve().parents[1] / 'skills/teach-experiment/SKILL.md'


class TutorQuestion(Contract):
    request_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    view: RunView
    reply_to: UUID | None = None
    focus_event_id: str | None = Field(default=None, max_length=200)

    @field_validator('question')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('请输入问题或回答')
        return value.strip()


def choose_focus(context, explicit=None):
    events = context['events']
    if explicit:
        event = next((e for e in events if e['id'] == explicit), None)
        if event is None:
            raise ValueError('指定操作不在本次提问记录中')
        return event
    # Don't attach a new-round/reset question to a previous phase's action.
    candidates = []
    decision_fallback = None
    for event in reversed(events):
        if event.get('type') in {'phase_changed', 'phase_entered', 'reset', 'replay', 'back', 'demo_restored'}:
            return candidates[0] if candidates else decision_fallback or event
        if event.get('type') == 'attempt_submitted' and decision_fallback is None:
            decision_fallback = event
        if event.get('type') in {'action', 'observation'}:
            candidates.append(event)
            if event.get('command', {}).get('input', {}).get('control') is None:
                return event
        if event.get('type') == 'initialized':
            # A pass may initialize the next task. Keep the immediately preceding
            # submitted action as focus, but don't cross a phase boundary.
            if not any(e.get('type') == 'attempt_submitted' for e in events[max(0, event['seq'] - 3):event['seq'] - 1]):
                return candidates[0] if candidates else decision_fallback or event
    return candidates[0] if candidates else decision_fallback


def evidence_packet(context):
    from .facts import fact_packet
    focus = choose_focus(context, context.get('focus_event_id'))
    task_id = focus.get('task_id') if focus else context.get('task_id')
    task = next((t for t in context['design']['tasks'] if t['id'] == task_id), None)
    return {
        'scope': {k: context[k] for k in ('context_id', 'run_id', 'revision', 'state_revision', 'phase', 'attempt_id')},
        'facts': fact_packet(context, focus),
        'reference_material': {
            'title': context['design']['title'], 'background': context['background'],
            'scientific_model': context['scientific_model'],
            'objectives': context['design'].get('objectives', []),
            'task': {k: v for k, v in task.items() if k not in {'initial', 'checkpoint'}} if task else None,
            'current_page_feedback': context.get('feedback', ''),
            'authority': 'design and generated prose, not observed state or verified causal conclusions',
        },
    }


def public_turn(row):
    keys = ('request_id', 'question', 'reply_to', 'context_id', 'target_context_id', 'revision', 'run_id',
            'state_revision', 'attempt_id', 'phase', 'focus_label', 'status', 'answer', 'error', 'created_at', 'updated_at')
    result = {key: row.get(key) for key in keys}
    if result['status'] == 'pending' and row['lease_until'] < time.time():
        result.update(status='failed', error='上次回答已中断，可以重试原问题。')
    return result


class TutorRepository:
    def __init__(self, repository=None):
        self.repo = repository or ExperimentRepository()
        self.store = self.repo.store

    def get(self, owner, identifier, request_id):
        row = self.store.get(owner, f'{identifier}:tutor:{request_id}')
        if not row:
            raise Missing('教学消息不存在')
        return row

    def history(self, owner, identifier, *, before=None, limit=20):
        ids = self.store.get(owner, f'{identifier}:tutor-index').get('ids', [])
        if before:
            if before not in ids:
                raise Missing('对话分页位置不存在')
            ids = ids[:ids.index(before)]
        page = ids[-limit:]
        return {'items': [public_turn(self.get(owner, identifier, key)) for key in page],
                'next_cursor': page[0] if len(ids) > limit else None}

    def prepare(self, owner, identifier, experiment, request):
        body_hash = hashlib.sha256(json.dumps(request.model_dump(mode='json'), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        key = str(request.request_id)
        with self.repo.transaction(owner, identifier):
            previous = self.store.get(owner, f'{identifier}:tutor:{key}')
            if previous:
                if previous['body_hash'] != body_hash:
                    raise Conflict('提问编号对应不同内容')
                # Recover a crash between saving the turn and its list pointer.
                ids = self.store.get(owner, f'{identifier}:tutor-index').get('ids', [])
                if key not in ids:
                    ids.append(key)
                    ids.sort(key=lambda item: self.get(owner, identifier, item)['created_at'])
                    self.store.put(owner, f'{identifier}:tutor-index', {'ids': ids})
                return previous, False
            parent = self.get(owner, identifier, str(request.reply_to)) if request.reply_to else None
            if parent and (parent['status'] != 'complete' or parent['revision'] != experiment['revision']):
                raise Conflict('只能回复当前实验版本中已完成的教学消息')
            if request.reply_to and request.focus_event_id:
                raise ValueError('回复旧问题与选择历史操作不能同时使用')
            # Validate focus before persisting the context.
            focus = choose_focus({'events': request.view.events}, request.focus_event_id)
            context = self.repo.capture(owner, identifier, experiment, request.view, request.question)
            context['focus_event_id'] = focus['id'] if focus else None
            self.store.put(owner, f'{identifier}:teaching-context:{context["context_id"]}', context)
            target_id = parent['target_context_id'] if parent else context['context_id']
            label = parent['focus_label'] if parent else (focus.get('command', {}).get('action') or '当前实验状态') if focus else '当前实验状态'
            if not parent and focus:
                design = experiment['spec']
                catalog = design.get('actions', []) + design.get('action_catalog', [])
                action = next((a for a in catalog if isinstance(a, dict) and a.get('id') == label), None)
                demo = next((step for step in design['demo_steps'] if step.get('action_id') == label), None)
                label = (action or {}).get('label') or (action or {}).get('title') or (demo or {}).get('title') or label
            source = SKILL.read_text(encoding='utf-8') + '\n\n' + TUTORING_RESPONSE_POLICY
            now = time.time()
            row = {'request_id': key, 'body_hash': body_hash, 'question': request.question,
                   'reply_to': str(request.reply_to) if request.reply_to else None,
                   'context_id': context['context_id'], 'target_context_id': target_id,
                   'revision': context['revision'], 'run_id': context['run_id'],
                   'state_revision': context['state_revision'], 'attempt_id': context['attempt_id'], 'phase': context['phase'],
                   'focus_label': str(label)[:160], 'status': 'pending', 'answer': '', 'error': '',
                   'created_at': now, 'updated_at': now, 'lease_until': now + LEASE_SECONDS,
                   'execution_id': str(uuid4()), 'skill': source,
                   'skill_version': hashlib.sha256(source.encode()).hexdigest()}
            self.store.put(owner, f'{identifier}:tutor:{key}', row)
            index = self.store.get(owner, f'{identifier}:tutor-index').get('ids', [])
            self.store.put(owner, f'{identifier}:tutor-index', {'ids': [*index, key]})
            return row, True

    def retry(self, owner, identifier, experiment, request_id):
        with self.repo.transaction(owner, identifier):
            row = self.get(owner, identifier, request_id)
            if row['status'] == 'complete':
                return row, False
            if row['revision'] != experiment['revision']:
                raise Conflict('实验版本已变化，请在新版本重新提问')
            if row['status'] == 'pending' and row['lease_until'] > time.time():
                raise Conflict('正在回答这条消息，请稍候')
            row.update(status='pending', error='', answer='', execution_id=str(uuid4()),
                       updated_at=time.time(), lease_until=time.time() + LEASE_SECONDS)
            self.store.put(owner, f'{identifier}:tutor:{request_id}', row)
            return row, True

    def finish(self, owner, identifier, row, *, answer='', error=''):
        with self.repo.transaction(owner, identifier):
            current = self.get(owner, identifier, row['request_id'])
            if current['execution_id'] != row['execution_id'] or current['status'] != 'pending':
                raise Conflict('本次回答已由其他请求接管')
            current.update(status='failed' if error else 'complete', answer=answer, error=error, updated_at=time.time())
            self.store.put(owner, f'{identifier}:tutor:{row["request_id"]}', current)
            return current

    def model_context(self, owner, identifier, row):
        current = self.repo.context(owner, identifier, row['context_id'])
        target = self.repo.context(owner, identifier, row['target_context_id'])
        parent = self.get(owner, identifier, row['reply_to']) if row['reply_to'] else None
        recent = self.history(owner, identifier, before=row['request_id'], limit=8)['items']
        history = [{k: turn[k] for k in ('question', 'answer', 'reply_to', 'run_id', 'state_revision')}
                   for turn in recent if turn['status'] == 'complete' and turn['revision'] == row['revision']]
        packet = {'question': row['question'], 'reply_to': public_turn(parent) if parent else None,
                  'target': evidence_packet(target),
                  'current': evidence_packet(current) if target['context_id'] != current['context_id'] else {'same_as_target': True},
                  'recent_conversation': history,
                  'conversation_authority': 'Conversation may contain incorrect explanations; use facts for counts, states and outcomes.'}
        return packet, {'target': target, 'current': current}


TOOL = {'type': 'function', 'function': {
    'name': 'read_experiment_evidence',
    'description': '只读查询 target/current 冻结实验。优先 get_fact_summary 查程序统计、list_operations 分页教学操作、get_operation 查前后状态及错误证据；原始事件仅用于排查，不能直接当作步骤数。',
    'parameters': {'type': 'object', 'properties': {
        'scope': {'type': 'string', 'enum': ['target', 'current']},
        'request': EvidenceRequest.model_json_schema()}, 'required': ['scope', 'request'], 'additionalProperties': False}}}


async def teach(owner, packet, contexts, skill, *, model=None):
    from .tutor_transport import TutorModel
    model = model or TutorModel.for_owner(owner)
    # Keep reference conversation before the authoritative observation projection.
    ordered = {key: packet[key] for key in ('recent_conversation', 'conversation_authority', 'reply_to', 'target', 'current', 'question') if key in packet}
    messages = [{'role': 'system', 'content': skill},
                {'role': 'user', 'content': json.dumps(ordered, ensure_ascii=False)}]
    # Keep the actual conversational exchange last, in its real roles. A JSON
    # context alone can make the model answer an embedded historical question
    # or silently substitute its expected answer for the learner's words.
    if packet.get('reply_to'):
        messages.append({'role': 'assistant', 'content': packet['reply_to']['answer']})
    messages.append({'role': 'user', 'content': packet['question']})
    calls_used = 0
    async with asyncio.timeout(90):
        for round_index in range(4):
            result = None
            available_tools = round_index < 3 and calls_used < 8
            if not available_tools:
                messages.append({'role': 'system', 'content': '本次只读证据查询已结束。请用已有记录直接回答；未查到或未上报的事实明确说未知，不补造过程，不再调用工具。'})
            async for item in model.stream(messages, [TOOL] if available_tools else []):
                if item['type'] == 'delta':
                    yield item
                elif item['type'] == 'result':
                    result = item
            if result is None:
                raise ValueError('教学服务未返回完整回答')
            if not result['calls']:
                if not result['content'].strip():
                    raise ValueError('教学服务未返回回答')
                return
            messages.append({'role': 'assistant', 'content': result['content'] or None, 'tool_calls': result['calls']})
            yield {'type': 'status', 'message': '正在查看相关操作记录…'}
            for call in result['calls']:
                try:
                    if calls_used >= 8:
                        raise ValueError('本次证据读取预算已用完；本条查询未执行。请依据已有记录回答，缺失依据保留未知。')
                    calls_used += 1
                    if call['function']['name'] != 'read_experiment_evidence':
                        raise ValueError('此工具不可用')
                    args = json.loads(call['function']['arguments'])
                    if set(args) != {'scope', 'request'} or args['scope'] not in contexts:
                        raise ValueError('只能读取本次问题的 target 或 current')
                    value = read_evidence(contexts[args['scope']], EvidenceRequest.model_validate(args['request']))
                    if len(json.dumps(value, ensure_ascii=False).encode()) > 100000:
                        value = {'error': '结果过大，请使用 list_events 小批分页或 get_snapshot 读取指定状态'}
                except (ValueError, TypeError, KeyError) as exc:
                    value = {'error': str(exc)[:300]}
                messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(value, ensure_ascii=False)})
        raise ValueError('教学服务未完成回答，请重试')


async def stream_turn(repository, owner, identifier, row, execute, *, model=None):
    def event(kind, **payload):
        return 'data: ' + json.dumps({'type': kind, **payload}, ensure_ascii=False) + '\n\n'
    if not execute:
        yield event('accepted', turn=public_turn(row))
        yield event('done', turn=public_turn(row))
        return
    finished = False
    answer = ''
    pending = None
    response = None
    try:
        yield event('accepted', turn=public_turn(row))
        packet, contexts = repository.model_context(owner, identifier, row)
        response = teach(owner, packet, contexts, row['skill'], model=model)
        queue = asyncio.Queue()
        async def produce():
            try:
                async for item in response:
                    queue.put_nowait(item)
            finally:
                queue.put_nowait(None)
        # Keep the model timeout in one task throughout the generator lifetime.
        pending = asyncio.create_task(produce())
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ': keep-alive\n\n'
                continue
            if item is None:
                await pending
                break
            if item['type'] == 'delta':
                answer += item['text']
            yield event(item['type'], **{k: v for k, v in item.items() if k != 'type'})
        saved = repository.finish(owner, identifier, row, answer=answer.strip())
        finished = True
        yield event('done', turn=public_turn(saved))
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.getLogger(__name__).exception('Experiment tutoring failed')
        try:
            saved = repository.finish(owner, identifier, row, error='暂时未能完成回答，请重试。你的实验可以继续。')
            finished = True
            yield event('error', turn=public_turn(saved))
        except Conflict:
            finished = True
            yield event('error', message='本次回答已由重试接管，请刷新对话查看结果。')
    finally:
        if pending and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        if response:
            await response.aclose()
        if not finished:
            try:
                repository.finish(owner, identifier, row, error='回答连接已中断，可以重试原问题。')
            except Conflict:
                pass
