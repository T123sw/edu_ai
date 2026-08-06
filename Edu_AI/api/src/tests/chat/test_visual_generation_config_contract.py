from app.chat.api.schemas_v2 import KnowledgeBaseDirectGraphRequestV2
from app.schemas.course import GenerateClassroomRequest


def test_mind_map_schema_preserves_description_and_depth():
    payload = KnowledgeBaseDirectGraphRequestV2(
        course_id="course-1",
        source_mode="none",
        title="电磁学",
        description="突出概念关系",
        max_depth=4,
        idempotency_key="mind-map-1",
    )

    assert payload.description == "突出概念关系"
    assert payload.max_depth == 4


def test_classroom_schema_preserves_voice_and_teaching_configuration():
    payload = GenerateClassroomRequest(
        topic="波的干涉",
        audience="本科一年级",
        objectives=["解释相干条件"],
        scene_count=8,
        duration_minutes=35,
        teaching_style="inquiry",
        enable_tts=True,
        voice="nova",
        requirement="通过实验问题讲解波的干涉",
    )

    assert payload.objectives == ["解释相干条件"]
    assert payload.duration_minutes == 35
    assert payload.teaching_style == "inquiry"
    assert payload.voice == "nova"
