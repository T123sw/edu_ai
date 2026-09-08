"""Cross-conversation reads retain identity and mutation boundaries."""
from types import SimpleNamespace
import json

import pytest

from app.chat.harness.runtime import HarnessRuntime
from app.chat.harness.store import HarnessStore
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from tests.chat.test_harness_runtime import request, toolset


def job(**changes):
    return SimpleNamespace(**{**dict(
        edu_job_id='report-job', owner_user_id='alice', course_id='course1',
        kind='generate_report', status='succeeded', progress=100, scope_id='linked-list',
        created_at='2026-09-08', result_ref={'material_id': 'report1'},
        input_summary={'title': '链表的实现', 'config': {
            'title': '链表的实现', 'harness_conversation_id': 'source-conversation',
            'harness_outline_id': 'source-outline', 'harness_outline_revision': 2,
            'harness_chapters': [{'title': name} for name in ['节点', '插入', '删除']]}}), **changes})


def page(*items, cursor=None):
    return SimpleNamespace(items=list(items), next_cursor=cursor)


def reviewed_artifact():
    from app.chat.harness.reviewed_report import CRITERIA, digest
    body = '# 节点\n' + '链表正文。' * 100 + '\n# 插入\n插入说明\n# 删除\n删除说明'
    return {'content': body, 'generation_state': {'report_review': {
        'decision': 'pass', 'method': 'model_review', 'content_sha256': digest(body),
        'checks': [{'criterion': c, 'passed': True} for c in CRITERIA]}}}


def test_empty_old_conversation_discovers_and_reads_completed_report(tmp_path):
    calls = []
    store = HarnessStore(tmp_path)
    with store.session(request()) as state:
        tools = toolset(request(), state, get_job=lambda _: job(),
                        list_report_jobs=lambda **kw: calls.append(kw) or page(job()),
                        read_artifact=lambda *a: reviewed_artifact())
        context = HarnessRuntime._context(request(), ConversationSnapshot(), state, tools)
        data = json.loads(context.split('\n', 1)[1])
        assert data['report_jobs'] == {}
        assert data['report_discovery']['candidates'][0]['status'] == 'succeeded'
        assert calls[0]['owner_user_id'] == 'alice' and calls[0]['course_id'] == 'course1'
        result = tools.call('query_report_job', {'task_id': 'report-job'})
        assert result['ok'], result
        assert result['data']['verification']['decision'] == 'pass'
        assert result['data']['artifact']['title'] == '链表的实现'
        assert state.data['outlines'] == {} and state.data['jobs'] == {}
        assert not tools.call('cancel_report_job', {'task_id': 'report-job'})['ok']
    with store.session(request()) as state:
        assert state.data['report_links']['report-job']['source_conversation_id'] == 'source-conversation'
        tools = toolset(request(), state, get_job=lambda _: job(owner_user_id='bob'))
        assert not tools.call('query_report_job', {'task_id': 'report-job'})['ok']
        assert tools.readable_report_links() == {}


@pytest.mark.parametrize('change', [{'owner_user_id': 'bob'}, {'course_id': 'course2'}, {'kind': 'generate_quiz'}])
def test_foreign_jobs_never_exposed_or_read(tmp_path, change):
    reads = []
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state, get_job=lambda _: job(**change),
                        list_report_jobs=lambda **kw: page(job(**change)),
                        read_artifact=lambda *a: reads.append(a))
        assert tools.call('find_report_jobs', {})['data']['candidates'] == []
        assert not tools.call('query_report_job', {'task_id': 'report-job'})['ok']
        assert reads == [] and not state.data.get('report_links')


def test_ambiguous_candidates_and_empty_pages_are_not_task_states(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state, list_report_jobs=lambda **kw: page(job(), job(edu_job_id='other'), cursor='20'))
        data = tools.call('find_report_jobs', {})['data']
        assert len(data['candidates']) == 2 and data['selection'] == 'unresolved'
        assert data['next_cursor'] == '20' and not state.data.get('report_links')
        tools.list_report_jobs = lambda **kw: page()
        data = tools.call('find_report_jobs', {})['data']
        assert data['lookup_status'] == 'not_found_in_page' and 'status' not in data
        tools.list_report_jobs = None
        assert tools.call('find_report_jobs', {})['data']['lookup_status'] == 'unavailable'


def test_authorization_precedes_automatic_and_tool_reads(tmp_path):
    calls = []
    def denied(req):
        raise PermissionError('revoked')
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state, authorize=denied,
                        list_report_jobs=lambda **kw: calls.append(kw))
        with pytest.raises(PermissionError):
            HarnessRuntime._context(request(), ConversationSnapshot(), state, tools)
        assert not tools.call('find_report_jobs', {})['ok']
        assert calls == []


def test_discovery_outage_and_scope_parameters(tmp_path):
    def broken(**kw):
        raise RuntimeError('database unavailable')
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state, list_report_jobs=broken)
        context = HarnessRuntime._context(request(), ConversationSnapshot(), state, tools)
        assert json.loads(context.split('\n', 1)[1])['report_discovery']['lookup_status'] == 'unavailable'
        assert not tools.call('find_report_jobs', {'owner': 'bob'})['ok']
        assert not tools.call('find_report_jobs', {'course_id': 'course2'})['ok']


def test_cross_conversation_stale_review_cannot_deliver(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        artifact = reviewed_artifact()
        artifact['content'] += '\n修改过的正文'
        tools = toolset(request(), state, get_job=lambda _: job(), read_artifact=lambda *a: artifact)
        data = tools.call('query_report_job', {'task_id': 'report-job'})['data']
        assert data['verification']['decision'] == 'fail' and 'artifact' not in data


def test_legacy_source_recovery_does_not_merge_history_or_accept_other_identities(tmp_path):
    store = HarnessStore(tmp_path)
    for req in [request(conversation_id='source'), request(owner='bob'), request(course_id='course2')]:
        with store.session(req) as state:
            state.data['jobs']['report-job'] = {'outline_id': 'source-outline', 'revision': 2}
            state.data['responses']['source-turn'] = {'request': req.model_dump(), 'result': {}}
            state.data['history'] = [{'role': 'user', 'content': 'private history'}]
            state.save()
    assert store.report_source(request(), 'report-job') == 'source'
    assert store.report_source(request(), 'missing') is None
    legacy = job()
    legacy.input_summary['config'].pop('harness_conversation_id')
    with store.session(request()) as state:
        tools = toolset(request(), state, get_job=lambda _: legacy,
                        read_artifact=lambda *a: reviewed_artifact(), resolve_report_source=store.report_source)
        data = tools.call('query_report_job', {'task_id': 'report-job'})['data']
        assert data['report_link']['source_conversation_id'] == 'source'
        assert state.data['history'] == [] and state.data['jobs'] == {}


def test_result_reference_cannot_escape_authorized_course(tmp_path):
    reads = []
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state, get_job=lambda _: job(result_ref={'course_id': 'course2'}),
                        read_artifact=lambda *a: reads.append(a))
        assert not tools.call('query_report_job', {'task_id': 'report-job'})['ok']
        assert reads == []


def test_multiple_queries_do_not_replace_completed_report_with_last_failure(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state)
        tools.outcomes = [
            {'ok': True, 'tool': 'query_report_job', 'data': {
                'task_id': 'completed', 'title': '链表', 'status': 'succeeded',
                'verification': {'decision': 'pass'}, 'artifact': {'artifact_id': 'ready'}}},
            {'ok': True, 'tool': 'query_report_job', 'data': {
                'task_id': 'failed', 'title': '链表旧版', 'status': 'failed'}},
        ]
        result = HarnessRuntime._result(request(), '', tools)
        assert '已生成并通过模型审阅' in result['message']['content']
        assert '生成失败' in result['message']['content']
        assert '哪一份' in result['message']['content']
        assert result['artifacts'] == [] and result['workflow'] is None
        assert 'task_id' not in result


@pytest.mark.parametrize('status,verification', [('succeeded', 'pass'), ('succeeded', 'fail'), ('running', None), ('failed', None)])
def test_read_answer_is_preserved_without_generation_workflow(tmp_path, status, verification):
    answer = '这份报告讨论了链表节点、插入和删除；下面继续解释插入时指针的更新顺序。'
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state)
        tools.outcomes = [{'ok': True, 'tool': 'query_report_job', 'data': {
            'task_id': 'existing', 'title': '链表', 'status': status,
            'verification': {'decision': verification}, 'artifact': {'artifact_id': 'existing-report'}}}]
        result = HarnessRuntime._result(request(), answer, tools)
        assert result['message']['content'] == answer
        assert result['action']['name'] == 'chat.reply'
        assert result['workflow'] is None and 'task_id' not in result
        assert bool(result['artifacts']) == (verification == 'pass')


def test_inspecting_multiple_candidates_does_not_replace_model_explanation(tmp_path):
    answer = '旧任务失败过，但你正在看的《链表》已经完成。文档首先介绍节点的结构。'
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state)
        tools.outcomes = [{'ok': True, 'tool': 'query_report_job', 'data': {
            'task_id': task_id, 'status': status}} for task_id, status in [('old', 'failed'), ('current', 'succeeded')]]
        result = HarnessRuntime._result(request(), answer, tools)
        assert result['message']['content'] == answer
        assert result['artifacts'] == [] and 'task_id' not in result


def test_stream_final_answer_and_next_turn_history_remain_identical(tmp_path):
    answer = '报告已经完成。链表节点由数据域和指针域组成，插入时要先连接后继节点。'
    prompts, instances = [], []
    class SDK:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def close(self): pass
        def run(self, prompt, **kwargs):
            prompts.append(prompt)
            instances[-1].call('query_report_job', {'task_id': 'report-job'})
            for text in [answer[:12], answer[12:]]:
                kwargs['on_notification'](SimpleNamespace(method='session.event', payload={'event': {
                    'type': 'assistant/chunk', 'data': {'chunk': {'type': 'text-delta', 'text': text}}}}))
            return SimpleNamespace(final_response=answer, finish_reason='stop')
    def factory(request, session, **kwargs):
        tools = toolset(request, session, get_job=lambda _: job(), read_artifact=lambda *a: reviewed_artifact(), **kwargs)
        instances.append(tools)
        return tools
    runtime = HarnessRuntime(store=HarnessStore(tmp_path), tool_factory=factory, sdk_factory=SDK)
    events = list(runtime.run_stream(request=request(request_id='read'), snapshot=ConversationSnapshot()))
    displayed = ''.join(e['payload']['content'] for e in events if e['type'] == 'delta')
    final = next(e['payload'] for e in events if e['type'] == 'result')
    assert displayed == final['message']['content'] == answer
    assert not any(e['type'] == 'task_submitted' for e in events)
    runtime.run(request=request(request_id='follow-up', question='继续解释插入操作'), snapshot=ConversationSnapshot())
    data = json.loads(prompts[-1].split('\n', 1)[1])
    assert data['history_reference'][-1]['content'] == answer


def test_history_refresh_preserves_legacy_read_answers_but_updates_submissions(tmp_path):
    from app.chat.persistence.task_status_projection import project_task_status
    req = request()
    answer = '报告已完成。下面解释文档中的节点结构。'
    with HarnessStore(tmp_path).session(req) as state:
        state.data['responses']['read'] = {'request': {**req.model_dump(), 'question': '文档写了什么'}, 'result': {
            'task_id': 'existing', 'workflow': {'stage': 'result_check'}, 'message': {'content': answer}}}
        state.save()
    payload = {'conversation_id': req.conversation_id, 'course_id': req.course_id,
               'state': {'task_messages': {'read-message': 'existing', 'submit-message': 'new'}},
               'history': [{'role': 'user', 'content': '文档写了什么'},
                           {'role': 'assistant', 'message_id': 'read-message', 'content': answer},
                           {'role': 'assistant', 'message_id': 'submit-message', 'content': '正在生成'}]}
    reads = []
    tasks = SimpleNamespace(get=lambda task_id, **kw: reads.append(task_id) or {'status': 'succeeded'})
    projected = project_task_status(payload, req.owner, task_store=tasks, harness_root=tmp_path)
    assert projected['history'][1]['content'] == answer and 'task_id' not in projected['history'][1]
    assert '任务已完成' in projected['history'][2]['content']
    assert reads == ['new'] and payload['history'][2]['content'] == '正在生成'
