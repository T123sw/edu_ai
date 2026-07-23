"""SPEC-02 §6 不变量校验单测（对应 ACC-04 的 AC-04-5）。"""

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.classroom_validation import validate_stage


def _valid_stage_and_scenes():
    stage = {"id": "stage-1", "name": "Retry Basics"}
    scenes = [
        {
            "id": "scene-1",
            "type": "slide",
            "content": {
                "type": "slide",
                "canvas": {
                    "id": "slide-1",
                    "viewportRatio": 0.5625,
                    "elements": [
                        {"id": "el-1", "type": "text"},
                        {"id": "el-2", "type": "video"},
                    ],
                },
            },
            "actions": [
                {"id": "act-1", "type": "speech", "text": "hello"},
                {"id": "act-2", "type": "spotlight", "elementId": "el-1"},
                {"id": "act-3", "type": "play_video", "elementId": "el-2"},
            ],
        }
    ]
    return stage, scenes


def test_valid_stage_has_no_violations():
    stage, scenes = _valid_stage_and_scenes()
    assert validate_stage(stage, scenes) == []


def test_missing_stage_id_is_a_violation():
    stage, scenes = _valid_stage_and_scenes()
    del stage["id"]
    violations = validate_stage(stage, scenes)
    assert any("Stage.id" in v for v in violations)


def test_duplicate_scene_id_is_a_violation():
    stage, scenes = _valid_stage_and_scenes()
    scenes.append(dict(scenes[0]))
    violations = validate_stage(stage, scenes)
    assert any("Scene.id 重复" in v for v in violations)


def test_missing_viewport_ratio_is_a_violation():
    stage, scenes = _valid_stage_and_scenes()
    del scenes[0]["content"]["canvas"]["viewportRatio"]
    violations = validate_stage(stage, scenes)
    assert any("viewportRatio" in v for v in violations)


def test_duplicate_element_id_is_a_violation():
    stage, scenes = _valid_stage_and_scenes()
    scenes[0]["content"]["canvas"]["elements"].append({"id": "el-1", "type": "shape"})
    violations = validate_stage(stage, scenes)
    assert any("element.id 重复" in v for v in violations)


def test_spotlight_referencing_missing_element_is_a_violation():
    stage, scenes = _valid_stage_and_scenes()
    scenes[0]["actions"][1]["elementId"] = "does-not-exist"
    violations = validate_stage(stage, scenes)
    assert any("spotlight.elementId" in v for v in violations)


def test_play_video_referencing_non_video_element_is_a_violation():
    stage, scenes = _valid_stage_and_scenes()
    scenes[0]["actions"][2]["elementId"] = "el-1"  # el-1 is type=text, not video
    violations = validate_stage(stage, scenes)
    assert any("play_video.elementId" in v and "不指向 video" in v for v in violations)


def test_missing_action_id_is_a_violation():
    stage, scenes = _valid_stage_and_scenes()
    del scenes[0]["actions"][0]["id"]
    violations = validate_stage(stage, scenes)
    assert any("actions[0].id 缺失" in v for v in violations)


def test_speech_audio_url_pointing_to_sidecar_local_is_a_violation():
    stage, scenes = _valid_stage_and_scenes()
    scenes[0]["actions"][0]["audioUrl"] = "http://localhost:3000/media/audio.mp3"
    violations = validate_stage(stage, scenes)
    assert any("audioUrl" in v for v in violations)


def test_speech_audio_url_pointing_to_edu_ai_storage_is_fine():
    stage, scenes = _valid_stage_and_scenes()
    scenes[0]["actions"][0]["audioUrl"] = "/api/media?path=audio/foo.mp3"
    assert validate_stage(stage, scenes) == []
