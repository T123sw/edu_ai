from types import SimpleNamespace

import pytest

from app.chat.workflows.report.edit_runtime import ReportEditRuntime
from core.course_storage import CourseStorageManager


REPORT_MD = """# 李白性格分析

## 摘要
原摘要。

## 第二部分
原第二部分。

## 结论
原结论。
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
    runtime = ReportEditRuntime(llm=FakeLLM("压缩后的摘要。"))
    result = runtime.run(
        question="把摘要压缩到150字以内",
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        source_artifact={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "李白性格分析.md",
            "content": REPORT_MD,
        },
    )

    report_artifact = next(artifact for artifact in result["artifacts"] if artifact["artifact_type"] == "report")
    assert report_artifact["artifact_id"] != "report-1"
    assert report_artifact["version"]["parent_artifact_id"] == "report-1"
    assert report_artifact["generation_state"]["generation_mode"] == "revise_report"
    assert "压缩后的摘要。" in report_artifact["content"]
    assert result["message"]["content"] == "已生成，请在右侧查看。"


def test_report_edit_runtime_regenerates_report_from_outline():
    runtime = ReportEditRuntime(llm=FakeLLM("# 新报告标题\n\n## 摘要\n新摘要。\n"))
    outline = [
        {"chapter_id": 1, "chapter_title": "问题界定", "sections": [{"section_id": "1.1", "title": "课堂纪律现状"}]},
    ]
    result = runtime.run(
        question="基于这个大纲重新生成一版正式报告",
        artifact_reference={"artifact_id": "outline-1", "artifact_type": "report_outline", "version_id": "v1"},
        source_artifact={
            "artifact_id": "outline-1",
            "artifact_type": "report_outline",
            "title": "李白性格分析-大纲.md",
            "content": outline,
        },
    )

    report_artifact = next(artifact for artifact in result["artifacts"] if artifact["artifact_type"] == "report")
    assert report_artifact["generation_state"]["generation_mode"] == "regenerate_from_outline"
    assert report_artifact["generation_state"]["source_outline_artifact_id"] == "outline-1"
    assert "# 新报告标题" in report_artifact["content"]


def test_report_edit_runtime_loads_source_artifact_from_course_storage():
    runtime = ReportEditRuntime(llm=FakeLLM("重写后的结论。"))
    course_storage = SimpleNamespace(
        get_generated_material=lambda course_id, material_type, material_id, *, owner_user_id: {
            "material_id": material_id,
            "material_type": material_type,
            "title": "李白性格分析.md",
            "report": REPORT_MD,
        }
    )

    result = runtime.run_from_request(
        request=SimpleNamespace(
            question="保留结构，重写结论",
            course_id="course-1",
            owner="teacher-a",
            artifact_reference=SimpleNamespace(
                artifact_id="report-1",
                artifact_type="report",
                version_id="v1",
                title="李白性格分析.md",
            ),
        ),
        snapshot=None,
        course_storage_manager=course_storage,
    )

    assert result["action"]["name"] == "report.edit"
    assert any(artifact["artifact_type"] == "report" for artifact in result["artifacts"])


def test_report_edit_runtime_reads_private_source_with_authenticated_owner(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "李白性格分析.md", "report": REPORT_MD},
        owner_user_id="teacher-a",
    )
    runtime = ReportEditRuntime(llm=FakeLLM("重写后的结论。"))
    reference = SimpleNamespace(
        artifact_id="report-1",
        artifact_type="report",
        version_id="v1",
        title="李白性格分析.md",
    )

    result = runtime.run_from_request(
        request=SimpleNamespace(
            question="保留结构，重写结论",
            course_id="course-1",
            owner="teacher-a",
            artifact_reference=reference,
        ),
        snapshot=None,
        course_storage_manager=manager,
    )

    assert result["action"]["name"] == "report.edit"

    with pytest.raises(ValueError, match="referenced artifact not found"):
        runtime.run_from_request(
            request=SimpleNamespace(
                question="保留结构，重写结论",
                course_id="course-1",
                owner="teacher-b",
                artifact_reference=reference,
            ),
            snapshot=None,
            course_storage_manager=manager,
        )


def test_report_edit_runtime_returns_disambiguation_prompt_instead_of_blind_edit():
    runtime = ReportEditRuntime(llm=FakeLLM("不应被调用"))
    result = runtime.run(
        question="修改这一部分，更强调课堂互动",
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        source_artifact={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "李白性格分析.md",
            "content": REPORT_MD,
        },
    )

    assert result["artifacts"] == []
    assert result["workflow"]["status"] == "awaiting_input"
    assert "请明确要修改的结构节点" in result["message"]["content"]


def test_report_edit_runtime_returns_graceful_fallback_for_artifact_question():
    runtime = ReportEditRuntime(llm=FakeLLM("不应被调用"))
    result = runtime.run(
        question="这份报告的核心观点是什么？",
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        source_artifact={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "李白性格分析.md",
            "content": REPORT_MD,
        },
    )

    assert result["artifacts"] == []
    assert result["workflow"]["status"] == "awaiting_input"
    assert "当前已引用的是报告正文" in result["message"]["content"]
