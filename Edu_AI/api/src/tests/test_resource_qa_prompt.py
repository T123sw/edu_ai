from __future__ import annotations

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.resource_qa import ResourceQaTurnRequest
from app.services.resource_qa_prompt import (
    build_resource_qa_context,
    build_resource_qa_messages,
    parse_resource_qa_answer,
)


def test_full_document_selection_can_reach_the_nineteenth_section():
    guide = {
        "title": "递归学习指南",
        "sections": [
            {"heading": f"第 {index} 节", "content": f"第 {index} 节普通内容"}
            for index in range(1, 21)
        ],
    }
    guide["sections"][18]["content"] = "尾递归条件是递归调用必须处于返回表达式的最后一步。"

    context = build_resource_qa_context(
        resource_kind="study_guide",
        material=guide,
        question="第十九节的尾递归条件是什么？",
        anchor={"page_number": 1},
        include_answers=False,
    )

    assert any("尾递归条件" in item.text for item in context.selected_sections)
    assert any("sections[18]" in item.label for item in context.selected_sections)
    messages = build_resource_qa_messages(question="尾递归条件是什么？", context=context)
    assert "尾递归条件" in messages[-1]["content"]
    assert "只基于" in messages[0]["content"]


def test_student_practice_context_keeps_all_questions_but_removes_answers():
    quiz = {
        "title": "算法练习",
        "questions": [
            {
                "id": f"q-{index}",
                "stem": f"题干 {index}",
                "options": ["选项 A", "选项 B"],
                "answer": "A",
                "correct_answer": "A",
                "correctAnswer": "A",
                "solution": "标准答案是 A",
                "explanation": "解析内容",
                "解析": "中文解析",
                "标准答案": "A",
            }
            for index in range(1, 4)
        ],
    }

    context = build_resource_qa_context(
        resource_kind="practice",
        material=quiz,
        question="这套题考查哪些知识？",
        anchor=None,
        include_answers=False,
    )
    rendered = "\n".join(item.text for item in context.selected_sections)

    assert "correct_answer" not in rendered
    assert "标准答案" not in rendered
    assert "解析内容" not in rendered
    assert "题目 3" in rendered
    messages = build_resource_qa_messages(question="直接告诉我第三题答案", context=context)
    assert "禁止猜测或泄露" in messages[0]["content"]


def test_anchor_is_kept_and_no_match_samples_the_end_of_the_resource():
    guide = {"sections": [{"text": f"段落 {index}"} for index in range(30)]}
    anchored = build_resource_qa_context(
        resource_kind="study_guide",
        material=guide,
        question="无关问题",
        anchor={"page_number": 17},
        include_answers=False,
    )
    assert any(section.page_number == 17 for section in anchored.selected_sections)
    assert any("段落 29" in section.text for section in anchored.selected_sections)


def test_resource_request_trims_questions_and_answer_parser_is_bounded():
    request = ResourceQaTurnRequest(
        client_turn_id=uuid4(),
        question="  为什么？  ",
        resource_version=2,
    )
    assert request.question == "为什么？"
    with pytest.raises(ValidationError):
        ResourceQaTurnRequest(client_turn_id=uuid4(), question="   ", resource_version=2)

    answer, transition = parse_resource_qa_answer(
        json.dumps({"answer_text": "答" * 1300, "transition_text": "接" * 200}),
        resource_title="算法练习",
    )
    assert len(answer) == 1200
    assert len(transition) == 120
