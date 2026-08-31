"""OpenMaicClient 单测（SPEC-07 / ACC-07，聚焦本轮 P2-3 范围）：

覆盖 generate_classroom 契约、wait_job 轮询回调、错误码映射矩阵、
重试策略（4xx 不重试 / 5xx 重试后成功或耗尽后抛出）、连接失败映射、
未知新字段透传不崩、config 默认超时值。
"""

import base64
import inspect
import json
import sys
from pathlib import Path

import httpx
import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

pytestmark = pytest.mark.anyio

from app.integrations.openmaic import (
    OpenMaicBadRequest,
    OpenMaicClient,
    OpenMaicConfig,
    OpenMaicError,
    OpenMaicJobNotFound,
    OpenMaicPollTimeout,
    OpenMaicServerError,
    OpenMaicSSRFRejected,
    OpenMaicUnavailable,
    get_openmaic_client,
)


async def test_openmaic_factory_can_return_uncached_clients(monkeypatch):
    import app.integrations.openmaic as openmaic_module

    monkeypatch.setattr(
        openmaic_module.runtime_config_resolver,
        "resolve",
        lambda *_args, **_kwargs: {
            "base_url": "http://sidecar-test:3000",
            "api_key": "",
            "timeout_seconds": 60,
            "_revision_id": "test-revision",
        },
    )
    openmaic_module._singletons.clear()
    supports_uncached = "use_cache" in inspect.signature(get_openmaic_client).parameters
    assert supports_uncached is True
    if not supports_uncached:
        return

    cached = get_openmaic_client(owner_user_id="teacher")
    same_cached = get_openmaic_client(owner_user_id="teacher")
    fresh = get_openmaic_client(owner_user_id="teacher", use_cache=False)
    another_fresh = get_openmaic_client(owner_user_id="teacher", use_cache=False)
    try:
        assert cached is same_cached
        assert fresh is not cached
        assert another_fresh is not fresh
    finally:
        await cached.aclose()
        await fresh.aclose()
        await another_fresh.aclose()
        openmaic_module._singletons.clear()


def _json_response(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


def _error_body(error_code: str, message: str) -> dict:
    return {"success": False, "errorCode": error_code, "error": message}


async def test_synthesize_tts_posts_server_managed_qwen_and_decodes_audio():
    expected = b"ID3-answer-audio"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate/tts"
        assert json.loads(request.content) == {
            "text": "回答。回到课堂。",
            "audioId": "turn-1",
            "ttsProviderId": "qwen-tts",
            "ttsVoice": "Cherry",
            "ttsSpeed": 1.0,
        }
        return httpx.Response(
            200,
            json={
                "success": True,
                "audioId": "turn-1",
                "base64": base64.b64encode(expected).decode("ascii"),
                "format": "mp3",
            },
        )

    client = OpenMaicClient(transport=httpx.MockTransport(handler))
    try:
        audio, format_name = await client.synthesize_tts(
            text="回答。回到课堂。",
            audio_id="turn-1",
            provider_id="qwen-tts",
            voice="Cherry",
        )
    finally:
        await client.aclose()

    assert audio == expected
    assert format_name == "mp3"


@pytest.mark.parametrize(
    ("audio_base64", "format_name"),
    [
        ("%%%", "mp3"),
        ("", "mp3"),
        (base64.b64encode(b"x").decode("ascii"), "flac"),
    ],
)
async def test_synthesize_tts_rejects_invalid_provider_audio(
    audio_base64: str,
    format_name: str,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "audioId": "turn-1",
                    "base64": audio_base64,
                    "format": format_name,
                },
            },
        )

    client = OpenMaicClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(OpenMaicServerError):
            await client.synthesize_tts(
                text="回答",
                audio_id="turn-1",
                provider_id="qwen-tts",
                voice="Cherry",
            )
    finally:
        await client.aclose()


async def test_synthesize_tts_rejects_audio_above_ten_mebibytes():
    oversized = base64.b64encode(b"x" * (10 * 1024 * 1024 + 1)).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "audioId": "turn-1",
                    "base64": oversized,
                    "format": "mp3",
                },
            },
        )

    client = OpenMaicClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(OpenMaicServerError):
            await client.synthesize_tts(
                text="回答",
                audio_id="turn-1",
                provider_id="qwen-tts",
                voice="Cherry",
            )
    finally:
        await client.aclose()


async def test_synthesize_tts_maps_rate_limit_timeout_and_failed_envelope():
    responses = iter(
        [
            httpx.Response(429, json=_error_body("RATE_LIMIT", "slow down")),
            httpx.Response(200, json={"success": False, "error": "provider failed"}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    client = OpenMaicClient(
        OpenMaicConfig(retries=0),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(OpenMaicError) as rate_limited:
            await client.synthesize_tts(
                text="回答",
                audio_id="turn-1",
                provider_id="qwen-tts",
                voice="Cherry",
            )
        assert rate_limited.value.status_code == 429

        with pytest.raises(OpenMaicServerError):
            await client.synthesize_tts(
                text="回答",
                audio_id="turn-1",
                provider_id="qwen-tts",
                voice="Cherry",
            )
    finally:
        await client.aclose()

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    timeout_client = OpenMaicClient(
        OpenMaicConfig(retries=0),
        transport=httpx.MockTransport(timeout_handler),
    )
    try:
        with pytest.raises(OpenMaicUnavailable):
            await timeout_client.synthesize_tts(
                text="回答",
                audio_id="turn-1",
                provider_id="qwen-tts",
                voice="Cherry",
            )
    finally:
        await timeout_client.aclose()


# ── config 默认值（AC-07-1） ─────────────────────────────────────────────


def test_config_defaults_match_spec():
    config = OpenMaicConfig(base_url="http://sidecar-test:3000")
    assert config.connect_timeout == 10.0
    assert config.request_timeout == 60.0
    assert config.parse_timeout == 20 * 60
    assert config.poll_interval == 5.0
    assert config.max_poll_seconds == 40 * 60
    assert config.retries == 2


# ── generate_classroom 契约（AC-07-3/9） ────────────────────────────────


async def test_generate_classroom_maps_research_context_and_returns_envelope():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return _json_response(
            202,
            {
                "jobId": "job-123",
                "status": "queued",
                "step": "initializing",
                "message": "Queued",
                "pollUrl": "http://sidecar-test:3000/api/generate-classroom/job-123",
                "pollIntervalMs": 5000,
                # unknown/future field must not break the client (AC-07-9)
                "futureField": {"anything": True},
            },
        )

    client = OpenMaicClient(
        OpenMaicConfig(base_url="http://sidecar-test:3000"),
        transport=httpx.MockTransport(handler),
    )
    try:
        envelope = await client.generate_classroom(
            requirement="Teach retries",
            research_context="RAG: chapter 3 covers retries.",
        )
    finally:
        await client.aclose()

    assert envelope["jobId"] == "job-123"
    assert envelope["pollUrl"].endswith("/job-123")

    import json as _json

    sent_body = _json.loads(captured["body"])
    assert sent_body["researchContext"] == "RAG: chapter 3 covers retries."
    assert sent_body["requirement"] == "Teach retries"
    assert sent_body["agentMode"] == "default"
    assert sent_body["enableWebSearch"] is False


async def test_generate_classroom_omits_research_context_when_not_provided():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return _json_response(
            202,
            {
                "jobId": "job-456",
                "status": "queued",
                "step": "initializing",
                "message": "Queued",
                "pollUrl": "http://sidecar-test:3000/api/generate-classroom/job-456",
                "pollIntervalMs": 5000,
            },
        )

    client = OpenMaicClient(transport=httpx.MockTransport(handler))
    try:
        await client.generate_classroom(requirement="Teach retries")
    finally:
        await client.aclose()

    import json as _json

    sent_body = _json.loads(captured["body"])
    assert "researchContext" not in sent_body


async def test_generate_classroom_sends_explicit_shared_tts_profile():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _json_response(
            202,
            {
                "jobId": "job-tts",
                "status": "queued",
                "pollUrl": "/api/generate-classroom/job-tts",
            },
        )

    client = OpenMaicClient(transport=httpx.MockTransport(handler))
    try:
        await client.generate_classroom(
            requirement="讲解快速排序",
            enable_tts=True,
            tts_provider_id="qwen-tts",
            tts_voice="Cherry",
            tts_speed=1.0,
        )
    finally:
        await client.aclose()

    assert captured["body"]["ttsProviderId"] == "qwen-tts"
    assert captured["body"]["ttsVoice"] == "Cherry"
    assert captured["body"]["ttsSpeed"] == 1.0


# ── wait_job 轮询回调（AC-07-4） ─────────────────────────────────────────


async def test_wait_job_polls_until_done_and_reports_progress():
    responses = [
        {
            "jobId": "job-1",
            "status": "running",
            "step": "generating_outlines",
            "progress": 30,
            "message": "Generating outlines",
            "pollUrl": "http://sidecar-test:3000/api/generate-classroom/job-1",
            "pollIntervalMs": 1,
            "done": False,
        },
        {
            "jobId": "job-1",
            "status": "running",
            "step": "generating_scenes",
            "progress": 60,
            "message": "Generating scenes",
            "pollUrl": "http://sidecar-test:3000/api/generate-classroom/job-1",
            "pollIntervalMs": 1,
            "done": False,
        },
        {
            "jobId": "job-1",
            "status": "succeeded",
            "step": "completed",
            "progress": 100,
            "message": "Done",
            "pollUrl": "http://sidecar-test:3000/api/generate-classroom/job-1",
            "pollIntervalMs": 1,
            "done": True,
            "result": {"id": "classroom-1", "scenes": []},
        },
    ]
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        return _json_response(200, responses[idx])

    seen = []
    client = OpenMaicClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.wait_job(
            "http://sidecar-test:3000/api/generate-classroom/job-1",
            on_progress=lambda step, progress, message: seen.append((step, progress)),
        )
    finally:
        await client.aclose()

    assert result["done"] is True
    assert result["result"]["id"] == "classroom-1"
    assert seen == [
        ("generating_outlines", 30),
        ("generating_scenes", 60),
        ("completed", 100),
    ]
    assert call_count["n"] == 3  # 轮询在 done 处停止，不多打一次


async def test_wait_job_raises_poll_timeout_when_never_done():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            200,
            {
                "jobId": "job-stuck",
                "status": "running",
                "step": "generating_scenes",
                "progress": 50,
                "message": "still working",
                "pollUrl": "http://sidecar-test:3000/api/generate-classroom/job-stuck",
                "pollIntervalMs": 1,
                "done": False,
            },
        )

    config = OpenMaicConfig(max_poll_seconds=0.01, poll_interval=0.001)
    client = OpenMaicClient(config, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(OpenMaicPollTimeout):
            await client.wait_job("http://sidecar-test:3000/api/generate-classroom/job-stuck")
    finally:
        await client.aclose()


# ── 错误映射矩阵（AC-07-5） ──────────────────────────────────────────────


async def test_error_mapping_400_missing_required_field():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(400, _error_body("MISSING_REQUIRED_FIELD", "Missing required field: requirement"))

    client = OpenMaicClient(
        OpenMaicConfig(retries=0), transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(OpenMaicBadRequest):
            await client.generate_classroom(requirement="")
    finally:
        await client.aclose()


async def test_error_mapping_403_ssrf():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(403, _error_body("INVALID_URL", "URL rejected by SSRF guard"))

    client = OpenMaicClient(
        OpenMaicConfig(retries=0), transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(OpenMaicSSRFRejected):
            await client.generate_classroom(requirement="x")
    finally:
        await client.aclose()


async def test_error_mapping_404_job_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(404, _error_body("INVALID_REQUEST", "Classroom generation job not found"))

    client = OpenMaicClient(
        OpenMaicConfig(retries=0), transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(OpenMaicJobNotFound):
            await client.poll_job("http://sidecar-test:3000/api/generate-classroom/missing")
    finally:
        await client.aclose()


async def test_error_mapping_connection_failure_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = OpenMaicClient(
        OpenMaicConfig(retries=0), transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(OpenMaicUnavailable):
            await client.generate_classroom(requirement="x")
    finally:
        await client.aclose()


# ── 重试策略（AC-07-6） ─────────────────────────────────────────────────


async def test_5xx_retries_then_succeeds():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 3:
            return _json_response(500, _error_body("INTERNAL_ERROR", "transient failure"))
        return _json_response(
            202,
            {
                "jobId": "job-retry",
                "status": "queued",
                "step": "initializing",
                "message": "Queued",
                "pollUrl": "http://sidecar-test:3000/api/generate-classroom/job-retry",
                "pollIntervalMs": 5000,
            },
        )

    client = OpenMaicClient(
        OpenMaicConfig(retries=2), transport=httpx.MockTransport(handler)
    )
    try:
        envelope = await client.generate_classroom(requirement="x")
    finally:
        await client.aclose()

    assert envelope["jobId"] == "job-retry"
    assert call_count["n"] == 3


async def test_5xx_exhausts_retries_and_raises():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return _json_response(500, _error_body("INTERNAL_ERROR", "persistent failure"))

    client = OpenMaicClient(
        OpenMaicConfig(retries=2), transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(OpenMaicServerError):
            await client.generate_classroom(requirement="x")
    finally:
        await client.aclose()

    assert call_count["n"] == 3  # 1 次原始 + 2 次重试


async def test_400_is_not_retried():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return _json_response(400, _error_body("MISSING_REQUIRED_FIELD", "Missing required field: requirement"))

    client = OpenMaicClient(
        OpenMaicConfig(retries=2), transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(OpenMaicBadRequest):
            await client.generate_classroom(requirement="")
    finally:
        await client.aclose()

    assert call_count["n"] == 1


# ── health（连通性快速检查，非本轮硬性 AC，但零成本覆盖） ──────────────


async def test_health_true_on_200_false_on_failure():
    def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "status": "ok"})

    client_ok = OpenMaicClient(transport=httpx.MockTransport(ok_handler))
    try:
        assert await client_ok.health() is True
    finally:
        await client_ok.aclose()

    def down_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client_down = OpenMaicClient(transport=httpx.MockTransport(down_handler))
    try:
        assert await client_down.health() is False
    finally:
        await client_down.aclose()
