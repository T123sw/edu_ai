from app.chat.api.schemas_v2 import (
    KnowledgeBaseDirectBlogRequestV2,
    KnowledgeBaseDirectLessonPlanRequestV2,
)


def test_blog_schema_preserves_every_visible_configuration_field():
    payload = KnowledgeBaseDirectBlogRequestV2(
        course_id="course-1",
        source_mode="none",
        topic="量子隧穿",
        audience="本科一年级",
        tone="popular",
        length="long",
        structure="概念—例子—总结",
        special_requirements="加入生活类比",
        idempotency_key="blog-config-1",
    )

    assert payload.model_dump()["special_requirements"] == "加入生活类比"
    assert payload.model_dump()["length"] == "long"


def test_lesson_plan_schema_preserves_process_and_outline_intent():
    payload = KnowledgeBaseDirectLessonPlanRequestV2(
        course_id="course-1",
        source_mode="none",
        topic="牛顿第二定律",
        teaching_process="导入—探究—应用",
        outline_preview=True,
    )

    assert payload.teaching_process == "导入—探究—应用"
    assert payload.outline_preview is True
