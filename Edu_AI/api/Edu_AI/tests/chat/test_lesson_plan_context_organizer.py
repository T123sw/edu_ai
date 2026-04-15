from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.lesson_plan_preparation import (
    LessonPlanContextSummary,
    LessonPlanPreparationResult,
)
from app.chat.slot_definitions import LessonPlanSlots
from app.chat.workflows.lesson_plan.assembler import LessonPlanAssembler
from app.chat.orchestrator.lesson_plan_context_organizer import LessonPlanContextOrganizer


def test_lesson_plan_preparation_defaults_are_stable_and_isolated():
    first = LessonPlanPreparationResult()
    second = LessonPlanPreparationResult()

    assert first.lesson_plan_intent == "unclear"
    assert first.topic is None
    assert first.audience is None
    assert first.objective is None
    assert first.duration is None
    assert first.lesson_type is None
    assert first.assessment_method == ""
    assert first.homework_preference == ""
    assert first.confidence == "low"
    assert first.soft_confirm_message == ""

    assert first.lesson_plan_context_summary == LessonPlanContextSummary()
    assert first.lesson_plan_context_summary.topic_summary == ""
    assert first.lesson_plan_context_summary.learner_summary == ""
    assert first.lesson_plan_context_summary.objective_summary == ""
    assert first.lesson_plan_context_summary.key_points == []
    assert first.lesson_plan_context_summary.hard_points == []
    assert first.lesson_plan_context_summary.constraints == {}
    assert first.lesson_plan_context_summary.source_scope == []
    assert first.constraints == {}
    assert first.knowledge_points == []
    assert first.key_points == []
    assert first.hard_points == []
    assert first.teaching_methods == []
    assert first.class_profile == []
    assert first.resource_constraints == []
    assert first.style_constraints == []
    assert first.missing_critical_fields == []
    assert first.source_scope == []

    first.lesson_plan_context_summary.key_points.append("core idea")
    first.knowledge_points.append("knowledge")
    first.class_profile.append("class signal")
    first.resource_constraints.append("projector")

    assert second.lesson_plan_context_summary.key_points == []
    assert second.knowledge_points == []
    assert second.class_profile == []
    assert second.resource_constraints == []
    assert second.source_scope == []

def test_lesson_plan_slots_expose_expanded_teacher_fields():
    slots = LessonPlanSlots()

    assert slots.duration == ""
    assert slots.lesson_type == ""
    assert slots.knowledge_points == []
    assert slots.key_points == []
    assert slots.hard_points == []
    assert slots.teaching_methods == []
    assert slots.class_profile == []
    assert slots.assessment_method == ""
    assert slots.homework_preference == ""
    assert slots.resource_constraints == []
    assert slots.style_constraints == []

    assert LessonPlanSlots.SlotMeta.core_slots == ["topic", "audience", "objective", "duration", "lesson_type"]
    assert LessonPlanSlots.SlotMeta.secondary_slots == [
        "knowledge_points",
        "key_points",
        "hard_points",
        "teaching_methods",
        "class_profile",
        "assessment_method",
        "homework_preference",
        "resource_constraints",
        "style_constraints",
    ]


def test_lesson_plan_schema_overlap_preserves_list_shaped_fields():
    slots = LessonPlanSlots(
        knowledge_points=["knowledge"],
        key_points=["key"],
        hard_points=["hard"],
        teaching_methods=["discussion"],
        class_profile=["class profile"],
        resource_constraints=["projector"],
        style_constraints=["clear language"],
        assessment_method="exit ticket",
        homework_preference="worksheet",
    )
    result = LessonPlanPreparationResult(
        constraints={"audience": "grade 8"},
        knowledge_points=["knowledge"],
        key_points=["key"],
        hard_points=["hard"],
        teaching_methods=["discussion"],
        class_profile=["class profile"],
        resource_constraints=["projector"],
        style_constraints=["clear language"],
        assessment_method="exit ticket",
        homework_preference="worksheet",
    )

    assert slots.knowledge_points == result.knowledge_points == ["knowledge"]
    assert slots.key_points == result.key_points == ["key"]
    assert slots.hard_points == result.hard_points == ["hard"]
    assert slots.class_profile == result.class_profile == ["class profile"]
    assert slots.teaching_methods == result.teaching_methods == ["discussion"]
    assert slots.resource_constraints == result.resource_constraints == ["projector"]
    assert slots.style_constraints == result.style_constraints == ["clear language"]
    assert result.assessment_method == "exit ticket"
    assert result.homework_preference == "worksheet"


def test_lesson_plan_models_round_trip_through_dump_preserves_overlap_fields():
    original = LessonPlanPreparationResult(
        topic="Fractions",
        audience="Grade 8",
        objective="Explain equivalent fractions",
        duration="45 minutes",
        lesson_type="new lesson",
        assessment_method="exit ticket",
        homework_preference="worksheet",
        constraints={"audience": "Grade 8", "pace": "moderate"},
        knowledge_points=["equivalent fractions"],
        key_points=["represent fractions visually"],
        hard_points=["common denominators"],
        teaching_methods=["discussion", "practice"],
        class_profile=["needs visuals"],
        resource_constraints=["projector"],
        style_constraints=["clear language"],
    )

    payload = original.model_dump()
    restored = LessonPlanPreparationResult.model_validate(payload)

    assert restored.model_dump() == payload
    assert restored.assessment_method == "exit ticket"
    assert restored.homework_preference == "worksheet"
    assert restored.constraints == {"audience": "Grade 8", "pace": "moderate"}
    assert restored.knowledge_points == ["equivalent fractions"]
    assert restored.key_points == ["represent fractions visually"]
    assert restored.hard_points == ["common denominators"]
    assert restored.teaching_methods == ["discussion", "practice"]
    assert restored.class_profile == ["needs visuals"]
    assert restored.resource_constraints == ["projector"]
    assert restored.style_constraints == ["clear language"]

    slot_payload = LessonPlanSlots.model_validate(
        {
            "topic": original.topic,
            "audience": original.audience,
            "objective": original.objective,
            "duration": original.duration,
            "lesson_type": original.lesson_type,
            "knowledge_points": original.knowledge_points,
            "key_points": original.key_points,
            "hard_points": original.hard_points,
            "teaching_methods": original.teaching_methods,
            "class_profile": original.class_profile,
            "assessment_method": original.assessment_method,
            "homework_preference": original.homework_preference,
            "resource_constraints": original.resource_constraints,
            "style_constraints": original.style_constraints,
        }
    )

    assert slot_payload.knowledge_points == original.knowledge_points
    assert slot_payload.key_points == original.key_points
    assert slot_payload.hard_points == original.hard_points
    assert slot_payload.teaching_methods == original.teaching_methods
    assert slot_payload.class_profile == original.class_profile
    assert slot_payload.assessment_method == original.assessment_method
    assert slot_payload.homework_preference == original.homework_preference
    assert slot_payload.resource_constraints == original.resource_constraints
    assert slot_payload.style_constraints == original.style_constraints


def test_lesson_plan_assembler_gathers_generation_context_and_slot_hints():
    context = GenerationContext(
        conversation_id="conv-lesson-1",
        resource_type="lesson_plan",
        summary_text="Fractions lesson planning context",
        current_topics=["Fractions"],
        user_goals=["Create a lesson plan"],
        confirmed_facts=["Students can compare whole numbers"],
        constraints={
            "audience": "Grade 5",
            "duration": "45 minutes",
            "lesson_type": "new lesson",
            "objective": "Compare fractions",
        },
        teaching_issues=["Students confuse common denominators"],
        student_signals=["Needs visuals"],
        evidence_points=[{"type": "note", "content": "exit ticket showed gaps"}],
        recent_relevant_messages=[{"role": "user", "content": "Help me plan Fractions"}],
        source_scope={"from_summary": True, "from_recent_messages": True},
    )

    assembled = LessonPlanAssembler().from_generation_context(context)

    assert assembled["summary"] == "Fractions lesson planning context"
    assert assembled["current_topics"] == ["Fractions"]
    assert assembled["user_goals"] == ["Create a lesson plan"]
    assert assembled["confirmed_facts"] == ["Students can compare whole numbers"]
    assert assembled["constraints"] == {
        "audience": "Grade 5",
        "duration": "45 minutes",
        "lesson_type": "new lesson",
        "objective": "Compare fractions",
    }
    assert assembled["teaching_issues"] == ["Students confuse common denominators"]
    assert assembled["student_signals"] == ["Needs visuals"]
    assert assembled["evidence_points"] == [{"type": "note", "content": "exit ticket showed gaps"}]
    assert assembled["recent_messages"] == [{"role": "user", "content": "Help me plan Fractions"}]
    assert assembled["slot_hints"]["topic"] == "Fractions"
    assert assembled["slot_hints"]["audience"] == "Grade 5"
    assert assembled["slot_hints"]["duration"] == "45 minutes"
    assert assembled["slot_hints"]["objective"] == "Compare fractions"
    assert assembled["slot_hints"]["lesson_type"] == "new lesson"


def test_lesson_plan_context_organizer_derives_preparation_fields_from_generation_context():
    context = GenerationContext(
        conversation_id="conv-lesson-2",
        resource_type="lesson_plan",
        summary_text="Fractions lesson planning context",
        current_topics=["Fractions"],
        user_goals=["Create a lesson plan"],
        confirmed_facts=["Students can compare whole numbers", "Students know halves and quarters"],
        constraints={
            "audience": "Grade 5",
            "duration": "45 minutes",
            "lesson_type": "new lesson",
        },
        teaching_issues=["Students confuse common denominators"],
        student_signals=["Needs visuals"],
        evidence_points=[{"type": "note", "content": "exit ticket showed gaps"}],
        recent_relevant_messages=[{"role": "user", "content": "Help me plan Fractions"}],
        source_scope={"from_summary": True, "from_recent_messages": True},
    )

    result = LessonPlanContextOrganizer().organize(
        context=context,
        request_question="Help me plan a Fractions lesson",
    )

    assert result.lesson_plan_intent == "generate_lesson_plan"
    assert result.topic == "Fractions"
    assert result.audience == "Grade 5"
    assert result.duration == "45 minutes"
    assert result.lesson_type == "new lesson"
    assert result.knowledge_points == ["Students can compare whole numbers", "Students know halves and quarters"]
    assert result.key_points[:2] == ["Students confuse common denominators", "Needs visuals"]
    assert result.hard_points == ["Students confuse common denominators"]
    assert result.class_profile[:2] == ["Grade 5", "Needs visuals"]
    assert result.lesson_plan_context_summary.source_scope == ["conversation_summary", "recent_messages"]
    assert result.source_scope == ["conversation_summary", "recent_messages"]
    assert "Fractions" in result.soft_confirm_message


def test_lesson_plan_context_organizer_prefers_explicit_topic_label_over_full_instruction_question():
    context = GenerationContext(
        conversation_id="conv-lesson-3",
        resource_type="lesson_plan",
        summary_text="",
        current_topics=[],
        user_goals=[],
        constraints={
            "audience": "本科高年级",
            "duration": "45分钟",
            "lesson_type": "新授课",
        },
        source_scope={"from_docs": True},
    )

    result = LessonPlanContextOrganizer().organize(
        context=context,
        request_question=(
            "请基于已选文档《随机过程-概率论基础.pdf》和《随机过程-随机过程的基本概念.pdf》，"
            "组织一节单课时教案。首先生成教案大纲，再生成详细正文。"
            "课题：随机过程的基本概念。课时长度：45分钟。课型：新授课。"
            "仅以我当前勾选的文档为依据，不承接历史对话上下文。"
        ),
    )

    assert result.topic == "随机过程的基本概念"
    assert "请基于已选文档" not in str(result.topic)
