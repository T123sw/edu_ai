import json
from uuid import uuid4
from urllib.parse import quote

from fastapi.testclient import TestClient
import pytest

from edu_deeptutor.api import Settings, create_app
from edu_deeptutor.contracts import GenerateRequest, public_progress

TOKEN = "test-internal-service-key-32-characters"


class FakeGateway:
    def __init__(self):
        self.owners = {}
        self.payload = None

    async def start(self, owner, payload):
        self.payload = payload
        turn = f"{owner}:{payload['client_submission_id']}"
        self.owners[turn] = owner
        return {"turn_id": turn, "session_id": "session", "status": "running"}

    async def get(self, owner, turn_id):
        if self.owners.get(turn_id) == owner:
            return {"turn_id": turn_id, "status": "running"}

    async def events(self, owner, turn_id, after_seq):
        for event in [
            {"seq": 1, "type": "content", "content": "PRIVATE ANSWER", "stage": "quizzing",
             "metadata": {"qa_pair": {"correct_answer": "PRIVATE ANSWER"}, "question_index": 0}},
            {"seq": 2, "type": "done", "metadata": {"status": "completed"}},
        ]:
            if event["seq"] > after_seq:
                yield event

    async def cancel(self, owner, turn_id):
        return True

    async def close(self):
        pass


@pytest.fixture
def bridge():
    gateway = FakeGateway()
    with TestClient(create_app(settings=Settings(token=TOKEN), gateway=gateway)) as client:
        yield client, gateway


def headers(owner="alice"):
    return {"Authorization": f"Bearer {TOKEN}", "X-Edu-Owner": owner}


def create(client):
    response = client.post("/internal/generations", headers=headers(),
                           json={"request_id": str(uuid4()), "requirement": "生成排序练习"})
    assert response.status_code == 202
    return response.json()["turn_id"]


def test_internal_auth_and_owner_are_required(bridge):
    client, _ = bridge
    assert client.post("/internal/generations", json={}).status_code == 401
    assert client.post("/internal/generations", headers={"Authorization": f"Bearer {TOKEN}"}, json={}).status_code == 400


def test_owner_isolation_covers_status_events_and_cancel(bridge):
    client, _ = bridge
    turn = create(client)
    assert client.get(f"/internal/turns/{turn}", headers=headers()).status_code == 200
    for method, suffix in (("GET", ""), ("GET", "/events?view=internal"), ("POST", "/cancel")):
        assert client.request(method, f"/internal/turns/{turn}{suffix}", headers=headers("bob")).status_code == 404


def test_utf8_owner_identity_is_preserved(bridge):
    client, gateway = bridge
    actor = "学生甲"
    response = client.post("/internal/generations", headers=headers(quote(actor, safe="")),
                           json={"request_id": str(uuid4()), "requirement": "生成练习"})
    assert response.status_code == 202
    assert gateway.owners[response.json()["turn_id"]] == actor


def test_progress_hides_answers_but_internal_stream_preserves_them(bridge):
    client, _ = bridge
    turn = create(client)
    path = f"/internal/turns/{turn}/events"
    progress = client.get(path, headers=headers())
    assert "PRIVATE ANSWER" not in progress.text
    assert "qa_pair" not in progress.text
    internal = client.get(path + "?view=internal", headers=headers())
    assert "PRIVATE ANSWER" in internal.text
    resumed = client.get(path + "?after_seq=1", headers=headers())
    assert [json.loads(line)["seq"] for line in resumed.text.splitlines()] == [2]
    assert client.post(f"/internal/turns/{turn}/cancel", headers=headers()).json() == {"cancel_requested": True}


def test_request_validation_does_not_echo_uploaded_bytes_or_requirements(bridge):
    client, _ = bridge
    response = client.post("/internal/generations", headers=headers(), json={"request_id": "PRIVATE-DATA", "requirement": "PRIVATE-DATA"})
    assert response.status_code == 422
    assert "PRIVATE-DATA" not in response.text


def test_model_reference_and_real_request_are_forwarded(bridge):
    client, gateway = bridge
    request = {"request_id": str(uuid4()), "requirement": "必须使用 Lomuto 划分",
               "model_selection": {"profile_id": "profile-1", "model_id": "model-1"}}
    assert client.post("/internal/generations", headers=headers(), json=request).status_code == 202
    assert gateway.payload["content"] == request["requirement"]
    assert gateway.payload["llm_selection"] == request["model_selection"]
    assert gateway.payload["capability"] == "deep_question"
    assert gateway.payload["auto_route"] is False


def test_mimic_requires_one_explicit_template_and_never_accepts_server_paths():
    base = {"request_id": uuid4(), "requirement": "仿卷", "mode": "mimic"}
    with pytest.raises(ValueError):
        GenerateRequest(**base)
    with pytest.raises(ValueError):
        GenerateRequest(**base, paper_path="/etc/passwd")
    attachment = {"filename": "paper.pdf", "mime_type": "application/pdf", "type": "pdf", "base64": "JVBERi0="}
    request = GenerateRequest(**base, attachments=[attachment])
    assert request.upstream_payload(frozenset())["config"]["max_questions"] == 0
    with pytest.raises(ValueError):
        GenerateRequest(**base, attachments=[attachment, attachment])


def test_tools_require_server_allowlist(bridge):
    client, _ = bridge
    response = client.post("/internal/generations", headers=headers(), json={
        "request_id": str(uuid4()), "requirement": "quiz", "tools": ["arbitrary-exec"]})
    assert response.status_code == 422


def test_progress_projection_drops_every_free_text_payload():
    event = {"type": "result", "stage": "answer-is-secret", "content": "secret", "result": {"answer": "secret"},
             "metadata": {"error": "secret", "total_questions": "secret", "status": "secret"}}
    assert "secret" not in json.dumps(public_progress(event))


def test_service_and_provider_errors_do_not_leak_configuration(bridge):
    client, gateway = bridge
    async def fail(*args):
        raise RuntimeError("secret-api-key-and-prompt")
    gateway.start = fail
    response = client.post("/internal/generations", headers=headers(), json={"request_id": str(uuid4()), "requirement": "quiz"})
    assert response.status_code == 503
    assert "secret" not in response.text
    assert TOKEN not in repr(Settings(token=TOKEN))


@pytest.mark.asyncio
async def test_idle_ndjson_has_heartbeats_without_changing_event_sequence():
    import asyncio
    from edu_deeptutor.api import event_lines
    release = asyncio.Event()
    closed = asyncio.Event()
    async def source():
        try:
            await release.wait()
            yield {'seq': 8, 'type': 'done', 'metadata': {'status': 'completed'}}
        finally:
            closed.set()
    stream = event_lines(source(), heartbeat_seconds=0.005)
    assert await anext(stream) == '\n'
    assert await anext(stream) == '\n'
    assert not closed.is_set()
    release.set()
    event = json.loads(await anext(stream))
    assert event['seq'] == 8 and event['type'] == 'done'
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert closed.is_set()


@pytest.mark.asyncio
async def test_disconnect_during_idle_stream_closes_pending_reader():
    import asyncio
    from edu_deeptutor.api import event_lines
    closed = asyncio.Event()
    async def source():
        try:
            await asyncio.Event().wait()
            yield {}
        finally:
            closed.set()
    stream = event_lines(source(), heartbeat_seconds=0.005)
    assert await anext(stream) == '\n'
    await asyncio.wait_for(stream.aclose(), timeout=1)
    assert closed.is_set()


@pytest.mark.asyncio
async def test_stream_scope_is_preserved_across_yields_and_closed_in_same_task():
    import asyncio
    from contextvars import ContextVar
    from edu_deeptutor.api import event_lines
    scope = ContextVar('test_stream_owner', default='outside')
    closed = []
    async def source():
        token = scope.set('owner')
        task = asyncio.current_task()
        try:
            for seq in (1,2):
                assert scope.get() == 'owner' and asyncio.current_task() is task
                yield {'seq':seq,'type':'progress'}
        finally:
            assert asyncio.current_task() is task
            scope.reset(token)
            closed.append(True)
    lines = [line async for line in event_lines(source(), heartbeat_seconds=.005) if line.strip()]
    assert [json.loads(line)['seq'] for line in lines] == [1,2]
    assert closed == [True] and scope.get() == 'outside'


@pytest.mark.asyncio
async def test_stream_scope_is_closed_in_producer_on_disconnect():
    import asyncio
    from contextvars import ContextVar
    from edu_deeptutor.api import event_lines
    scope = ContextVar('test_stream_disconnect', default='outside')
    closed=[]
    async def source():
        token=scope.set('owner');task=asyncio.current_task()
        try:
            await asyncio.Event().wait()
            yield {}
        finally:
            assert asyncio.current_task() is task
            scope.reset(token);closed.append(True)
    stream=event_lines(source(), heartbeat_seconds=.005)
    assert await anext(stream)=='\n'
    await asyncio.wait_for(stream.aclose(),timeout=1)
    assert closed==[True] and scope.get()=='outside'
