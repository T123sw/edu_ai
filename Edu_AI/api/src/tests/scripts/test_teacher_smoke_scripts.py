from __future__ import annotations

import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(SRC_ROOT / "scripts"))

from smoke_teacher_agent_tools import build_cases, validate_reply
from smoke_teacher_generation import build_resource_requests
from teacher_smoke_common import poll_job


def test_agent_cases_cover_none_rag_web_and_combined_modes():
    cases = build_cases(
        course_id="course-1",
        selected_doc_id="doc-1",
        include_web=True,
    )

    assert [case.name for case in cases] == [
        "plain",
        "rag-selected",
        "rag-course-auto",
        "web",
        "rag-web",
    ]
    assert cases[1].payload["source_mode"] == "selected_documents"
    assert cases[1].payload["selected_doc_ids"] == ["doc-1"]
    assert cases[3].payload["allow_web"] is True
    assert cases[4].expected_tools == {"rag_search", "web_search"}


def test_agent_cases_skip_selected_case_without_document():
    cases = build_cases(
        course_id="course-1",
        selected_doc_id=None,
        include_web=False,
    )

    assert [case.name for case in cases] == ["plain", "rag-course-auto"]


def test_validate_reply_checks_source_mode_and_executed_tools():
    response = {
        "message": {"content": "answer"},
        "trace": {
            "source_mode": "selected_documents",
            "agent_steps": [
                {"tool": "rag_search", "ok": True},
                {"tool": "web_search", "ok": True},
            ],
        },
    }

    validate_reply(
        response,
        expected_source_mode="selected_documents",
        expected_tools={"rag_search", "web_search"},
    )


def test_generation_matrix_covers_all_non_ppt_teacher_resources():
    requests = build_resource_requests(
        course_id="course-1",
        topic="链表",
        source_mode="none",
        selected_doc_ids=[],
    )

    assert set(requests) == {
        "report",
        "lesson_plan",
        "quiz",
        "game",
        "flashcard",
        "graph",
        "blog",
        "classroom",
    }
    assert all("ppt" not in item.path for item in requests.values())
    assert all(item.payload["source_mode"] == "none" for item in requests.values())


def test_generation_matrix_propagates_selected_documents():
    requests = build_resource_requests(
        course_id="course-1",
        topic="链表",
        source_mode="selected_documents",
        selected_doc_ids=["doc-1"],
    )

    assert all(
        item.payload["selected_doc_ids"] == ["doc-1"]
        for item in requests.values()
    )


def test_poll_job_returns_terminal_success():
    responses = iter(
        [
            {"status": "queued", "result_ref": None},
            {"status": "running", "result_ref": None},
            {
                "status": "succeeded",
                "result_ref": {"material_id": "material-1"},
            },
        ]
    )

    result = poll_job(
        "job-1",
        request_json=lambda *_args, **_kwargs: next(responses),
        timeout_seconds=1,
        interval_seconds=0,
    )

    assert result["status"] == "succeeded"
    assert result["result_ref"]["material_id"] == "material-1"
