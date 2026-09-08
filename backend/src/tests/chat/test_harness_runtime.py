import json
import subprocess
import sys
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from filelock import Timeout

from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.harness.bridge import tool_bridge
from app.chat.harness.runtime import HarnessRuntime
from app.chat.harness.store import HarnessStore
from app.chat.harness.tools import ReportTools
from app.chat.orchestrator.main_orchestrator import MainOrchestrator


def request(**kwargs):
    return ChatRequestV2(**{"question": "只生成递归教学报告大纲", "owner": "alice",
                           "course_id": "course1", "conversation_id": "conv1", **kwargs})


class Gateway:
    def chat(self, messages, **kwargs):
        count = json.loads(messages[-1]["content"])["section_count"]
        return json.dumps({"chapters": [{"title": f"章节{i}", "points": ["案例", "要点"]} for i in range(count)]})


def toolset(req, session, **kwargs):
    defaults = dict(request=req, session=session, gateway=Gateway(), emit=lambda event: None,
                    submit=lambda command: SimpleNamespace(edu_job_id="job_report"),
                    get_job=lambda task: None, read_artifact=lambda ref, owner: None,
                    cancel_job=lambda *a, **kw: None, validate_scope=lambda req: None)
    return ReportTools(**{**defaults, **kwargs})


def draft(tools, **kwargs):
    outcome = tools.call("draft_report_outline", {"subject": "递归", "section_count": 3, **kwargs})
    assert outcome["ok"], outcome
    # Fixture for an outline already shown in a previous user turn.
    outline = outcome['data']
    outline.update(presented_revision=outline['revision'], presented_request_id='fixture-outline-turn', created_request_id='fixture-outline-turn')
    tools.session.save()
    return outline


def ref(outline):
    return {k: outline[k] for k in ("outline_id", "revision")}


@pytest.mark.parametrize("utterance", ["开始", "go ahead", "Sí, adelante", "按刚才讨论的结构写"])
def test_model_submission_is_language_independent_and_version_bound(tmp_path, utterance):
    store = HarnessStore(tmp_path)
    calls = []
    submit = lambda command: calls.append(command) or SimpleNamespace(edu_job_id="job_report")
    with store.session(request()) as state:
        outline = draft(toolset(request(), state))
    with store.session(request()) as state:
        tools = toolset(request(question="修改大纲"), state)
        revised = draft(tools, revise_outline_id=outline["outline_id"])
        assert not tools.call("submit_report", ref(outline))["ok"]
    with store.session(request()) as state:
        tools = toolset(request(question=utterance, request_id="decision1"), state, submit=submit)
        assert tools.call("submit_report", ref(revised))["ok"]
        assert tools.call("submit_report", ref(revised))["data"]["task_id"] == "job_report"
        assert len(calls) == 1
        assert state.data['outlines'][revised['outline_id']]['confirmation']['user_message'] == utterance
        assert calls[0].config['harness_approval_request_id'] == 'decision1'


def test_model_decides_not_to_call_submit_and_scope_cannot_be_overridden(tmp_path):
    store = HarnessStore(tmp_path)
    with store.session(request()) as state:
        outline = draft(toolset(request(), state))
    with store.session(request(scope_id='other', scope_type='knowledge_point')) as state:
        calls = []
        tools = toolset(request(scope_id='other', scope_type='knowledge_point'), state,
                        submit=lambda command: calls.append(command))
        assert not tools.call('submit_report', ref(outline))['ok']
        assert not tools.call('submit_report', {**ref(outline), 'approved': True})['ok']
        assert calls == []


def test_store_isolates_actors_and_courses_but_retains_scope_history(tmp_path):
    store = HarnessStore(tmp_path)
    with store.session(request()) as state:
        outline = draft(toolset(request(), state))
        with pytest.raises(Timeout):
            with store.session(request(scope_id='node2')):
                pass
    for other in [request(owner="bob"), request(course_id="course2"), request(conversation_id='other')]:
        with store.session(other) as state:
            assert state.data["outlines"] == {}
    with store.session(request(scope_id='node2')) as state:
        assert outline['outline_id'] in state.data['outlines']


def test_submission_error_keeps_decision_and_reuses_idempotency_key(tmp_path):
    calls = []
    def submit(command):
        calls.append(command)
        if len(calls) == 1: raise RuntimeError('interrupted')
        return SimpleNamespace(edu_job_id='job_report')
    store = HarnessStore(tmp_path)
    with store.session(request()) as state:
        tools = toolset(request(question='go ahead', request_id='first'), state, submit=submit)
        outline = draft(tools)
        assert not tools.call('submit_report', ref(outline))['ok']
        assert outline['status'] == 'confirmed'
    with store.session(request()) as state:
        tools = toolset(request(question='resume', request_id='retry'), state, submit=submit)
        assert tools.call('submit_report', ref(outline))['ok']
        assert calls[0].idempotency_key == calls[1].idempotency_key
        assert calls[1].config['harness_approval_request_id'] == 'first'


def test_search_permission_errors_and_explicit_evidence(tmp_path):
    calls = []
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state, web=lambda **kw: calls.append(kw))
        assert "web_search" not in {s["name"] for s in tools.schemas()}
        assert not tools.call("web_search", {"query": "递归"})["ok"]
        assert calls == []
        req = request(capability={"allow_web": True})
        tools = toolset(req, state, web=lambda **kw: {"ok": False})
        assert tools.call("web_search", {"query": "递归"})["error"] == "retrieval_failed"
        tools.web = lambda **kw: {"ok": True, "payload": {"summary": "来源摘要", "sources": [{"url": "https://example.org"}]}}
        evidence = tools.call("web_search", {"query": "递归"})["data"]
        outline = draft(tools, evidence_ids=[evidence["evidence_id"]])
        assert outline["evidence_ids"] == [evidence["evidence_id"]]
        changed = toolset(request(question="确认大纲并继续"), state)
        assert not changed.call("submit_report", ref(outline))["ok"]


def test_bad_outline_count_fails_without_saved_artifact(tmp_path):
    class BadGateway:
        def chat(self, *a, **kw):
            return '{"chapters": []}'
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state, gateway=BadGateway())
        assert not tools.call("draft_report_outline", {"subject": "递归", "section_count": 2})["ok"]
        invalid = tools.call("draft_report_outline", {"subject": "递归"})
        assert not invalid["ok"] and invalid["retryable"]
        assert state.data["outlines"] == {}
        tools.gateway = Gateway()
        assert tools.call("draft_report_outline", {"subject": "递归"})["data"]["revision"] == 1


def test_query_cannot_read_other_jobs_and_checks_actual_artifact(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        outline = draft(toolset(request(), state))
        state.data["jobs"]["job_report"] = {**ref(outline)}
        job = SimpleNamespace(owner_user_id="alice", course_id="course1", status="succeeded",
                              progress=100, result_ref={"material_id": "report1"})
        tools = toolset(request(), state, get_job=lambda task: job,
                        read_artifact=lambda ref, owner: {"content": "正文缺少大纲章节"})
        assert not tools.call("query_report_job", {"task_id": "job_other"})["ok"]
        result = tools.call("query_report_job", {"task_id": "job_report"})
        assert result["data"]["verification"]["decision"] == "fail"
        tools.read_artifact = lambda ref, owner: {"content": outline["markdown"] + "\n正文内容" * 100}
        unreviewed = tools.call("query_report_job", {"task_id": "job_report"})["data"]
        assert unreviewed["verification"]["decision"] == "fail" and "artifact" not in unreviewed
        from app.chat.harness.reviewed_report import CRITERIA, digest
        body = outline["markdown"] + "\n正文内容" * 100
        tools.read_artifact = lambda ref, owner: {"content": body, "generation_state": {"report_review": {
            "decision": "pass", "method": "model_review", "content_sha256": digest(body),
            "checks": [{"criterion": c, "passed": True} for c in CRITERIA]}}}
        assert tools.call("query_report_job", {"task_id": "job_report"})["data"]["verification"]["decision"] == "pass"
        job.owner_user_id = "bob"
        assert not tools.call("query_report_job", {"task_id": "job_report"})["ok"]


def test_mcp_stdio_bridge_and_bearer_auth(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state)
        with tool_bridge(tools) as (url, token):
            with pytest.raises(HTTPError) as exc:
                urlopen(Request(url, data=b'{}', method="POST"))
            assert exc.value.code == 403
            import os
            from app.chat.harness import mcp_proxy
            payload = '\n'.join(json.dumps({"jsonrpc": "2.0", "id": i, "method": method})
                                for i, method in enumerate(["initialize", "tools/list", "ping"])) + '\n'
            result = subprocess.run([sys.executable, mcp_proxy.__file__], input=payload, text=True,
                                    capture_output=True, timeout=10,
                                    env={**os.environ, "EDU_MCP_URL": url, "EDU_MCP_TOKEN": token})
            assert result.returncode == 0, result.stderr
            responses = [json.loads(line) for line in result.stdout.splitlines()]
            assert responses[0]["result"]["serverInfo"]["name"] == "edu-report"
            assert "submit_report" in {t["name"] for t in responses[1]["result"]["tools"]}
            assert responses[2]["result"] == {}


def test_runtime_rehydrates_history_replays_and_filters_reasoning(tmp_path):
    prompts, configurations, closes = [], [], []
    class SDK:
        def __init__(self, **kwargs):
            configurations.append(kwargs)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()
        def close(self):
            closes.append(True)
        def run(self, prompt, **kwargs):
            prompts.append(prompt)
            for kind, value in [("reasoning-delta", "PRIVATE"), ("text-delta", "你好")]:
                kwargs["on_notification"](SimpleNamespace(method="session.event", payload={"event": {
                    "type": "assistant/chunk", "data": {"chunk": {"type": kind, "text": value}}}}))
            return SimpleNamespace(final_response="你好", finish_reason="stop")
    def factory(request, session, **kwargs):
        return toolset(request, session, **kwargs)
    runtime = HarnessRuntime(store=HarnessStore(tmp_path), tool_factory=factory, sdk_factory=SDK)
    req = request(question="我是李老师", request_id="first")
    events = list(runtime.run_stream(request=req, snapshot=ConversationSnapshot()))
    assert [e["payload"]["content"] for e in events if e["type"] == "delta"] == ["你好"]
    assert events[-1]["payload"]["trace"]["path"] == "deepseek-harness"
    replay = runtime.run(request=req, snapshot=ConversationSnapshot())
    assert replay["trace"]["response_replayed"]
    assert len(prompts) == 1
    runtime = HarnessRuntime(store=HarnessStore(tmp_path), tool_factory=factory, sdk_factory=SDK)
    runtime.run(request=request(question="我是谁", request_id="second"), snapshot=ConversationSnapshot())
    assert "我是李老师" in prompts[-1]
    assert configurations[0]["profile"] == "sdk-minimal"
    assert closes


def test_orchestrator_routes_sync_and_report_hint_to_harness():
    calls = []
    class Runtime:
        def run(self, **kwargs):
            calls.append("sync")
            return {"ok": True}
        def run_stream(self, **kwargs):
            calls.append("stream")
            yield {"type": "result", "payload": {"ok": True}}
    orchestrator = MainOrchestrator(fast_runtime=None, workflow_registry={},
                                   context_builder=SimpleNamespace(build=lambda req: ConversationSnapshot()),
                                   harness_runtime=Runtime())
    assert orchestrator.dispatch(request()) == {"ok": True}
    assert list(orchestrator.dispatch_stream(request(action_hint="generate.report")))[0]["type"] == "result"
    assert calls == ["sync", "stream"]
    assert not HarnessRuntime.supports(request(action_hint="generate.quiz"))


def test_http_response_model_preserves_harness_fields(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth import get_current_user
    from app.chat.api.routes_v2 import router
    from app.chat.api.schemas_v2 import ChatResponseV2
    result = {"message": {"role": "assistant", "content": "任务已提交"},
              "conversation": {"conversation_id": "conv1"}, "action": {"name": "generate.report"},
              "trace": {"path": "deepseek-harness"}, "task_id": "job_report",
              "harness_outline": {"outline_id": "outline1", "revision": 1, "subject": "递归"},
              "verification": {"decision": "pass"}}
    assert ChatResponseV2.model_validate(result).task_id == "job_report"
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "alice"}
    class Service:
        def reply(self, payload):
            assert payload.owner == "alice"
            return result
    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: Service())
    response = TestClient(app).post("/api/chat/v2/reply", json={"question": "确认大纲并继续"})
    assert response.status_code == 200
    assert response.json()["task_id"] == "job_report"
    assert response.json()["harness_outline"]["revision"] == 1


def test_failed_enqueue_is_not_reported_as_submitted(tmp_path):
    store = HarnessStore(tmp_path)
    with store.session(request()) as state:
        outline = draft(toolset(request(), state))
    with store.session(request()) as state:
        tools = toolset(request(question="确认大纲并继续"), state,
                        submit=lambda command: SimpleNamespace(edu_job_id="job_failed", status="failed"))
        first = tools.call("submit_report", ref(outline))
        second = tools.call("submit_report", ref(outline))
        assert not first["ok"] and not second["ok"]
        assert "job_failed" in state.data["jobs"]


def test_report_http_entry_uses_unified_harness_path(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth import get_current_user
    from app.chat.api.routes_v2 import router
    from core.config import Config
    received = []
    monkeypatch.setattr(Config, "USE_DEEPSEEK_HARNESS", True)
    class Service:
        def reply(self, payload):
            received.append(payload)
            return {"message": {"role": "assistant", "content": "大纲"},
                    "conversation": {"conversation_id": "conv1"}, "action": {"name": "generate.report"},
                    "trace": {"path": "deepseek-harness"}}
    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: Service())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "alice"}
    client = TestClient(app)
    response = client.post("/api/chat/v2/report", json={"question": "生成报告大纲", "report_config": {"length": "800字"}})
    assert response.status_code == 200
    assert received[-1].action_hint == "generate.report" and "800字" in received[-1].question
    response = client.post("/api/chat/v2/report", json={"question": "确认大纲并继续", "report_config": {"length": "800字"}})
    assert response.status_code == 200 and received[-1].question.startswith("确认大纲并继续\n报告要求：")


def test_runtime_closes_sdk_on_timeout(tmp_path):
    import threading
    released = threading.Event()
    class SDK:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()
        def close(self):
            released.set()
        def run(self, *args, **kwargs):
            released.wait(5)
            return SimpleNamespace(final_response="", finish_reason="completed")
    runtime = HarnessRuntime(store=HarnessStore(tmp_path), sdk_factory=SDK, timeout=.3,
                             tool_factory=lambda request, session, **kw: toolset(request, session, **kw))
    result = runtime.run(request=request(), snapshot=ConversationSnapshot())
    assert result["trace"]["error"] == "harness_timeout"
    assert released.is_set()


def organization_fixture():
    return {"scope": "仅研究有序数组二分查找的边界与循环不变量", "prerequisites": ["数组与循环"],
            "objectives": ["解释循环不变量为何保持", "追踪边界更新与终止"],
            "units": [{"title": f"边界模块{i}", "explanation": "明确有序数组候选区间在更新前后必须保留所有可能解的位置。",
                       "example": "在数组 [1, 3, 5, 7] 中查找 5 并逐步记录左右边界。",
                       "misconception": "混用闭区间和半开区间更新规则可能漏掉末尾元素。",
                       "check": "对空数组和单元素数组分别追踪退出条件并解释结果。",
                       "objective_indices": [i % 2], "evidence_ids": []} for i in range(3)], "limitations": []}


class OrganizedGateway:
    def __init__(self, invalid=False):
        self.invalid = invalid
    def chat(self, messages, **kwargs):
        prompt = json.loads(messages[-1]['content'])
        if 'content' in prompt and 'request' in prompt:
            return json.dumps({'passed': True, 'issues': [], 'checks': [{'passed':True,'reason':'checked'}]*4})
        if 'section_count' not in prompt:
            value = organization_fixture()
            if self.invalid:
                value['units'][0]['evidence_ids'] = ['fabricated']
            return json.dumps(value)
        return json.dumps({'chapters': [{'title': f'边界章节{i}', 'points': ['具体区间和例子'],
                             'unit_indices': [0 if self.invalid else i]} for i in range(3)]})


def test_organization_rejects_fabricated_evidence_and_does_not_save(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state, gateway=OrganizedGateway(invalid=True))
        result = tools.call('organize_report_content', {'subject': '二分查找'})
        assert not result['ok'] and result['retryable']
        assert not state.data.get('organizations')


def test_organized_outline_covers_units_and_rejects_stale_requirements(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        gateway = OrganizedGateway()
        tools = toolset(request(), state, gateway=gateway)
        organization = tools.call('organize_report_content', {'subject': '二分查找'})['data']
        args = {'subject': '二分查找', 'section_count': 3, 'organization_id': organization['organization_id']}
        assert not tools.call('draft_report_outline', {**args, 'requirements': '新要求'})['ok']
        gateway.invalid = True
        assert not tools.call('draft_report_outline', args)['ok']
        assert not state.data['outlines']
        gateway.invalid = False
        outline = tools.call('draft_report_outline', args)['data']
        assert outline['quality']['objective_coverage']
        assert '学习目标' not in outline['markdown'] and '自检：' not in outline['markdown']
        assert len(outline['markdown']) < 400
        assert state.data['organizations'][organization['organization_id']]['units'][0]['example']
        assert outline['quality']['semantic_review'] == 'not_performed'


def test_search_normalizes_sources_and_rejects_unusable_urls(tmp_path):
    req = request(capability={'allow_web': True})
    with HarnessStore(tmp_path).session(req) as state:
        tools = toolset(req, state, web=lambda **kw: {'ok': True, 'payload': {'sources': [
            {'url': 'https://example.org/a#first'}, {'url': 'https://example.org/a#second'},
            {'url': 'javascript:alert(1)'}, {'url': 'https://user:password@example.org'}]}})
        result = tools.call('web_search', {'query': '二分查找'})['data']
        assert len(result['sources']) == 1
        assert result['sources'][0]['url'] == 'https://example.org/a'
        assert result['retrieved_at'] and result['trust'] == 'untrusted_reference'


def test_web_domain_filter_is_enforced_by_server(tmp_path):
    req = request(capability={'allow_web': True})
    with HarnessStore(tmp_path).session(req) as state:
        calls = []
        def web(**kwargs):
            calls.append(kwargs)
            return {'ok': True, 'payload': {'sources': [{'url': 'https://fake-docs.python.org.evil.test/a'}]}}
        tools = toolset(req, state, web=web)
        result = tools.call('web_search', {'query': 'bisect', 'domains': ['docs.python.org']})
        assert not result['ok'] and result['error'] == 'no_sources_found'
        assert 'site:docs.python.org' in calls[0]['query']
        assert not tools.call('web_search', {'query': 'bisect', 'domains': ['https://docs.python.org']})['ok']


def test_content_gateway_disables_only_supported_thinking_mode():
    from app.chat.harness.content_gateway import ContentGateway
    assert ContentGateway._thinking_params('deepseek-v4-flash') == {'thinking': {'type': 'disabled'}}
    assert ContentGateway._thinking_params('qwen3-test') == {'enable_thinking': False}
    assert ContentGateway._thinking_params('unrelated') == {}


def test_reference_pages_block_private_or_unapproved_hosts_before_network(monkeypatch):
    from app.chat.harness.web_sources import read_reference_pages
    import socket
    calls=[]
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: calls.append(a) or [])
    for url in ['http://docs.python.org/a', 'https://127.0.0.1/a', 'https://docs.python.org.evil.test/a',
                'https://user:password@docs.python.org/a']:
        with pytest.raises(ValueError, match='reference_host_not_supported'):
            read_reference_pages([url], [])
    assert not calls
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(None,None,None,None,('127.0.0.1',443))])
    with pytest.raises(ValueError, match='reference_address_not_public'):
        read_reference_pages(['https://docs.python.org/3/library/bisect.html'], [])


def test_reference_page_evidence_retains_provenance(tmp_path, monkeypatch):
    from app.chat.harness import web_sources
    req=request(capability={'allow_web':True})
    monkeypatch.setattr(web_sources, 'read_reference_pages', lambda urls, domains: [
        {'url':urls[0], 'title':'Python docs', 'excerpt':'Direct page excerpt', 'retrieval_mode':'direct_reference_page'}])
    with HarnessStore(tmp_path).session(req) as state:
        tools=toolset(req, state, web=lambda **kw: pytest.fail('must not call search when reading reference'))
        result=tools.call('web_search', {'query':'bisect', 'reference_urls':['https://docs.python.org/3/library/bisect.html']})
        assert result['ok']
        assert result['data']['coverage']=='reference_page_excerpt'
        assert result['data']['sources'][0]['retrieval_mode']=='direct_reference_page'


def test_semantic_review_rejects_content_before_persistence(tmp_path):
    class RejectingGateway(OrganizedGateway):
        def chat(self, messages, **kwargs):
            prompt=json.loads(messages[-1]['content'])
            if 'content' in prompt and 'request' in prompt:
                return json.dumps({'passed':False,'checks':[{'passed':False,'reason':'越界反例'}]*4,'issues':['插入点可能等于数组长度，访问前必须检查范围。']})
            return super().chat(messages, **kwargs)
    with HarnessStore(tmp_path).session(request()) as state:
        tools=toolset(request(), state, gateway=RejectingGateway())
        result=tools.call('organize_report_content', {'subject':'二分查找'})
        assert result['error']=='content_quality_failed' and result['retryable']
        assert '数组长度' in result['issues']
        assert not state.data.get('organizations')


def test_failed_organization_cannot_be_bypassed_with_legacy_draft(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        tools=toolset(request(), state, gateway=OrganizedGateway(invalid=True))
        assert not tools.call('organize_report_content', {'subject':'二分查找'})['ok']
        result=tools.call('draft_report_outline', {'subject':'二分查找','section_count':3})
        assert result['error']=='organization_required_after_content_planning'
        assert not state.data['outlines']


def test_content_failures_have_a_server_retry_limit(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        tools=toolset(request(), state, gateway=OrganizedGateway(invalid=True))
        for _ in range(3):
            assert tools.call('organize_report_content', {'subject':'二分查找'})['retryable']
        result=tools.call('organize_report_content', {'subject':'二分查找'})
        assert result['error']=='content_retry_budget_exhausted' and not result['retryable']


def test_report_subject_stays_on_named_subtopic_of_combined_node(tmp_path):
    from app.chat.application.knowledge_context import ResolvedWorkspaceContext
    req = request(question='数组的实现报告', scope_type='knowledge_point', scope_id='array-linked-list',
                  workspace_context=ResolvedWorkspaceContext(course_id='course1', scope_type='knowledge_point',
                      scope_id='array-linked-list', scope_title='数组与链表', scope_path=['课程', '数组与链表'], resolution='resolved'))
    with HarnessStore(tmp_path).session(req) as state:
        outline = draft(toolset(req, state), subject='数组的实现')
        assert outline['subject'] == '数组的实现'
        assert '数组与链表' not in outline['markdown']


def test_legacy_shard_migrates_outline_and_keeps_owner_isolation(tmp_path):
    import hashlib
    req = request(scope_type='knowledge_point', scope_id='array')
    legacy_key = hashlib.sha256(json.dumps([req.owner, req.course_id, req.scope_type, req.scope_id, req.conversation_id]).encode()).hexdigest()
    legacy = tmp_path / legacy_key
    legacy.mkdir()
    legacy.joinpath('state.json').write_text(json.dumps({'version': 1, 'history': [{'role': 'user', 'content': '数组报告'}],
        'active_outline': 'old', 'outlines': {'old': {'outline_id': 'old', 'revision': 1, 'subject': '数组', 'source_policy': {'allow_rag': False}}},
        'evidence': {}, 'jobs': {}, 'responses': {'turn': {'request': req.model_dump(mode='json'), 'result': {}}}}))
    with HarnessStore(tmp_path).session(req.model_copy(update={'scope_id': 'other'})) as state:
        assert state.data['outlines']['old']['workspace']['scope_id'] == 'array'
        assert state.data['outlines']['old']['source_policy']['scope_id'] == 'array'
    with HarnessStore(tmp_path).session(req.model_copy(update={'owner': 'bob'})) as state:
        assert not state.data['outlines']
    assert legacy.joinpath('state.json').exists()


def test_model_workspace_selection_preserves_topic_and_working_memory(tmp_path):
    course = SimpleNamespace(get_course_info=lambda cid: {'name': '课程'}, get_knowledge_graph=lambda cid: {
        'root': {'id': 'root', 'label': '课程', 'children': [{'id': 'array-list', 'label': '数组与链表'}]}})
    req = request(scope_type='course')
    with HarnessStore(tmp_path).session(req) as state:
        tools = toolset(req, state, course_storage=course)
        outcome = tools.call('select_workspace', {'scope_type': 'knowledge_point', 'scope_id': 'array-list', 'topic': 'Array implementation'})
        assert outcome['ok']
        assert req.scope_id == 'array-list' and req.workspace_context.update_workspace
        assert state.data['discussion_workspace']['topic'] == 'Array implementation'
        assert not tools.call('select_workspace', {'scope_type': 'knowledge_point', 'scope_id': 'foreign', 'topic': '数组'})['ok']
        assert tools.call('update_working_memory', {'goal': '数组报告', 'confirmed_facts': ['用户要求英文正文'], 'plan': ['按当前大纲写正文']})['ok']
    with HarnessStore(tmp_path).session(request(scope_type='course')) as state:
        assert state.data['working_memory']['confirmed_facts'] == ['用户要求英文正文']


def test_rag_enabled_does_not_implicitly_request_background_retrieval(tmp_path):
    req = request(capability={'allow_rag': True, 'selected_doc_ids': ['doc1']})
    commands = []
    with HarnessStore(tmp_path).session(req) as state:
        tools = toolset(req, state, submit=lambda command: commands.append(command) or SimpleNamespace(edu_job_id='job1'))
        outline = draft(tools)
        assert tools.call('submit_report', ref(outline))['ok']
        assert commands[0].source_mode == 'none'
        assert commands[0].selected_doc_ids == []
        assert commands[0].config['allow_rag'] is True


def test_model_can_explicitly_choose_additional_retrieval(tmp_path):
    req = request(capability={'allow_rag': True})
    commands = []
    with HarnessStore(tmp_path).session(req) as state:
        tools = toolset(req, state, submit=lambda command: commands.append(command) or SimpleNamespace(edu_job_id='job1'))
        outline = draft(tools)
        assert tools.call('submit_report', {**ref(outline), 'source_mode': 'course_auto'})['ok']
        assert commands[0].source_mode == 'course_auto'


def test_model_cannot_override_disabled_retrieval(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state)
        outline = draft(tools)
        assert tools.call('submit_report', {**ref(outline), 'source_mode': 'course_auto'})['error'] == 'retrieval_not_allowed'


def test_quota_error_is_public_and_reaches_model_as_distinct_failure(tmp_path):
    from core.embedding_errors import embedding_response_error
    failure = embedding_response_error(403, {'error': {'code': 'local:insufficient_quota', 'message': 'raw provider request-id secret'}})
    assert failure.code == 'EMBEDDING_QUOTA_EXHAUSTED'
    assert '额度不足' in str(failure) and 'secret' not in str(failure)
    req = request(capability={'allow_rag': True})
    with HarnessStore(tmp_path).session(req) as state:
        tools = toolset(req, state, rag=lambda **kw: {'ok': False, 'error_code': failure.code, 'error': str(failure)})
        outcome = tools.call('rag_search', {'query': '链表'})
        assert not outcome['ok'] and not outcome['retryable']
        assert 'EMBEDDING_QUOTA_EXHAUSTED' in outcome['error']
        assert not state.data['evidence']


def test_historical_embedding_error_is_redacted_without_mutation():
    from core.embedding_errors import public_legacy_embedding_error
    raw = 'Embedding API错误: HTTP 403 - ' + json.dumps({'error': {'code': 'local:insufficient_quota', 'message': 'provider-private-detail'}})
    assert '额度不足' in public_legacy_embedding_error(raw)
    assert 'provider-private-detail' not in public_legacy_embedding_error(raw)
    assert public_legacy_embedding_error('普通错误说明') == '普通错误说明'


def test_background_retrieval_quota_is_a_typed_task_failure():
    from app.services.generation_task_handlers import GenerationTaskHandler
    from app.services.durable_task_handlers import DurableTaskExecutionError
    from core.embedding_errors import embedding_response_error
    def resolve(*args, **kwargs):
        raise embedding_response_error(403, {'error': {'code': 'local:insufficient_quota'}})
    handler = GenerationTaskHandler(course_storage_manager=SimpleNamespace(), source_resolver=SimpleNamespace(resolve=resolve))
    with pytest.raises(DurableTaskExecutionError) as failure:
        handler.handle({'resource_type': 'report', 'course_id': 'course1', 'source_mode': 'course_auto'},
                       SimpleNamespace(owner_user_id='alice', course_id='course1'))
    assert failure.value.code == 'EMBEDDING_QUOTA_EXHAUSTED'


def test_new_outline_cannot_submit_until_presented_and_next_user_turn(tmp_path):
    req = request(request_id='outline-turn')
    store = HarnessStore(tmp_path)
    commands = []
    submit = lambda command: commands.append(command) or SimpleNamespace(edu_job_id='job1')
    with store.session(req) as state:
        tools = toolset(req, state, submit=submit)
        outline = tools.call('draft_report_outline', {'subject': '数组', 'section_count': 3})['data']
        assert not tools.call('submit_report', ref(outline))['ok']
        response = HarnessRuntime._result(req, '', tools)
        assert response['harness_outline']['revision'] == 1
        assert not tools.call('submit_report', ref(outline))['ok']
        assert commands == []
    next_req = request(question='Go ahead', request_id='user-confirmation-turn')
    with store.session(next_req) as state:
        tools = toolset(next_req, state, submit=submit)
        assert tools.call('submit_report', ref(outline))['ok']
        assert len(commands) == 1


def test_revision_cannot_reuse_previous_presentation(tmp_path):
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state)
        old = draft(tools)
        revised = tools.call('draft_report_outline', {'subject': '数组', 'section_count': 3, 'revise_outline_id': old['outline_id']})['data']
        assert not tools.call('submit_report', ref(revised))['ok']
        assert not revised.get('presented_revision')


@pytest.mark.parametrize('rag_on,web_on', [(False,False),(True,False),(False,True),(True,True)])
def test_buttons_mean_required_not_permission(monkeypatch, rag_on, web_on):
    from core.config import Config
    from app.chat.application.request_normalizer import normalize_chat_request
    monkeypatch.setattr(Config, 'USE_DEEPSEEK_HARNESS', True)
    req = normalize_chat_request(SimpleNamespace(question='问题', allow_rag=rag_on, allow_web=web_on))
    assert req.capability.allow_rag and req.capability.allow_web
    assert req.capability.require_rag == rag_on and req.capability.require_web == web_on


def test_required_retrieval_blocks_report_until_tool_succeeds(tmp_path):
    req = request(capability={'allow_rag': True, 'require_rag': True})
    with HarnessStore(tmp_path).session(req) as state:
        tools = toolset(req, state, rag=lambda **kw: {'ok': True, 'payload': {'answer':'课程中的数组知识', 'sources':[{'title':'课程资料'}]}})
        assert tools.required_retrieval_missing() == ['rag_search']
        assert not tools.call('draft_report_outline', {'subject':'数组','section_count':3})['ok']
        evidence = tools.call('rag_search', {'query':'数组'})
        assert evidence['ok'] and not tools.required_retrieval_missing()
        assert tools.call('draft_report_outline', {'subject':'数组','section_count':3,'evidence_ids':[evidence['data']['evidence_id']]})['ok']


def test_outline_section_titles_are_headings_not_summary_bullets(tmp_path):
    class TitleGateway:
        def chat(self, messages, **kwargs):
            return json.dumps({'chapters': [{'title': f'章节{i}', 'section_titles': ['内存布局', '地址计算']} for i in range(3)]})
    with HarnessStore(tmp_path).session(request()) as state:
        tools = toolset(request(), state, gateway=TitleGateway())
        outline = draft(tools)
        assert '### 1.1 内存布局' in outline['markdown']
        assert '### 3.2 地址计算' in outline['markdown']
        assert '\n- ' not in outline['markdown']
        assert outline['chapters'][0]['points'] == ['内存布局', '地址计算']


def test_outline_stream_never_exposes_model_rewrite_before_saved_outline(tmp_path):
    instances = []
    def factory(request, session, **kwargs):
        instance = toolset(request, session, **kwargs)
        instances.append(instance)
        return instance
    class SDK:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def close(self): pass
        def run(self, prompt, **kwargs):
            outcome = instances[0].call('draft_report_outline', {'subject': '链表', 'section_count': 3})
            assert outcome['ok']
            kwargs['on_notification'](SimpleNamespace(method='session.event', payload={'event': {
                'type': 'assistant/chunk', 'data': {'chunk': {
                    'type': 'text-delta', 'text': '# 模型另写的大纲\n## 不同章节'}}}}))
            return SimpleNamespace(final_response='# 模型另写的大纲', finish_reason='stop')
    store = HarnessStore(tmp_path)
    req = request(request_id='outline-stream')
    runtime = HarnessRuntime(store=store, tool_factory=factory, sdk_factory=SDK)
    events = list(runtime.run_stream(request=req, snapshot=ConversationSnapshot()))
    assert not [event for event in events if event['type'] == 'delta']
    result = events[-1]['payload']
    with store.session(req) as state:
        outline = state.data['outlines'][result['harness_outline']['outline_id']]
        assert result['message']['content'].startswith(outline['markdown'])
        assert outline['presented_revision'] == result['harness_outline']['revision']
    assert '模型另写' not in result['message']['content']


@pytest.mark.parametrize('status,expected', [('succeeded', '任务已完成'), ('running', '任务正在进行'), ('failed', '任务生成失败')])
def test_conversation_projects_durable_task_status_without_mutating_history(tmp_path, status, expected):
    from app.chat.persistence.task_status_projection import project_task_status
    payload = {'conversation_id': 'c', 'course_id': 'course1', 'state': {'task_messages': {'m': 'job1'}},
               'history': [{'message_id': 'm', 'role': 'assistant', 'content': '正在生成'}]}
    class Tasks:
        def get(self, task_id, owner_user_id):
            return {'status': status} if owner_user_id == 'alice' else None
    projected = project_task_status(payload, 'alice', task_store=Tasks(), harness_root=tmp_path)
    assert expected in projected['history'][0]['content']
    assert projected['history'][0]['task_id'] == 'job1'
    assert payload['history'][0]['content'] == '正在生成'
    assert 'task_id' not in project_task_status(payload, 'bob', task_store=Tasks(), harness_root=tmp_path)['history'][0]
