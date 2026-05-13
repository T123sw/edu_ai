from types import SimpleNamespace

from app.chat.workflows.ppt.edit_runtime import PptEditRuntime


class StubHtml2PptClient:
    def __init__(self):
        self.calls = []

    def create_revision(self, job_id, *, mode, target_slides, user_instruction, metadata=None):
        self.calls.append(
            {
                "op": "create_revision",
                "job_id": job_id,
                "mode": mode,
                "target_slides": list(target_slides or []),
                "user_instruction": user_instruction,
                "metadata": dict(metadata or {}),
            }
        )
        return {"revision_id": "rev_0001", "status": "queued"}

    def get_revision_status(self, job_id, revision_id):
        self.calls.append({"op": "get_revision_status", "job_id": job_id, "revision_id": revision_id})
        return {"revision_id": revision_id, "status": "completed", "phase": "completed"}

    def get_job_results(self, job_id):
        self.calls.append({"op": "get_job_results", "job_id": job_id})
        return {
            "job_id": job_id,
            "latest_revision_id": "rev_0001",
            "slide_count": 16,
            "results": {
                "html_full_url": "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0001/deck.html",
                "pptx_url": "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0001/deck.pptx",
                "manifest_url": "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0001/manifest.json",
            },
        }


class PendingRevisionHtml2PptClient:
    def __init__(self):
        self.calls = 0

    def get_revision_status(self, job_id, revision_id):
        self.calls += 1
        return {"revision_id": revision_id, "status": "running", "phase": "queued"}


def _source_deck():
    return {
        "artifact_id": "conv-ppt:deck:job_001",
        "artifact_type": "ppt_deck",
        "title": "TCP 三次握手课件.pptx",
        "content": {
            "job_id": "job_001",
            "revision_id": "rev_0000",
            "slide_count": 6,
            "theme_id": "heu_academic_elegant",
        },
        "generation_state": {
            "status": "completed",
            "phase": "completed",
        },
    }


def _outline_artifact():
    return {
        "artifact_id": "conv-ppt:outline",
        "artifact_type": "ppt_outline",
        "title": "TCP 三次握手课件-大纲",
        "content": {
            "deck_title": "TCP 三次握手课件",
            "slides": [
                {"slide_index": 1, "title": "封面"},
                {"slide_index": 2, "title": "背景"},
                {"slide_index": 3, "title": "过程"},
            ],
        },
    }


def test_ppt_edit_runtime_requests_slide_target_when_missing():
    runtime = PptEditRuntime(html2ppt_client=StubHtml2PptClient(), poll_interval_seconds=0)

    result = runtime.run(
        question="帮我把这个 PPT 调整得更像流程图",
        artifact_reference={"artifact_id": "conv-ppt:deck:job_001", "artifact_type": "ppt_deck"},
        source_artifact=_source_deck(),
        outline_artifact=_outline_artifact(),
    )

    assert result["action"]["name"] == "ppt.edit"
    assert result["workflow"]["status"] == "awaiting_input"
    assert "第 3 页" in result["message"]["content"]


def test_ppt_edit_runtime_calls_revision_and_returns_running_deck():
    client = StubHtml2PptClient()
    runtime = PptEditRuntime(html2ppt_client=client, poll_interval_seconds=0)

    result = runtime.run(
        question="把第 3 页改成流程图风格",
        artifact_reference={"artifact_id": "conv-ppt:deck:job_001", "artifact_type": "ppt_deck"},
        source_artifact=_source_deck(),
        outline_artifact=_outline_artifact(),
    )

    artifact_types = [artifact["artifact_type"] for artifact in result["artifacts"]]
    deck_artifact = result["artifacts"][-1]

    assert result["action"]["name"] == "ppt.edit"
    assert result["workflow"]["status"] == "running"
    assert result["workflow"]["phase"] == "polling_revision"
    assert artifact_types == ["ppt_outline", "ppt_deck"]
    assert deck_artifact["artifact_id"] == "conv-ppt:deck:job_001"
    assert deck_artifact["content"]["revision_id"] == "rev_0001"
    assert deck_artifact["content"]["slide_count"] == 16
    assert deck_artifact["generation_state"]["status"] == "running"
    assert deck_artifact["generation_state"]["pending_revision_id"] == "rev_0001"
    assert deck_artifact["generation_state"]["generation_mode"] == "revise_ppt"
    assert client.calls == [
        {
            "op": "get_job_results",
            "job_id": "job_001",
        },
        {
            "op": "create_revision",
            "job_id": "job_001",
            "mode": "single_slide",
            "target_slides": [3],
            "user_instruction": "把第 3 页改成流程图风格",
            "metadata": {
                "source_revision_id": "rev_0000",
                "source_artifact_id": "conv-ppt:deck:job_001",
            },
        },
    ]


def test_ppt_edit_runtime_supports_chinese_slide_numbers():
    client = StubHtml2PptClient()
    runtime = PptEditRuntime(html2ppt_client=client, poll_interval_seconds=0)

    result = runtime.run(
        question="第五页的流程太多，超出了边界，保留五个流程就行",
        artifact_reference={"artifact_id": "conv-ppt:deck:job_001", "artifact_type": "ppt_deck"},
        source_artifact=_source_deck(),
        outline_artifact=_outline_artifact(),
    )

    assert result["workflow"]["status"] == "running"
    assert client.calls[-1]["target_slides"] == [5]


def test_ppt_edit_runtime_refreshes_stale_slide_count_before_range_validation():
    client = StubHtml2PptClient()
    runtime = PptEditRuntime(html2ppt_client=client, poll_interval_seconds=0)

    result = runtime.run(
        question="把第 9 页的流程精简为 5 步",
        artifact_reference={"artifact_id": "conv-ppt:deck:job_001", "artifact_type": "ppt_deck"},
        source_artifact=_source_deck(),
        outline_artifact=_outline_artifact(),
    )

    assert result["workflow"]["status"] == "running"
    assert [call["op"] for call in client.calls] == [
        "get_job_results",
        "create_revision",
    ]
    assert client.calls[1]["target_slides"] == [9]
    assert result["artifacts"][-1]["content"]["slide_count"] == 16


def test_ppt_edit_runtime_resume_running_revision_returns_new_deck():
    client = StubHtml2PptClient()
    runtime = PptEditRuntime(html2ppt_client=client, poll_interval_seconds=0)

    running = runtime.run(
        question="把第 3 页改成流程图风格",
        artifact_reference={"artifact_id": "conv-ppt:deck:job_001", "artifact_type": "ppt_deck"},
        source_artifact=_source_deck(),
        outline_artifact=_outline_artifact(),
    )
    snapshot = SimpleNamespace(
        workflow_state=SimpleNamespace(
            workflow_type="ppt",
            status="running",
            stage="polling_revision",
            artifacts=running["artifacts"],
        )
    )
    request = SimpleNamespace(
        question="",
        conversation_id="conv-ppt",
        course_id="course-1",
        artifact_reference=SimpleNamespace(
            artifact_id="conv-ppt:deck:job_001",
            artifact_type="ppt_deck",
            title="TCP 三次握手课件.pptx",
        ),
    )

    result = runtime.resume_from_snapshot(
        request=request,
        snapshot=snapshot,
        course_storage_manager=None,
    )

    assert result is not None
    assert result["workflow"]["status"] == "completed"
    assert result["artifacts"][-1]["artifact_id"] == "conv-ppt:deck:job_001:rev_0001"
    assert result["artifacts"][-1]["content"]["revision_id"] == "rev_0001"
    assert result["artifacts"][-1]["content"]["slide_count"] == 16
    assert [call["op"] for call in client.calls] == [
        "get_job_results",
        "create_revision",
        "get_revision_status",
        "get_job_results",
    ]


def test_ppt_edit_runtime_waits_twenty_minutes_before_revision_timeout_by_default():
    client = PendingRevisionHtml2PptClient()
    runtime = PptEditRuntime(html2ppt_client=client, poll_interval_seconds=0)

    result = runtime._wait_for_revision_terminal_state(job_id="job_001", revision_id="rev_0001")

    assert client.calls == 1200
    assert result["status"] == "failed"
    assert result["message"] == "PPT revision timed out before completion."


def test_ppt_edit_runtime_run_from_request_loads_course_material():
    runtime = PptEditRuntime(html2ppt_client=StubHtml2PptClient(), poll_interval_seconds=0)
    course_storage = SimpleNamespace(
        get_generated_material=lambda course_id, material_type, material_id: {
            "material_id": material_id,
            "title": "TCP 三次握手课件.pptx",
            "content": {
                "job_id": "job_001",
                "revision_id": "rev_0000",
                "slide_count": 6,
            },
            "outline": {
                "deck_title": "TCP 三次握手课件",
                "slides": [{"slide_index": 3, "title": "过程"}],
            },
            "generation_state": {"status": "completed", "phase": "completed"},
        }
    )
    request = SimpleNamespace(
        question="把第 3 页改成流程图风格",
        course_id="course-1",
        artifact_reference=SimpleNamespace(
            artifact_id="ppt-deck-1",
            artifact_type="ppt_deck",
            title="TCP 三次握手课件.pptx",
        ),
    )

    result = runtime.run_from_request(
        request=request,
        snapshot=None,
        course_storage_manager=course_storage,
    )

    assert result["workflow"]["status"] == "running"
    assert result["artifacts"][-1]["artifact_type"] == "ppt_deck"
