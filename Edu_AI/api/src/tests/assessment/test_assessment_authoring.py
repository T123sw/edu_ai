from __future__ import annotations

import json

import pytest

from app.assessment.extractors import extract_assessment_items
from app.assessment.generator import AssessmentAuthoringError, AssessmentDraftGenerator
from app.assessment.quality import AssessmentQualityService


class JsonLlm:
    def __init__(self, questions: list[dict]):
        self._payload = json.dumps({"questions": questions}, ensure_ascii=False)

    def invoke(self, _prompt):
        return self._payload


def test_existing_quiz_questions_are_normalized_with_stable_source_refs():
    materials = [
        {
            "material_type": "quiz",
            "material_id": "quiz-1",
            "questions": [
                {
                    "id": "q1",
                    "type": "choice",
                    "stem": "Python 的循环关键字是？",
                    "options": ["for", "when", "switch"],
                    "answer": "A",
                    "explanation": "for 用于迭代。",
                },
                {
                    "id": "q2",
                    "type": "blank",
                    "stem": "终止当前循环使用 ____。",
                    "answer": "break",
                },
            ],
        }
    ]

    result = extract_assessment_items(
        materials,
        assessment_version_id="asv-1",
        knowledge_point_ids=["loops"],
    )

    assert len(result.items) == 2
    assert result.items[0].item_type == "single_choice"
    assert result.items[0].scoring_key == {"correct_option_id": "opt-1"}
    assert result.items[1].item_type == "structured_blank"
    assert result.items[1].scoring_key == {"accepted_answers": ["break"]}
    assert result.items[0].source_refs == [
        {"material_type": "quiz", "material_id": "quiz-1", "source_item_id": "q1"}
    ]
    assert {item.created_origin for item in result.items} == {"imported"}


def test_classroom_quiz_scene_is_detected_as_existing_assessment_content():
    materials = [
        {
            "material_type": "classroom",
            "material_id": "classroom-1",
            "scenes": [
                {"id": "scene-1", "type": "slide", "content": {}},
                {
                    "id": "scene-quiz",
                    "type": "quiz",
                    "content": {
                        "questions": [
                            {
                                "id": "cq1",
                                "type": "judge",
                                "stem": "递归必须有终止条件。",
                                "answer": "正确",
                            }
                        ]
                    },
                },
            ],
        }
    ]

    result = extract_assessment_items(
        materials,
        assessment_version_id="asv-1",
        knowledge_point_ids=["recursion"],
    )

    assert len(result.items) == 1
    assert result.items[0].item_type == "judge"
    assert result.items[0].scoring_key == {"correct_value": True}
    assert result.items[0].source_refs[0]["scene_id"] == "scene-quiz"


def test_generator_uses_parseable_material_and_maps_only_requested_coverage_gaps():
    generator = AssessmentDraftGenerator(
        llm=JsonLlm(
            [
                {
                    "id": "g1",
                    "type": "choice",
                    "question": "循环不变量用于什么？",
                    "choices": ["证明循环正确", "定义类", "导入模块", "处理文件"],
                    "correct_answer": "A",
                    "analysis": "循环不变量用于证明循环前后性质保持。",
                },
                {
                    "id": "g2",
                    "type": "short",
                    "question": "说明递归终止条件的作用。",
                    "correct_answer": "避免无限递归。",
                    "analysis": "终止条件让递归在基本情形返回。",
                },
            ]
        )
    )
    materials = [
        {
            "material_type": "report",
            "material_id": "report-1",
            "title": "循环与递归",
            "content": "循环不变量用于证明循环正确；递归必须有基本情形作为终止条件。",
        }
    ]

    items = generator.generate(
        materials=materials,
        assessment_version_id="asv-1",
        task_title="循环与递归学习",
        task_instructions="阅读材料后完成测评",
        coverage_gaps=["loop-invariant", "recursion-base-case"],
        difficulty="medium",
    )

    assert len(items) == 2
    assert [item.knowledge_point_ids for item in items] == [
        ["loop-invariant"],
        ["recursion-base-case"],
    ]
    assert all(item.created_origin == "generated" for item in items)
    assert all(item.source_refs[0]["material_id"] == "report-1" for item in items)
    assert items[1].grading_provider == "rubric_ai_teacher"
    assert items[1].rubric["reference_answer"] == "避免无限递归。"


def test_generator_rejects_tasks_without_parseable_materials():
    generator = AssessmentDraftGenerator(llm=JsonLlm([]))

    with pytest.raises(AssessmentAuthoringError) as error:
        generator.generate(
            materials=[],
            assessment_version_id="asv-1",
            task_title="空任务",
            task_instructions="",
            coverage_gaps=["loops"],
            difficulty="medium",
        )

    assert error.value.code == "ASSESSMENT_SOURCE_REQUIRED"


def test_generator_infers_knowledge_points_from_material_when_optional_context_is_empty():
    generator = AssessmentDraftGenerator(
        llm=JsonLlm(
            [
                {
                    "id": "g1",
                    "type": "short",
                    "question": "Explain how a pivot partitions a list.",
                    "correct_answer": "Values are separated around the pivot.",
                    "analysis": "The pivot defines the two partitions.",
                    "knowledge_points": ["partition", "pivot"],
                }
            ]
        )
    )

    items = generator.generate(
        materials=[
            {
                "material_type": "report",
                "material_id": "report-1",
                "title": "Quick sort",
                "content": "Quick sort partitions values around a pivot and recurses.",
            }
        ],
        assessment_version_id="asv-1",
        task_title="",
        task_instructions="",
        coverage_gaps=[],
        difficulty="medium",
    )

    assert len(items) == 5
    assert items[0].knowledge_point_ids == ["partition", "pivot"]
    assert all(item.source_refs[0]["material_id"] == "report-1" for item in items)


def test_quality_gate_reports_scoring_coverage_duplicate_source_and_leak_issues():
    extracted = extract_assessment_items(
        [
            {
                "material_type": "quiz",
                "material_id": "quiz-1",
                "questions": [
                    {
                        "id": "q1",
                        "type": "choice",
                        "stem": "重复题",
                        "options": ["A", "B"],
                        "answer": "",
                    },
                    {
                        "id": "q2",
                        "type": "choice",
                        "stem": "重复题",
                        "options": ["A", "B"],
                        "answer": "A",
                    },
                ],
            }
        ],
        assessment_version_id="asv-1",
        knowledge_point_ids=["loops"],
    )
    first = extracted.items[0]
    leaked = type(first)(
        **{
            **first.__dict__,
            "prompt": {**first.prompt, "correct_answer": "A"},
            "source_refs": [],
        }
    )

    report = AssessmentQualityService().validate(
        [leaked, extracted.items[1]],
        required_knowledge_point_ids=["loops", "recursion"],
    )

    codes = {issue.code for issue in report.issues}
    assert report.publishable is False
    assert {
        "MISSING_SCORING_KEY",
        "KNOWLEDGE_POINT_UNCOVERED",
        "DUPLICATE_ITEM",
        "SOURCE_MISSING",
        "STUDENT_PROJECTION_LEAK",
    }.issubset(codes)
