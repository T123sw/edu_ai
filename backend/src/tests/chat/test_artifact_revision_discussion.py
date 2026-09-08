"""Discussion is a non-writing stage; only later approval can enqueue edits."""
import json
from types import SimpleNamespace

from app.artifact_revision.service import ArtifactRevisionService
from tests.chat.test_artifact_revision import manager, seed
from tests.chat.test_artifact_revision_jobs import runtime


def proposal(*changes):
    return {"scope": "动态内存分配", "changes": list(changes or ["增加节点分配与释放示例"]),
            "reason": "衔接原文，帮助学生理解内存生命周期。", "question": "按此方案修改可以吗？"}


class SequenceModel:
    def __init__(self, *outputs):
        self.outputs = iter(outputs)
        self.inputs = []
    def invoke(self, prompt):
        self.inputs.append(json.loads(prompt[1]['content']))
        return SimpleNamespace(content=json.dumps(next(self.outputs), ensure_ascii=False))


def test_discussion_revises_plan_and_preserves_read_interlude_before_approval(manager):
    ref = seed(manager)
    first = proposal('增加三个分配、失败处理和释放示例')
    revised = proposal('只增加一个节点分配与释放的入门示例')
    model = SequenceModel({'proposal': first}, {'proposal': revised}, {'answer': '一个入门示例更适合初学者。'}, {'confirm': True})
    queued = []
    service = ArtifactRevisionService(manager, model, submitter=lambda **kw: queued.append(kw) or {'status': 'queued'})
    def turn(text, pending=None):
        return service.run(owner_user_id='teacher', conversation_id='conv', course_id='course',
                           question=text, operation_id='op', artifact_reference=ref, pending=pending)
    one = turn('修改动态内存分配，加几个例子')
    assert one['status'] == 'needs_clarification'
    assert first['reason'] in one['message'] and first['changes'][0] in one['message']
    assert queued == []
    two = turn('同意方向，但只要一个入门例子', one['pending'])
    assert two['pending']['proposal'] == revised and queued == []
    read = turn('为什么只加一个？', two['pending'])
    assert read['status'] == 'answered' and read['pending'] == two['pending'] and queued == []
    final = turn('可以，按这个方案修改', read['pending'])
    assert final['status'] == 'queued' and len(queued) == 1
    assert queued[0]['state']['approved_plan'] == revised
    assert manager.get_generated_material('course', 'report', 'one', owner_user_id='teacher')['version'] == 1
    assert '原始案例' in model.inputs[0]['source']


def test_initial_edits_and_confirmation_without_shown_plan_are_rejected(manager):
    ref = seed(manager)
    for invalid in ({'confirm': True}, {'edits': [{'path': [], 'before': '原始案例', 'after': '改了'}]}):
        queued = []
        service = ArtifactRevisionService(manager, SequenceModel(invalid, invalid), submitter=lambda **kw: queued.append(kw))
        result = service.run(owner_user_id='teacher', conversation_id='conv', course_id='course',
                             question='直接修改，不用问', operation_id='op', artifact_reference=ref)
        assert result['status'] == 'failed' and queued == []
        assert manager.get_generated_material('course', 'report', 'one', owner_user_id='teacher')['version'] == 1


def test_missing_information_can_take_multiple_turns_without_writes(manager):
    ref = seed(manager)
    plan = proposal('为初学者补充一个分配和释放例子')
    model = SequenceModel({'question': '面向初学者还是有 C 语言基础的学生？'},
                          {'question': '希望课堂演示还是课后练习？'}, {'proposal': plan})
    service = ArtifactRevisionService(manager, model)
    pending = None
    for question in ('加几个例子', '初学者', '课堂演示'):
        result = service.run(owner_user_id='teacher', conversation_id='conv', course_id='course',
                             question=question, operation_id='op', artifact_reference=ref, pending=pending)
        assert result['status'] == 'needs_clarification'
        pending = result['pending']
        assert manager.get_generated_material('course', 'report', 'one', owner_user_id='teacher')['version'] == 1
    assert pending['proposal'] == plan


def test_approved_plan_survives_real_queue_and_worker(runtime):
    r = runtime
    plan = proposal('把旧案例替换为新案例')
    r.service.llm = SequenceModel({'proposal': plan}, {'confirm': True})
    args = dict(owner_user_id='teacher', conversation_id='conv', course_id='course', operation_id='discussion-op', artifact_reference=r.ref)
    first = r.service.run(question='更新案例', **args)
    assert first['status'] == 'needs_clarification'
    assert not r.executor.run_once()
    final = r.service.run(question='同意，开始修改', pending=first['pending'], **args)
    assert final['status'] == 'queued'
    assert r.store.get_durable(final['task_id']).command['state']['approved_plan'] == plan
    assert r.executor.run_once()
    assert r.manager.get_generated_material('course','report','report1',owner_user_id='teacher')['version'] == 2


def test_provider_failure_logs_status_without_leaking_details(manager, caplog):
    ref = seed(manager)
    class ProviderError(Exception):
        status_code = 402
    class Unavailable:
        def invoke(self, prompt):
            raise ProviderError('Insufficient Balance with private provider details')
    service = ArtifactRevisionService(manager, Unavailable())
    result = service.run(owner_user_id='teacher', conversation_id='conv', course_id='course',
                         question='增加例子', operation_id='diagnostic-op', artifact_reference=ref)
    assert result['status'] == 'failed'
    assert '暂时不可用' in result['message']
    assert 'status=402' in caplog.text and 'operation=diagnostic-op' in caplog.text
    assert 'private provider details' not in caplog.text + result['message']
    assert manager.get_generated_material('course','report','one',owner_user_id='teacher')['version'] == 1
