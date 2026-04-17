from types import SimpleNamespace

from app.chat.workflows.report.edit_runtime import ReportEditRuntime


REPORT_MD = """# \u674e\u767d\u6027\u683c\u5206\u6790

## \u6458\u8981
\u539f\u6458\u8981\u3002

## \u7b2c\u4e8c\u90e8\u5206
\u539f\u7b2c\u4e8c\u90e8\u5206\u3002

## \u7ed3\u8bba
\u539f\u7ed3\u8bba\u3002
"""


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return FakeResponse(self.content)


def test_report_edit_runtime_rewrites_summary_and_returns_new_report_artifact():
    runtime = ReportEditRuntime(llm=FakeLLM("\u538b\u7f29\u540e\u7684\u6458\u8981\u3002"))
    result = runtime.run(
        question="\u628a\u6458\u8981\u538b\u7f29\u5230150\u5b57\u4ee5\u5185",
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        source_artifact={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
            "content": REPORT_MD,
        },
    )

    report_artifact = next(artifact for artifact in result["artifacts"] if artifact["artifact_type"] == "report")
    assert report_artifact["artifact_id"] != "report-1"
    assert report_artifact["version"]["parent_artifact_id"] == "report-1"
    assert report_artifact["generation_state"]["generation_mode"] == "revise_report"
    assert "\u538b\u7f29\u540e\u7684\u6458\u8981\u3002" in report_artifact["content"]
    assert result["message"]["content"] == "\u5df2\u751f\u6210\uff0c\u8bf7\u5728\u53f3\u4fa7\u67e5\u770b\u3002"


def test_report_edit_runtime_regenerates_report_from_outline():
    runtime = ReportEditRuntime(llm=FakeLLM("# \u65b0\u62a5\u544a\u6807\u9898\n\n## \u6458\u8981\n\u65b0\u6458\u8981\u3002\n"))
    outline = [
        {"chapter_id": 1, "chapter_title": "\u95ee\u9898\u754c\u5b9a", "sections": [{"section_id": "1.1", "title": "\u8bfe\u5802\u7eaa\u5f8b\u73b0\u72b6"}]},
    ]
    result = runtime.run(
        question="\u57fa\u4e8e\u8fd9\u4e2a\u5927\u7eb2\u91cd\u65b0\u751f\u6210\u4e00\u7248\u6b63\u5f0f\u62a5\u544a",
        artifact_reference={"artifact_id": "outline-1", "artifact_type": "report_outline", "version_id": "v1"},
        source_artifact={
            "artifact_id": "outline-1",
            "artifact_type": "report_outline",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790-\u5927\u7eb2.md",
            "content": outline,
        },
    )

    report_artifact = next(artifact for artifact in result["artifacts"] if artifact["artifact_type"] == "report")
    assert report_artifact["generation_state"]["generation_mode"] == "regenerate_from_outline"
    assert report_artifact["generation_state"]["source_outline_artifact_id"] == "outline-1"
    assert "# \u65b0\u62a5\u544a\u6807\u9898" in report_artifact["content"]


def test_report_edit_runtime_loads_source_artifact_from_course_storage():
    runtime = ReportEditRuntime(llm=FakeLLM("\u91cd\u5199\u540e\u7684\u7ed3\u8bba\u3002"))
    course_storage = SimpleNamespace(
        get_generated_material=lambda course_id, material_type, material_id: {
            "material_id": material_id,
            "material_type": material_type,
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
            "report": REPORT_MD,
        }
    )

    result = runtime.run_from_request(
        request=SimpleNamespace(
            question="\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba",
            course_id="course-1",
            artifact_reference=SimpleNamespace(
                artifact_id="report-1",
                artifact_type="report",
                version_id="v1",
                title="\u674e\u767d\u6027\u683c\u5206\u6790.md",
            ),
        ),
        snapshot=None,
        course_storage_manager=course_storage,
    )

    assert result["action"]["name"] == "report.edit"
    assert any(artifact["artifact_type"] == "report" for artifact in result["artifacts"])


def test_report_edit_runtime_returns_disambiguation_prompt_instead_of_blind_edit():
    runtime = ReportEditRuntime(llm=FakeLLM("\u4e0d\u5e94\u88ab\u8c03\u7528"))
    result = runtime.run(
        question="\u4fee\u6539\u8fd9\u4e00\u90e8\u5206\uff0c\u66f4\u5f3a\u8c03\u8bfe\u5802\u4e92\u52a8",
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        source_artifact={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
            "content": REPORT_MD,
        },
    )

    assert result["artifacts"] == []
    assert result["workflow"]["status"] == "awaiting_input"
    assert "\u8bf7\u660e\u786e\u8981\u4fee\u6539\u7684\u7ed3\u6784\u8282\u70b9" in result["message"]["content"]


def test_report_edit_runtime_returns_graceful_fallback_for_artifact_question():
    runtime = ReportEditRuntime(llm=FakeLLM("\u4e0d\u5e94\u88ab\u8c03\u7528"))
    result = runtime.run(
        question="\u8fd9\u4efd\u62a5\u544a\u7684\u6838\u5fc3\u89c2\u70b9\u662f\u4ec0\u4e48\uff1f",
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        source_artifact={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
            "content": REPORT_MD,
        },
    )

    assert result["artifacts"] == []
    assert result["workflow"]["status"] == "awaiting_input"
    assert "\u5f53\u524d\u5df2\u5f15\u7528\u7684\u662f\u62a5\u544a\u6b63\u6587" in result["message"]["content"]


def test_report_edit_runtime_uses_matched_snippet_instead_of_first_node():
    runtime = ReportEditRuntime(llm=FakeLLM("\u6539\u5199\u540e\u7684\u7b2c\u4e8c\u90e8\u5206\u3002"))
    result = runtime.run(
        question="\u628a\u201c\u539f\u7b2c\u4e8c\u90e8\u5206\u201d\u8fd9\u53e5\u6539\u5f97\u66f4\u6b63\u5f0f",
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        source_artifact={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
            "content": REPORT_MD,
        },
    )

    report_artifact = next(artifact for artifact in result["artifacts"] if artifact["artifact_type"] == "report")
    assert "\u6539\u5199\u540e\u7684\u7b2c\u4e8c\u90e8\u5206\u3002" in report_artifact["content"]
    assert "\u539f\u6458\u8981\u3002" in report_artifact["content"]
