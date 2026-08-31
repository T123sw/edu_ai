from __future__ import annotations

from app.resource_learning.manifest import build_classroom_learning_manifest


def _classroom_payload() -> dict:
    return {
        "course_id": "course-1",
        "material_id": "classroom-1",
        "version": 3,
        "scenes": [
            {
                "id": "s1",
                "type": "slide",
                "content": {"type": "slide"},
                "actions": [
                    {"id": "focus-1", "type": "spotlight", "targetId": "title"},
                    {"id": "a1", "type": "speech", "text": "普通讲解。"},
                    {"id": "a2", "type": "show", "targetId": "formula"},
                    {"id": "live-1", "type": "discussion", "topic": "自由讨论"},
                ],
            },
            {
                "id": "q1",
                "type": "quiz",
                "content": {
                    "type": "quiz",
                    "questions": [
                        {
                            "id": "question-1",
                            "type": "single",
                            "question": "1+1?",
                            "answer": ["B"],
                            "knowledgePointIds": ["kp-1"],
                        },
                        {
                            "id": "question-optional",
                            "type": "short",
                            "question": "说说你的想法",
                            "required": False,
                            "answer": "开放回答",
                        },
                    ],
                },
            },
            {"id": "d1", "type": "interactive", "content": {"type": "interactive"}},
        ],
    }


def test_build_manifest_classifies_slide_quiz_and_interactive() -> None:
    manifest = build_classroom_learning_manifest(_classroom_payload())

    assert [scene.kind for scene in manifest.scenes] == ["explanation", "exercise", "demo"]
    assert manifest.required_question_ids == ("question-1",)
    assert manifest.mode == "completable"
    assert manifest.course_id == "course-1"
    assert manifest.resource_id == "classroom-1"
    assert manifest.resource_version == 3


def test_manifest_keeps_scoring_private_data_and_required_flags() -> None:
    manifest = build_classroom_learning_manifest(_classroom_payload())

    first, optional = manifest.questions
    assert first.scoring_values == ("B",)
    assert first.knowledge_point_ids == ("kp-1",)
    assert first.required is True
    assert optional.scoring_values == ("开放回答",)
    assert optional.required is False


def test_manifest_duration_matches_classroom_timeline_rules() -> None:
    payload = _classroom_payload()
    slide = payload["scenes"][0]
    slide["actions"] = [
        {"id": "orphan-focus", "type": "laser", "targetId": "x"},
        {"id": "cn", "type": "speech", "text": "这是十个汉字的讲解文本", "speed": 2},
        {"id": "en", "type": "speech", "text": "one two three four five six seven eight nine ten", "speed": 1},
        {"id": "visual", "type": "show", "targetId": "x"},
        {"id": "discussion", "type": "discussion", "topic": "live"},
    ]

    manifest = build_classroom_learning_manifest(payload)
    explanation = manifest.scenes[0]

    # Chinese speech: max(2000, 11 * 150) / 2 = 1000; English: 10 * 240 = 2400.
    # Focus and discussion do not add serial explanation time; ordinary actions add 1000ms.
    assert explanation.expected_duration_ms == 4_400
    assert explanation.required_action_ids == ("orphan-focus", "cn", "en", "visual")


def test_manifest_without_required_questions_is_behavior_only() -> None:
    payload = _classroom_payload()
    payload["scenes"][1]["content"]["questions"][0]["required"] = False

    manifest = build_classroom_learning_manifest(payload)

    assert manifest.required_question_ids == ()
    assert manifest.mode == "behavior_only"


def test_manifest_identity_and_hash_are_deterministic() -> None:
    first = build_classroom_learning_manifest(_classroom_payload())
    second = build_classroom_learning_manifest(_classroom_payload())

    assert first.manifest_id == second.manifest_id
    assert first.content_hash == second.content_hash
