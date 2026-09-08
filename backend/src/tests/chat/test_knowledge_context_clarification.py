from types import SimpleNamespace
from copy import deepcopy

import pytest

from app.chat.application.knowledge_context import KnowledgeContextService
from app.chat.application.reply_service_v2 import ReplyServiceV2
from app.chat.domain.contracts import ChatRequestV2


class Conversations:
    def __init__(self): self.data = {}
    def get_conversation(self, cid, owner=None):
        data = self.data[cid]
        if owner and data['owner'] != owner: raise KeyError(cid)
        return data
    def ensure_conversation(self, cid, question=None, owner=None):
        self.data.setdefault(cid, {'owner': owner, 'state': {}})
    def get_state(self, cid): return deepcopy(self.data[cid]['state'])
    def update_state(self, cid, patch): self.data[cid]['state'].update(deepcopy(patch))


@pytest.fixture
def harness(monkeypatch):
    # These cases exercise the legacy resolver; model-planning cases opt in below.
    from core.config import Config
    monkeypatch.setattr(Config, 'USE_DEEPSEEK_HARNESS', False)
    storage = Conversations()
    graph = {'root': {'id': 'root', 'label': '数据结构', 'children': [
        {'id': 'array', 'label': '数组'}, {'id': 'list', 'label': '链表'},
        {'id': 'c1', 'label': '章节一', 'children': [{'id': 't1', 'label': '遍历'}]},
        {'id': 'c2', 'label': '章节二', 'children': [{'id': 't2', 'label': '遍历'}]},
    ]}}
    def authorize(request):
        if request.course_id != 'data': raise PermissionError('denied')
    resolver = KnowledgeContextService(
        course_storage=SimpleNamespace(get_course_info=lambda cid: {'name': '数据结构'}, get_knowledge_graph=lambda cid: graph),
        conversation_storage=storage, authorize=authorize)
    return resolver, storage


def req(question='为当前课程生成报告', **kw):
    return ChatRequestV2(question=question, owner='teacher', conversation_id='conv', course_id='data', **kw)


def test_current_course_resolves_current_node(harness):
    resolver, _ = harness
    request = req(scope_type='knowledge_point', scope_id='array')
    assert resolver.prepare(request) is None
    assert request.workspace_context.scope_title == '数组'
    assert request.scope_id == 'array'


@pytest.mark.parametrize('stream', [False, True])
def test_reply_missing_scope_zero_dispatch_then_resume(harness, stream):
    resolver, storage = harness
    calls = []
    def dispatch(request):
        calls.append(request)
        return {'message': {'role': 'assistant', 'content': '生成数组报告'}, 'conversation': {'conversation_id': 'conv'}, 'action': {'name': 'generate.report'}, 'artifacts': [], 'sources': [], 'trace': {'path': 'fast'}}
    def dispatch_stream(request, **kw): yield {'type': 'result', 'payload': dispatch(request)}
    service = ReplyServiceV2(orchestrator=SimpleNamespace(dispatch=dispatch, dispatch_stream=dispatch_stream),
        conversation_store=SimpleNamespace(write_v2_result=lambda *args: None), knowledge_context_service=resolver)
    def run(question):
        payload = SimpleNamespace(question=question, conversation_id='conv', owner='teacher', course_id='data', selected_doc_ids=['source'], allow_rag=True)
        if stream: return next(e['payload'] for e in service.reply_stream(payload) if e['type'] == 'result')
        return service.reply(payload)
    result = run('为当前课程生成报告')
    assert result['clarification']['status'] == 'needs_clarification'
    assert calls == []
    run('数组')
    assert len(calls) == 1
    assert '生成报告' in calls[0].question
    assert calls[0].scope_id == 'array'
    assert calls[0].capability.selected_doc_ids == ['source']
    assert storage.get_state('conv')['pending_operation'] is None


def test_duplicate_paths_and_resume(harness):
    resolver, _ = harness
    result = resolver.prepare(req('生成遍历报告', scope_type='knowledge_point', scope_id='array'))
    assert len(result['clarification']['candidates']) == 2
    followup = req('数据结构 › 章节二 › 遍历', scope_type='knowledge_point', scope_id='array')
    assert resolver.prepare(followup) is None
    assert followup.scope_id == 't2'


def test_invalid_scope_no_fallback(harness):
    resolver, _ = harness
    result = resolver.prepare(req(scope_type='knowledge_point', scope_id='foreign'))
    assert result['action']['name'] == 'workspace.invalid'
    assert result['workspace_context']['resolution'] == 'invalid'


def test_access_and_actor_isolation(harness):
    resolver, _ = harness
    resolver.prepare(req())
    request = req('数组'); request.owner = 'student'
    with pytest.raises(PermissionError): resolver.prepare(request)
    request = req(); request.course_id = 'physics'
    with pytest.raises(PermissionError): resolver.prepare(request)


def test_chat_without_scope_and_switch(harness):
    resolver, _ = harness
    assert resolver.prepare(req('你好')) is None
    request = req('换到链表')
    result = resolver.prepare(request)
    assert result['workspace_context']['update_workspace'] is True
    assert request.scope_id == 'list'


def test_explicit_whole_course(harness):
    resolver, _ = harness
    request = req('为整门课程生成报告', scope_type='knowledge_point', scope_id='array')
    assert resolver.prepare(request) is None
    assert request.scope_id is None
    assert request.workspace_context.explicit_course


def test_scope_change_cancels_pending(harness):
    resolver, _ = harness
    resolver.prepare(req())
    result = resolver.prepare(req('数组', scope_type='knowledge_point', scope_id='array'))
    assert result['action']['name'] == 'operation.cancelled'


def test_tool_boundary_revalidates_and_forces_trusted_topic(harness, monkeypatch):
    from app.chat.runtime.agent_tools.context import ToolExecutionContext
    from app.chat.runtime.agent_tools.executor import execute_tool
    resolver, _ = harness
    request = req(scope_type='knowledge_point', scope_id='array')
    resolver.prepare(request)
    monkeypatch.setattr('app.chat.application.knowledge_context.authorize_workspace', lambda request: None)
    monkeypatch.setattr('core.course_storage.storage_manager', resolver.courses)
    calls = []
    def handler(name, args, ctx):
        calls.append((args, ctx.request.scope_id))
        return {'ok': True, 'payload': {}}
    monkeypatch.setattr('app.chat.runtime.agent_tools.executor.get_tool_handler', lambda name: handler)
    ctx = ToolExecutionContext(capability=request.capability, max_steps=5, request=request)
    execute_tool('generate_report', {'subject': '整门课程'}, ctx)
    assert calls == [({'subject': '数组', 'topic': '数组'}, 'array')]
    monkeypatch.setattr(resolver.courses, 'get_knowledge_graph', lambda cid: {})
    result = execute_tool('generate_report', {'subject': '数组'}, ctx)
    assert result['ok'] is False
    assert len(calls) == 1


def test_tool_boundary_missing_scope_has_no_side_effect(harness, monkeypatch):
    from app.chat.runtime.agent_tools.context import ToolExecutionContext
    from app.chat.runtime.agent_tools.executor import execute_tool
    resolver, _ = harness
    request = req('你好')
    resolver.prepare(request)
    calls = []
    monkeypatch.setattr('app.chat.runtime.agent_tools.executor.get_tool_handler', lambda name: calls.append(name))
    result = execute_tool('generate_report', {'subject': '课程'}, ToolExecutionContext(capability=request.capability, max_steps=5, request=request))
    assert result['ok'] is False
    assert calls == []


@pytest.mark.parametrize('stream', [False, True])
def test_revision_uses_one_pending_slot_and_never_calls_generation(harness, stream):
    resolver, storage = harness
    seen = []
    def revise(**kw):
        seen.append(kw)
        if not kw['pending']:
            return {'status': 'needs_clarification', 'message': '希望怎样修改？', 'pending': {'owner_user_id': kw['owner_user_id'], 'conversation_id': kw['conversation_id'], 'reference': {'artifact_id': 'report1'}, 'question': kw['question']}}
        return {'status': 'completed', 'message': '已保存新版本', 'artifact': {'material_id': 'report1', 'course_id': 'original', 'scope_id': 'array', 'content': '原文加例子'}, 'artifact_reference': {'artifact_id': 'report1', 'artifact_type': 'report', 'version_id': 'v2'}}
    service = ReplyServiceV2(conversation_store=SimpleNamespace(storage=storage, write_v2_result=lambda *args: None), knowledge_context_service=resolver,
        artifact_revision_service=SimpleNamespace(run=revise), orchestrator=SimpleNamespace(dispatch=lambda req: pytest.fail('revision must not generate')))
    def run(question):
        payload = SimpleNamespace(question=question, owner='teacher', conversation_id='conv', course_id='data')
        return next(e['payload'] for e in service.reply_stream(payload) if e['type'] == 'result') if stream else service.reply(payload)
    first = run('修改上次的报告')
    assert first['artifact_revision']['status'] == 'needs_clarification'
    assert storage.get_state('conv')['pending_operation']['kind'] == 'artifact_revision'
    second = run('增加例子')
    assert second['artifacts'][0]['scope_id'] == 'array'
    assert seen[1]['pending']['reference']['artifact_id'] == 'report1'
    assert storage.get_state('conv')['pending_operation'] is None


def test_factory_scope_requires_valid_node_or_explicit_topic(harness):
    from app.chat.application.knowledge_context import resolve_direct_workspace
    resolver, _ = harness
    payload = SimpleNamespace(course_id='data', scope_type='course', scope_id=None, question='生成报告')
    with pytest.raises(ValueError, match='选择知识点'):
        resolve_direct_workspace(payload, resolver.courses)
    payload.question = '数组报告'
    assert resolve_direct_workspace(payload, resolver.courses).scope_title == '数组'
    assert payload.scope_id == 'array'
    payload.scope_id = 'foreign'
    with pytest.raises(ValueError, match='不属于'):
        resolve_direct_workspace(payload, resolver.courses)


def test_generation_context_uses_request_scope_and_sources(harness):
    from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
    from app.chat.domain.conversation_snapshot import ConversationSnapshot
    resolver, _ = harness
    request = req(scope_type='knowledge_point', scope_id='array')
    resolver.prepare(request)
    snapshot = ConversationSnapshot(conversation_id='conv', conversation_memory={'current_topics': ['错误主题']}, active_context={'pinned_doc_ids': ['stale'], 'current_course_id': 'wrong'})
    context = GenerationContextBuilder().build_for_resource(request=request, snapshot=snapshot, resource_type='report')
    assert context.current_topics == ['数组']
    assert context.current_course_id == 'data'
    assert context.selected_doc_ids == []


def test_planner_contract_uses_trusted_topic(harness):
    from app.chat.runtime.planning.task_contract_extractor import extract_task_contract
    resolver, _ = harness
    request = req(scope_type='knowledge_point', scope_id='array')
    resolver.prepare(request)
    assert extract_task_contract(request, request.capability).topic == '数组'


def test_retry_hints_do_not_split_tool_call_responses():
    from app.chat.runtime.nodes.executor import _inject_reflect_hint, _inject_plan_step_hint
    messages = [
        {'role': 'assistant', 'tool_calls': [{'id': 'one'}, {'id': 'two'}]},
        {'role': 'tool', 'tool_call_id': 'one', 'content': 'ok'},
        {'role': 'tool', 'tool_call_id': 'two', 'content': 'ok'},
    ]
    state = {'reflect_hint': '请补充大纲', 'plan_mode': 'guided', 'plan_step_index': 0, 'current_plan': {'steps': [{'user_title': '生成', 'expected_tools': ['draft_outline']}]}}
    for inject in (_inject_reflect_hint, _inject_plan_step_hint):
        result = inject(messages, state)
        assert result[:3] == messages


def test_empty_completion_uses_configured_backup():
    from app.chat.agents.report_generation import _ConfiguredFallbackChatModel
    calls = []
    class Model:
        def __init__(self, content): self.content = content
        def invoke(self, *args, **kw):
            calls.append(self.content)
            return SimpleNamespace(content=self.content)
    result = _ConfiguredFallbackChatModel([Model(''), Model('数组报告')]).invoke('生成')
    assert result.content == '数组报告'
    assert calls == ['', '数组报告']


def test_cancel_is_bound_to_owner_conversation_and_operation(harness):
    resolver, storage = harness
    result = resolver.prepare(req())
    op = result['clarification']['operation_id']
    with pytest.raises(KeyError): resolver.cancel(owner='other', conversation_id='conv', operation_id=op)
    assert not resolver.cancel(owner='teacher', conversation_id='conv', operation_id='stale')
    assert storage.get_state('conv')['pending_operation']
    assert resolver.cancel(owner='teacher', conversation_id='conv', operation_id=op)
    assert storage.get_state('conv')['pending_operation'] is None


def test_direct_api_rejects_before_source_or_job_work(harness, monkeypatch):
    from app.chat.api.routes_v2 import _validate_direct_generation_source
    from fastapi import HTTPException
    resolver, _ = harness
    monkeypatch.setattr('core.course_storage.storage_manager', resolver.courses)
    calls = []
    monkeypatch.setattr('app.chat.api.routes_v2._get_generation_source_resolver', lambda: SimpleNamespace(validate=lambda *args, **kwargs: calls.append(args)))
    payload = SimpleNamespace(course_id='data', scope_type='course', scope_id=None, question='为当前课程生成报告')
    with pytest.raises(HTTPException) as exc:
        _validate_direct_generation_source(payload, owner='teacher')
    assert exc.value.status_code == 422
    assert exc.value.detail['code'] == 'needs_clarification'
    assert calls == []
    payload.scope_type, payload.scope_id = 'knowledge_point', 'array'
    _validate_direct_generation_source(payload, owner='teacher')
    assert len(calls) == 1


def test_v2_json_schema_accepts_current_agent_trace():
    from app.chat.api.schemas_v2 import ChatResponseV2
    response = ChatResponseV2.model_validate({'message': {'role': 'assistant', 'content': 'ok'}, 'conversation': {'conversation_id': 'conv'}, 'action': {'name': 'agent.reply'}, 'trace': {'path': 'agent'}})
    assert response.trace.path == 'agent'


def test_quoted_edit_content_does_not_replace_explicit_artifact_target(tmp_path, monkeypatch):
    import json
    from app.artifact_revision.service import ArtifactRevisionService
    from core.course_storage import CourseStorageManager
    monkeypatch.setenv('MATERIAL_PERSISTENCE_MODE', 'json')
    manager = CourseStorageManager(tmp_path)
    manager.save_generated_material('data', 'report', 'report1', {'title': '数组报告', 'content': '原文'}, owner_user_id='teacher', visibility='private')
    model = SimpleNamespace(invoke=lambda *args: SimpleNamespace(content=json.dumps({'edits': [{'path': [], 'before': '原文', 'after': '原文\n验收标记'}]})))
    result = ArtifactRevisionService(manager, model).run(owner_user_id='teacher', conversation_id='conv', course_id='data',
        question='只在最后增加一句“验收标记”，其他内容不变', operation_id='quoted-edit',
        artifact_reference={'artifact_id': 'report1', 'artifact_type': 'report', 'version_id': 'v1', 'source_course_id': 'data'})
    assert result['status'] == 'completed'
    assert result['artifact_reference']['version_id'] == 'v2'


def test_revision_version_routes_preserve_actor_and_base_version(monkeypatch):
    import asyncio
    from app.chat.api import routes_v2
    from app.chat.api.schemas_v2 import ArtifactRevisionVersionRequestV2
    calls = []
    service = SimpleNamespace(read_version=lambda **kw: calls.append(kw) or {'version': kw['version']}, restore=lambda **kw: calls.append(kw) or {'status': 'completed'})
    monkeypatch.setattr(routes_v2, '_get_reply_service', lambda: SimpleNamespace(artifact_revision_service=service))
    access = SimpleNamespace(require=lambda course, user, capability: calls.append((course, user['username'], capability)))
    payload = ArtifactRevisionVersionRequestV2(reference={'artifact_id': 'report1', 'artifact_type': 'report', 'version_id': 'v3', 'source_course_id': 'data'}, version=1, operation_id='restore1')
    user = {'username': 'teacher', 'role': 'teacher'}
    assert asyncio.run(routes_v2.read_artifact_revision(payload, user, access)) == {'version': 1}
    assert asyncio.run(routes_v2.restore_artifact_revision(payload, user, access)) == {'status': 'completed'}
    assert calls[-1]['owner_user_id'] == 'teacher'
    assert calls[-1]['base_version'] == 3
    assert calls[-1]['version'] == 1
    assert calls[-1]['operation_id'] == 'restore1'


def test_explicit_course_confirmation_preserves_original_generation_scope(harness):
    resolver, _ = harness
    first = req('为整门课程生成报告', scope_type='knowledge_point', scope_id='array')
    resolver.prepare(first)
    followup = req('确认生成', scope_type='knowledge_point', scope_id='array')
    assert resolver.prepare(followup) is None
    assert followup.scope_type == 'course'
    assert followup.scope_id is None
    assert followup.workspace_context.explicit_course


def test_ambiguous_switch_resumes_as_switch_not_generation(harness):
    resolver, _ = harness
    resolver.prepare(req('换到遍历'))
    followup = req('数据结构 › 章节一 › 遍历')
    result = resolver.prepare(followup)
    assert result['action']['name'] == 'workspace.changed'
    assert followup.scope_id == 't1'


def test_factory_binds_actual_generator_topic_and_respects_explicit_override(harness):
    from app.chat.application.knowledge_context import resolve_direct_workspace
    resolver, _ = harness
    payload = SimpleNamespace(course_id='data', scope_type='knowledge_point', scope_id='array', question='为当前课程生成报告', report_config={'title': '当前课程报告'})
    resolve_direct_workspace(payload, resolver.courses)
    assert '数组' in payload.question
    assert payload.report_config['title'] == '数组报告'
    payload.question = '为链表生成报告'; payload.report_config = None
    resolve_direct_workspace(payload, resolver.courses)
    assert payload.scope_id == 'list'
    payload.question = '为整门课程生成报告'
    resolve_direct_workspace(payload, resolver.courses)
    assert payload.scope_type == 'course' and payload.scope_id is None


@pytest.mark.parametrize('stream', [False, True])
def test_read_answer_uses_shared_entry_without_generation_or_artifact(harness, stream):
    resolver, storage = harness
    outcome = {'status': 'answered', 'message': '原文讲数组的索引访问。', 'artifact_reference': {'artifact_id': 'report1', 'artifact_type': 'report', 'version_id': 'v1'}}
    service = ReplyServiceV2(
        conversation_store=SimpleNamespace(storage=storage, write_v2_result=lambda *args: None),
        knowledge_context_service=resolver,
        artifact_revision_service=SimpleNamespace(run=lambda **kwargs: outcome.copy()),
        orchestrator=SimpleNamespace(dispatch=lambda req: pytest.fail('read must not generate')),
    )
    payload = SimpleNamespace(question='这个文档写的什么', owner='teacher', conversation_id='conv', course_id='data')
    result = next(e['payload'] for e in service.reply_stream(payload) if e['type'] == 'result') if stream else service.reply(payload)
    assert result['action']['name'] == 'artifact.read'
    assert result['message']['content'] == outcome['message']
    assert result['artifacts'] == []
    assert result['artifact_revision']['status'] == 'answered'


@pytest.mark.parametrize("question", ["数组如何实现？", "我接下来要对数组进行备课", "帮我生成一份有关于数组的实现的报告"])
def test_combined_course_node_recognizes_natural_topic(harness, question):
    resolver, storage = harness
    resolver.courses.get_knowledge_graph = lambda cid: {"root": {"id": "root", "label": "课程", "children": [
        {"id": "array-linked-list", "label": "数组与链表"}]}}
    request = req(question, scope_type="course")
    assert resolver.prepare(request) is None
    assert request.scope_id == "array-linked-list"
    assert request.workspace_context.update_workspace is True
    assert storage.get_state("conv")["discussion_workspace"]["context"]["scope_id"] == "array-linked-list"
    assert request.question == question


def test_topic_correction_prefers_new_topic(harness):
    resolver, _ = harness
    request = req("链表讲完了，接下来讲数组如何实现", scope_type="knowledge_point", scope_id="list")
    assert resolver.prepare(request) is None
    assert request.scope_id == "array"
    assert request.workspace_context.update_workspace is True


def test_normal_unknown_question_does_not_force_topic_selection(harness):
    resolver, _ = harness
    assert resolver.prepare(req("如何给学生提供有效反馈？", scope_type="course")) is None


@pytest.mark.parametrize('question', ['开始', 'go ahead', '换到数组', '为当前课程生成报告', '取消', '修改报告'])
def test_model_preparation_never_interprets_user_text(harness, question):
    resolver, storage = harness
    request = req(question, scope_type='course')
    assert resolver.prepare_model(request) is None
    assert request.scope_type == 'course' and request.scope_id is None
    assert not storage.get_state('conv').get('pending_operation')


def test_harness_main_entry_skips_legacy_scope_and_edit_decisions(harness, monkeypatch):
    from core.config import Config
    monkeypatch.setattr(Config, 'USE_DEEPSEEK_HARNESS', True)
    resolver, _ = harness
    monkeypatch.setattr(resolver, 'prepare', lambda req: pytest.fail('legacy text classifier ran'))
    def dispatch(request):
        assert request.question == '修改一下数组报告'
        return {'message': {'role': 'assistant', 'content': '模型决定下一步'}, 'conversation': {'conversation_id': 'conv'},
                'action': {'name': 'chat.reply'}, 'trace': {'path': 'deepseek-harness'}}
    service = ReplyServiceV2(orchestrator=SimpleNamespace(dispatch=dispatch),
        conversation_store=SimpleNamespace(write_v2_result=lambda *a: None), knowledge_context_service=resolver)
    monkeypatch.setattr(service, '_run_artifact_edit', lambda **kw: pytest.fail('legacy edit classifier ran'))
    response = service.reply(SimpleNamespace(question='修改一下数组报告', owner='teacher', course_id='data', conversation_id='conv'))
    assert response['trace']['path'] == 'deepseek-harness'
