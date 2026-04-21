from pathlib import Path
import uuid

from core.course_storage import CourseStorageManager


def _temp_root() -> Path:
    root = Path("D:/Edu_AI_1/tmp/ai-lecture-session-service").resolve() / f"case-{uuid.uuid4().hex[:12]}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_course(manager: CourseStorageManager, course_id: str = "course-1") -> None:
    manager.create_course_structure(course_id)
    manager.save_course_info(
        course_id,
        {
            "id": course_id,
            "title": "计算思维",
            "description": "课程说明",
            "icon": "BookOutlined",
            "color": "#1677ff",
        },
    )


def test_storage_maps_ai_lecture_sessions_to_dedicated_directory():
    manager = CourseStorageManager(root_path=str(_temp_root()))
    _write_course(manager)

    assert manager.save_generated_material(
        "course-1",
        "ai_lecture_session",
        "ai-session-1",
        {
            "title": "AI 实时讲解",
            "content": {"session_snapshot_id": "snapshot-1"},
            "generation_state": {"status": "created"},
        },
    )

    material = manager.get_generated_material("course-1", "ai_lecture_session", "ai-session-1")
    assert material is not None
    assert material["material_type"] == "ai_lecture_session"
    assert material["material_id"] == "ai-session-1"
    assert (
        manager.get_course_dir("course-1")
        / "generated_materials"
        / "lecture_sessions"
        / "ai-session-1.json"
    ).exists()


from app.ai_lecture_sessions import (
    AiLectureSessionService,
    RecordingClientResult,
)


class StubRecordingClient:
    def __init__(self):
        self.start_calls = []
        self.stop_calls = []

    def start_recording(self, *, livetalking_session_id: int) -> RecordingClientResult:
        self.start_calls.append(livetalking_session_id)
        return RecordingClientResult(ok=True, recording_path=None, message="recording")

    def stop_recording(self, *, livetalking_session_id: int) -> RecordingClientResult:
        self.stop_calls.append(livetalking_session_id)
        source = _temp_root() / "source-recording.mp4"
        source.write_bytes(b"fake-mp4")
        return RecordingClientResult(ok=True, recording_path=str(source), message="stopped")


class StubHtmlSlideExporter:
    def __init__(self):
        self.calls = []

    def export(self, *, deck_html_path: Path, output_dir: Path):
        self.calls.append({"deck_html_path": deck_html_path, "output_dir": output_dir})
        output_dir.mkdir(parents=True, exist_ok=True)
        slide_one = output_dir / "slide-001.png"
        slide_two = output_dir / "slide-002.png"
        slide_one.write_bytes(b"png-1")
        slide_two.write_bytes(b"png-2")
        return [slide_one, slide_two]


def test_create_session_persists_material_snapshot_and_metadata():
    manager = CourseStorageManager(root_path=str(_temp_root()))
    _write_course(manager)
    service = AiLectureSessionService(storage_manager=manager, recording_client=StubRecordingClient())

    created = service.create_session(
        course_id="course-1",
        source_ppt_material_id="ppt-ready",
        title="第一讲 AI 讲解",
        owner="teacher-a",
    )

    assert created["material_id"].startswith("ai_session_")
    assert created["material_type"] == "ai_lecture_session"
    assert created["content"]["source_ppt_material_id"] == "ppt-ready"
    assert created["content"]["session_snapshot_id"] == created["material_id"]
    assert created["content"]["can_continue_interactive"] is True
    assert created["generation_state"]["status"] == "created"

    loaded = service.get_session("course-1", created["material_id"])
    assert loaded["material"]["material_id"] == created["material_id"]
    assert loaded["snapshot"]["source_ppt_material_id"] == "ppt-ready"
    assert loaded["metadata"]["recording_status"] == "not_started"


def test_patch_snapshot_appends_script_and_events_without_losing_position():
    manager = CourseStorageManager(root_path=str(_temp_root()))
    _write_course(manager)
    service = AiLectureSessionService(storage_manager=manager, recording_client=StubRecordingClient())
    created = service.create_session(
        course_id="course-1",
        source_ppt_material_id="ppt-ready",
        title="第一讲 AI 讲解",
        owner="teacher-a",
    )

    updated = service.patch_snapshot(
        course_id="course-1",
        session_id=created["material_id"],
        payload={
            "ai_lecturer_course_id": "1001",
            "outline": [{"title": "第一页", "content": "内容"}],
            "script": [{"page_index": 0, "sentences": ["第一句"]}],
            "events": [{"type": "speak", "page_index": 0, "sentence_index": 0, "text": "第一句"}],
            "last_position": {"page_index": 0, "sentence_index": 0},
        },
    )

    assert updated["ai_lecturer_course_id"] == "1001"
    assert updated["script"][0]["sentences"] == ["第一句"]
    assert updated["events"][0]["type"] == "speak"
    assert updated["last_position"] == {"page_index": 0, "sentence_index": 0}


def test_recording_stop_copies_file_to_session_directory_and_updates_material():
    manager = CourseStorageManager(root_path=str(_temp_root()))
    _write_course(manager)
    recording_client = StubRecordingClient()
    service = AiLectureSessionService(storage_manager=manager, recording_client=recording_client)
    created = service.create_session(
        course_id="course-1",
        source_ppt_material_id="ppt-ready",
        title="第一讲 AI 讲解",
        owner="teacher-a",
    )

    service.start_recording("course-1", created["material_id"], livetalking_session_id=123456)
    stopped = service.stop_recording("course-1", created["material_id"], livetalking_session_id=123456)

    assert recording_client.start_calls == [123456]
    assert recording_client.stop_calls == [123456]
    assert stopped["recording_status"] == "completed"
    assert stopped["recording_url"].endswith(f"/lecture-sessions/{created['material_id']}/recording")
    assert (
        manager.get_course_dir("course-1")
        / "generated_materials"
        / "lecture_sessions"
        / created["material_id"]
        / "recording.mp4"
    ).exists()

    material = manager.get_generated_material("course-1", "ai_lecture_session", created["material_id"])
    assert material["content"]["recording_url"] == stopped["recording_url"]
    assert material["generation_state"]["status"] == "completed"


def test_get_session_populates_slide_image_urls_from_source_ppt_deck():
    manager = CourseStorageManager(root_path=str(_temp_root()))
    _write_course(manager)
    jobs_root = manager.root_path / "html2ppt-jobs"
    deck_path = jobs_root / "job-1" / "revisions" / "rev_0001" / "deck.html"
    deck_path.parent.mkdir(parents=True, exist_ok=True)
    deck_path.write_text("<html><body><div class='slide'>slide</div></body></html>", encoding="utf-8")
    manager.save_generated_material(
        "course-1",
        "ppt",
        "ppt-ready",
        {
            "title": "PPT Deck",
            "content": {
                "html_full_url": "/ppt/artifacts/job-1/rev_0001/deck.html",
                "slide_count": 2,
            },
            "generation_state": {"status": "completed"},
        },
    )
    exporter = StubHtmlSlideExporter()
    service = AiLectureSessionService(
        storage_manager=manager,
        recording_client=StubRecordingClient(),
        html_slide_exporter=exporter,
        html2ppt_jobs_root=jobs_root,
    )
    created = service.create_session(
        course_id="course-1",
        source_ppt_material_id="ppt-ready",
        title="AI Lecture",
        owner="teacher-a",
    )

    loaded = service.get_session("course-1", created["material_id"])

    assert exporter.calls, "session load should export slide images from the source deck"
    assert loaded["snapshot"]["slide_count"] == 2
    assert loaded["snapshot"]["slide_image_urls"] == [
        f"/api/courses/course-1/lecture-sessions/{created['material_id']}/slides/slide-001.png",
        f"/api/courses/course-1/lecture-sessions/{created['material_id']}/slides/slide-002.png",
    ]
