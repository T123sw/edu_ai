"""Owned, append-only browser evidence. This does not certify generated science."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import time
from uuid import UUID, uuid4
from pydantic import Field, JsonValue, model_validator
from .contracts import Contract, PROTOCOL, Phase
from app.self_learning.store import lock

class RunView(Contract):
    run_id: UUID
    revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    seq: int = Field(ge=0, le=2000)
    phase: Phase
    index: int = Field(ge=0)
    attempt_id: UUID
    attempt_before: dict[str, JsonValue]
    last_input: dict[str, JsonValue]
    state: dict[str, JsonValue]
    feedback: str = Field(max_length=12000)
    verdict: str = Field(max_length=40)
    events: list[dict[str, JsonValue]] = Field(max_length=2000)
    snapshots: dict[str, dict[str, JsonValue]]

    @model_validator(mode='after')
    def consistency(self):
        data = self.model_dump(mode='json')
        if len(json.dumps(data, ensure_ascii=False, allow_nan=False)) > 1500000: raise ValueError('运行记录过大')
        if len(self.events) != self.seq: raise ValueError('事件序号不连续')
        ids = set()
        for seq, e in enumerate(self.events, 1):
            if e.get('seq') != seq or not isinstance(e.get('id'), str) or not e['id'] or e['id'] in ids: raise ValueError('事件缺失或重复')
            ids.add(e['id'])
            if e.get('actor') not in ['system', 'user'] or e.get('phase') not in ['demonstrate', 'guided', 'explore']: raise ValueError('事件来源或阶段无效')
            command = e.get('command')
            if command is not None and (not isinstance(command, dict) or not isinstance(command.get('action'), str) or not isinstance(command.get('input'), dict)):
                raise ValueError('操作记录格式无效')
            if not isinstance(e.get('before'), str) or not isinstance(e.get('after'), str) or e['before'] not in self.snapshots or e['after'] not in self.snapshots: raise ValueError('事件快照缺失')
            if e.get('before') != f'{seq}:before' or e.get('after') != str(seq): raise ValueError('快照编号不匹配')
        if self.snapshots.get(str(self.seq)) != self.state: raise ValueError('当前状态与最后快照不匹配')
        return self

class SaveRun(Contract):
    expected_seq: int = Field(ge=-1)
    view: RunView

class FreezeQuestion(Contract):
    expected_seq: int = Field(ge=0)
    question: str = Field(min_length=1, max_length=2000)

class Conflict(ValueError): pass
class Missing(ValueError): pass

class ExperimentRepository:
    def __init__(self, store=None):
        from ..service import PracticeStore
        self.store = store or PracticeStore()

    @contextmanager
    def transaction(self, owner, identifier):
        key = owner + ':' + identifier
        # All experiment writers use this lock; PG lock also covers other workers.
        if self.store.repository:
            from app.database import database_session
            from sqlalchemy import text
            with lock, database_session(engine=self.store.repository._engine) as session:
                if session.bind.dialect.name == 'postgresql':
                    session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], signed=True)})
                yield
        else:
            folder = self.store.root / '.experiment-locks'; folder.mkdir(parents=True, exist_ok=True)
            with lock, (folder / hashlib.sha256(key.encode()).hexdigest()).open('a') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                try: yield
                finally: fcntl.flock(handle, fcntl.LOCK_UN)

    def get(self, owner, identifier, run_id):
        data = self.store.get(owner, f'{identifier}:experiment:{run_id}')
        if not data: raise Missing('运行记录不存在')
        return data

    def save(self, owner, identifier, experiment, request: SaveRun):
        view = request.view.model_dump(mode='json'); run_id = view['run_id']
        if view['revision'] != experiment['revision']: raise Conflict('实验版本已改变')
        spec = experiment['spec']
        if view['phase'] not in spec.get('phases', ['demonstrate', 'guided', 'explore']):
            raise ValueError('该实验不支持此阶段')
        maximum = len(spec['demo_steps']) if view['phase'] == 'demonstrate' else len(spec['tasks']) if view['phase'] == 'guided' else 0
        if view['index'] > maximum: raise ValueError('当前步骤不存在')
        with self.transaction(owner, identifier):
            key = f'{identifier}:experiment:{run_id}'; previous = self.store.get(owner, key)
            if previous and previous['view'] == view:
                self.store.put(owner, identifier + ':experiment-latest', {'run_id': run_id})
                return previous
            if (previous['view']['seq'] if previous else -1) != request.expected_seq: raise Conflict('运行记录已更新，请保留本地记录并重新读取')
            if previous:
                old = previous['view']
                if view['seq'] <= old['seq'] or view['events'][:old['seq']] != old['events']: raise Conflict('已保存的操作不能改写')
                if any(view['snapshots'].get(k) != v for k, v in old['snapshots'].items()): raise Conflict('已保存的状态不能改写')
            data = {'protocol': experiment.get('protocol', PROTOCOL), 'practice_id': identifier, 'view': view, 'saved_at': time.time(), 'evidence_source': 'browser_reported', 'scientifically_verified': False}
            self.store.put(owner, key, data)
            self.store.put(owner, identifier + ':experiment-latest', {'run_id': run_id})
            return data

    def latest(self, owner, identifier):
        pointer = self.store.get(owner, identifier + ':experiment-latest')
        return self.get(owner, identifier, pointer['run_id']) if pointer else None

    def freeze(self, owner, identifier, experiment, run_id, request: FreezeQuestion):
        with self.transaction(owner, identifier):
            saved = self.get(owner, identifier, run_id); view = saved['view']
            if view['seq'] != request.expected_seq or view['revision'] != experiment['revision']: raise Conflict('提问对应的状态已改变，请重新提交')
            context_id = str(uuid4()); spec = experiment['spec']
            context = {'context_version': 'edu-experiment-context/1', 'context_id': context_id, 'practice_id': identifier, 'run_id': run_id, 'revision': view['revision'], 'state_revision': view['seq'], 'phase': view['phase'], 'task_id': spec['tasks'][view['index']]['id'] if view['phase'] == 'guided' and view['index'] < len(spec['tasks']) else None, 'attempt_id': view['attempt_id'], 'question': request.question, 'background': spec['teaching_context'], 'scientific_model': spec['scientific_model'], 'state_fields': spec['state_fields'], 'design': spec, 'current_state': view['state'], 'feedback': view['feedback'], 'events': view['events'], 'snapshots': view['snapshots'], 'evidence_source': 'browser_reported', 'scientifically_verified': False, 'created_at': time.time(), 'teaching_status': 'reserved'}
            # Automatic advancement can show the next task while the learner is
            # asking about feedback from the preceding action. Preserve both.
            context['step_index'] = view['index']
            context['verdict'] = view['verdict']
            context['focus'] = {
                'last_action_event_id': next((e['id'] for e in reversed(view['events']) if e.get('type') == 'action'), None),
                'last_feedback_event_id': next((e['id'] for e in reversed(view['events']) if e.get('feedback')), None),
                'last_submitted_attempt': next(({'attempt_id': e.get('attempt_id'), 'task_id': e.get('task_id'), 'event_id': e['id']} for e in reversed(view['events']) if e.get('type') == 'attempt_submitted'), None),
            }
            self.store.put(owner, f'{identifier}:teaching-context:{context_id}', context)
            return context

    def context(self, owner, identifier, context_id):
        data = self.store.get(owner, f'{identifier}:teaching-context:{context_id}')
        if not data: raise Missing('教学上下文不存在')
        return data

    def capture(self, owner, identifier, experiment, view: RunView, question):
        """Caller holds transaction. Capture question-time evidence without moving the run.

        Autosave may already be ahead, or the submitted browser tail may not yet
        be synced. Both are valid provided their common history is immutable.
        """
        value = view.model_dump(mode='json')
        if value['revision'] != experiment['revision']:
            raise Conflict('实验版本已改变，请刷新后提问')
        spec = experiment['spec']
        maximum = len(spec['demo_steps']) if view.phase == 'demonstrate' else len(spec['tasks']) if view.phase == 'guided' else 0
        if view.index > maximum:
            raise ValueError('当前步骤不存在')
        saved = self.store.get(owner, f'{identifier}:experiment:{view.run_id}')
        if saved:
            old = saved['view']
            shorter, longer = sorted([old, value], key=lambda v: v['seq'])
            if (old['seq'] == value['seq'] and old != value) or old['revision'] != value['revision'] or shorter['events'] != longer['events'][:shorter['seq']] or any(longer['snapshots'].get(k) != v for k, v in shorter['snapshots'].items()):
                raise Conflict('提问记录与已保存的操作不一致，请同步记录后重试')
        context_id = str(uuid4())
        context = {
            'context_version': 'edu-experiment-context/1', 'context_id': context_id,
            'practice_id': identifier, 'run_id': str(view.run_id), 'revision': view.revision,
            'state_revision': view.seq, 'phase': view.phase,
            'step_index': view.index, 'verdict': view.verdict,
            'task_id': spec['tasks'][view.index]['id'] if view.phase == 'guided' and view.index < len(spec['tasks']) else None,
            'attempt_id': str(view.attempt_id), 'question': question,
            'background': spec['teaching_context'], 'scientific_model': spec['scientific_model'],
            'state_fields': spec['state_fields'], 'design': spec,
            'current_state': value['state'], 'feedback': view.feedback,
            'events': value['events'], 'snapshots': value['snapshots'],
            'evidence_source': 'browser_reported', 'scientifically_verified': False,
            'created_at': time.time(), 'teaching_status': 'active',
        }
        self.store.put(owner, f'{identifier}:teaching-context:{context_id}', context)
        return context
