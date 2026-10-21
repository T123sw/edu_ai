import json
from uuid import uuid4

import httpx
import pytest

from app.integrations.deeptutor import DeepTutorClient, DeepTutorConfig, DeepTutorError

TOKEN = "internal-test-token-with-32-characters"


@pytest.mark.asyncio
async def test_client_keeps_causal_request_and_event_cursor():
    seen = []
    async def handle(request):
        seen.append(request)
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        assert request.headers["X-Edu-Owner"] == "alice"
        if request.url.path.endswith("/events"):
            return httpx.Response(200, content='{"seq":3,"type":"done"}\n', headers={"Content-Type": "application/x-ndjson"})
        return httpx.Response(202, json={"turn_id": "turn1", "session_id": "s1", "status": "running"})
    payload = {"request_id": str(uuid4()), "requirement": "生成十五题"}
    async with DeepTutorClient(DeepTutorConfig("http://bridge:8026", TOKEN), transport=httpx.MockTransport(handle)) as client:
        assert (await client.start(owner="alice", request=payload))["turn_id"] == "turn1"
        assert json.loads(seen[0].content) == payload
        assert [event async for event in client.progress(owner="alice", turn_id="turn1", after_seq=2)] == [{"seq": 3, "type": "done"}]
        assert seen[-1].url.params["after_seq"] == "2"
        assert seen[-1].url.params["view"] == "progress"
        _ = [event async for event in client.internal_events(owner="alice", turn_id="turn1")]
        assert seen[-1].url.params["view"] == "internal"


@pytest.mark.asyncio
async def test_client_does_not_expose_provider_error_text():
    async def handle(request):
        return httpx.Response(503, json={"detail": "SECRET-KEY-AND-ANSWER"})
    async with DeepTutorClient(DeepTutorConfig("http://bridge", TOKEN), transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(DeepTutorError) as failure:
            await client.status(owner="alice", turn_id="turn")
        assert failure.value.status_code == 503
        assert "SECRET" not in str(failure.value)
    assert TOKEN not in repr(DeepTutorConfig("http://bridge", TOKEN))


@pytest.mark.asyncio
async def test_transport_failure_can_be_retried_with_same_request_id():
    async def handle(request):
        raise httpx.ConnectError("private-service-location", request=request)
    async with DeepTutorClient(DeepTutorConfig("http://bridge", TOKEN), transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(DeepTutorError, match="unavailable") as failure:
            await client.start(owner="alice", request={"request_id": str(uuid4()), "requirement": "quiz"})
        assert failure.value.status_code == 503


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://user:secret@host", "https://host?secret=x"])
def test_only_configured_http_origins_are_accepted(url):
    with pytest.raises(ValueError):
        DeepTutorConfig(url, TOKEN)
