import json

import httpx
import pytest

from app.chat.workflows.ppt.html2ppt_client import Html2PptClient


def test_html2ppt_client_builds_and_sends_phase1_requests():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("utf-8") if request.content else ""
        calls.append(
            {
                "method": request.method,
                "path": request.url.path,
                "json": json.loads(body) if body else None,
            }
        )
        if request.method == "POST" and request.url.path == "/ppt/jobs":
            return httpx.Response(200, json={"job_id": "job_001", "status": "queued"})
        if request.method == "GET" and request.url.path == "/ppt/jobs/job_001":
            return httpx.Response(200, json={"job_id": "job_001", "status": "running"})
        if request.method == "GET" and request.url.path == "/ppt/jobs/job_001/results":
            return httpx.Response(200, json={"job_id": "job_001", "results": {"pptx_url": "/ppt/artifacts/job_001/rev_0000/deck.pptx"}})
        return httpx.Response(404)

    client = Html2PptClient(
        base_url="http://testserver",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver"),
    )

    job = client.create_job(
        content_markdown="# Deck\n",
        theme_id="heu_academic_elegant",
        metadata={
            "request_id": "req-1",
            "timestamp": "2026-04-08T10:00:00+08:00",
            "idempotency_key": "idem-1",
            "user_id": "teacher",
        },
    )
    status = client.get_job_status("job_001")
    results = client.get_job_results("job_001")

    assert job == {"job_id": "job_001", "status": "queued"}
    assert status == {"job_id": "job_001", "status": "running"}
    assert results == {
        "job_id": "job_001",
        "results": {"pptx_url": "http://testserver/ppt/artifacts/job_001/rev_0000/deck.pptx"},
    }
    assert calls == [
        {
            "method": "POST",
            "path": "/ppt/jobs",
            "json": {
                "content_markdown": "# Deck\n",
                "theme_id": "heu_academic_elegant",
                "metadata": {
                    "request_id": "req-1",
                    "timestamp": "2026-04-08T10:00:00+08:00",
                    "idempotency_key": "idem-1",
                    "user_id": "teacher",
                },
            },
        },
        {"method": "GET", "path": "/ppt/jobs/job_001", "json": None},
        {"method": "GET", "path": "/ppt/jobs/job_001/results", "json": None},
    ]


def test_html2ppt_client_raises_for_non_success_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    client = Html2PptClient(
        base_url="http://testserver",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver"),
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.get_job_status("job_404")


def test_html2ppt_client_disables_environment_proxy_lookup_by_default(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["kwargs"] = dict(kwargs)

    monkeypatch.setattr(httpx, "Client", FakeClient)

    client = Html2PptClient(base_url="http://127.0.0.1:46080")

    assert captured["kwargs"]["base_url"] == "http://127.0.0.1:46080"
    assert captured["kwargs"]["trust_env"] is False
    assert client.base_url == "http://127.0.0.1:46080"


def test_html2ppt_client_normalizes_relative_result_urls_to_absolute_urls():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/ppt/jobs/job_001/results":
            return httpx.Response(
                200,
                json={
                    "job_id": "job_001",
                    "latest_revision_id": "rev_0000",
                    "results": {
                        "html_full_url": "/ppt/artifacts/job_001/rev_0000/deck.html",
                        "pptx_url": "/ppt/artifacts/job_001/rev_0000/deck.pptx",
                        "manifest_url": "/ppt/artifacts/job_001/rev_0000/manifest.json",
                    },
                },
            )
        return httpx.Response(404)

    client = Html2PptClient(
        base_url="http://127.0.0.1:46080",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:46080"),
    )

    results = client.get_job_results("job_001")

    assert results["results"]["html_full_url"] == "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/deck.html"
    assert results["results"]["pptx_url"] == "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/deck.pptx"
    assert results["results"]["manifest_url"] == "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/manifest.json"


def test_html2ppt_client_builds_revision_requests():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("utf-8") if request.content else ""
        calls.append(
            {
                "method": request.method,
                "path": request.url.path,
                "json": json.loads(body) if body else None,
            }
        )
        if request.method == "POST" and request.url.path == "/ppt/jobs/job_001/revisions":
            return httpx.Response(200, json={"revision_id": "rev_0001", "status": "queued"})
        if request.method == "GET" and request.url.path == "/ppt/jobs/job_001/revisions/rev_0001":
            return httpx.Response(200, json={"revision_id": "rev_0001", "status": "completed"})
        return httpx.Response(404)

    client = Html2PptClient(
        base_url="http://testserver",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver"),
    )

    revision = client.create_revision(
        "job_001",
        mode="single_slide",
        target_slides=[3],
        user_instruction="把第 3 页改成流程图风格",
        metadata={"source_revision_id": "rev_0000"},
    )
    status = client.get_revision_status("job_001", "rev_0001")

    assert revision == {"revision_id": "rev_0001", "status": "queued"}
    assert status == {"revision_id": "rev_0001", "status": "completed"}
    assert calls == [
        {
            "method": "POST",
            "path": "/ppt/jobs/job_001/revisions",
            "json": {
                "mode": "single_slide",
                "target_slides": [3],
                "user_instruction": "把第 3 页改成流程图风格",
                "metadata": {"source_revision_id": "rev_0000"},
            },
        },
        {
            "method": "GET",
            "path": "/ppt/jobs/job_001/revisions/rev_0001",
            "json": None,
        },
    ]
