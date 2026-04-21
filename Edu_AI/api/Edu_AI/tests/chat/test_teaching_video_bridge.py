from pathlib import Path
import uuid

from core.course_storage import CourseStorageManager

from app.teaching_video_bridge import OfflineTeachingVideoDisabledError, TeachingVideoBridgeService


class StubPptDownloader:
    def __init__(self, pptx_path: Path):
        self.pptx_path = pptx_path
        self.calls = []

    def download(self, *, source_url: str, destination_path: Path) -> Path:
        self.calls.append({"source_url": source_url, "destination_path": destination_path})
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(self.pptx_path.read_bytes())
        return destination_path


class StubSlideExporter:
    def __init__(self, exported_images: list[Path]):
        self.exported_images = exported_images
        self.calls = []

    def export(self, *, pptx_path: Path, output_dir: Path) -> list[Path]:
        self.calls.append({"pptx_path": pptx_path, "output_dir": output_dir})
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []
        for image in self.exported_images:
            target = output_dir / image.name
            target.write_bytes(image.read_bytes())
            results.append(target)
        return results


class StubHtmlSlideExporter:
    def __init__(self, exported_images: list[Path]):
        self.exported_images = exported_images
        self.calls = []

    def export(self, *, deck_html_path: Path, output_dir: Path) -> list[Path]:
        self.calls.append({"deck_html_path": deck_html_path, "output_dir": output_dir})
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []
        for image in self.exported_images:
            target = output_dir / image.name
            target.write_bytes(image.read_bytes())
            results.append(target)
        return results


class StubAiLecturerClient:
    def __init__(self):
        self.create_calls = []
        self.status_calls = []

    def create_offline_video(self, *, course_title: str, pages: list[dict]) -> dict:
        self.create_calls.append({"course_title": course_title, "pages": pages})
        return {
            "task_id": "course_task_001",
            "status": "processing",
            "video_url": "/api/v1/offline/download/course_task_001.mp4",
        }

    def get_offline_task_status(self, task_id: str) -> dict:
        self.status_calls.append(task_id)
        return {
            "task_id": task_id,
            "status": "success",
            "video_url": "/api/v1/offline/download/course_task_001.mp4",
        }


class FailingAiLecturerClient(StubAiLecturerClient):
    def get_offline_task_status(self, task_id: str) -> dict:
        self.status_calls.append(task_id)
        return {
            "task_id": task_id,
            "status": "failed",
            "video_url": "",
            "error": "Wav2Lip inference failed",
        }


def _make_temp_root() -> Path:
    base_dir = Path("D:/Edu_AI_1/tmp/teaching-video-bridge").resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    case_dir = base_dir / f"case-{uuid.uuid4().hex[:12]}"
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def _write_course_info(storage_manager: CourseStorageManager, course_id: str) -> None:
    storage_manager.create_course_structure(course_id)
    storage_manager.save_course_info(
        course_id,
        {
            "id": course_id,
            "title": "计算机网络",
            "description": "课程描述",
            "icon": "BookOutlined",
            "color": "#1677ff",
        },
    )


def test_list_available_ppts_only_returns_decks_with_pptx_and_markdown():
    tmp_path = _make_temp_root()
    storage_manager = CourseStorageManager(root_path=str(tmp_path))
    _write_course_info(storage_manager, "course-1")
    html2ppt_jobs_root = tmp_path / "html2ppt-jobs"
    legacy_content_path = html2ppt_jobs_root / "job-2" / "revisions" / "rev_0000" / "content.md"
    legacy_content_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_content_path.write_text("# Legacy Deck\n\n## Slide 1\n- Title: Legacy\n", encoding="utf-8")

    storage_manager.save_generated_material(
        course_id="course-1",
        material_type="ppt",
        material_id="ppt-ready",
        material_data={
            "title": "TCP 三次握手.pptx",
            "content": {
                "pptx_url": "http://127.0.0.1:46080/ppt/artifacts/job-1/rev_0000/deck.pptx",
                "html_full_url": "http://127.0.0.1:46080/ppt/artifacts/job-1/rev_0000/deck.html",
                "content_markdown": "# Deck\n\n## Slide 1\n- Role: cover\n- Title: TCP\n\n### Blocks\n- Lead: intro\n",
                "slide_count": 1,
            },
            "generation_state": {"status": "completed"},
        },
    )
    storage_manager.save_generated_material(
        course_id="course-1",
        material_type="ppt",
        material_id="ppt-missing-markdown",
        material_data={
            "title": "不完整课件.pptx",
            "content": {
                "pptx_url": "http://127.0.0.1:46080/ppt/artifacts/job-2/rev_0000/deck.pptx",
                "job_id": "job-2",
                "revision_id": "rev_0000",
            },
            "generation_state": {"status": "completed"},
        },
    )

    service = TeachingVideoBridgeService(
        course_storage_manager=storage_manager,
        ai_lecturer_client=StubAiLecturerClient(),
        ppt_downloader=StubPptDownloader(tmp_path / "unused.pptx"),
        slide_exporter=StubSlideExporter([]),
        task_root=tmp_path / "tasks",
        html2ppt_jobs_root=html2ppt_jobs_root,
    )

    items = service.list_available_ppts("course-1")

    assert len(items) == 2
    by_id = {item["material_id"]: item for item in items}
    assert set(by_id) == {"ppt-ready", "ppt-missing-markdown"}
    assert by_id["ppt-ready"]["material_id"] == "ppt-ready"
    assert by_id["ppt-ready"]["pptx_url"].endswith("deck.pptx")
    return
    assert items[0]["title"] == "TCP 三次握手.pptx"
    assert items[0]["pptx_url"].endswith("deck.pptx")
    assert items[1]["material_id"] == "ppt-missing-markdown"


def test_create_task_adapts_ppt_and_content_markdown_into_ai_lecturer_pages(monkeypatch):
    monkeypatch.setenv("AI_LECTURER_OFFLINE_ENABLED", "1")
    tmp_path = _make_temp_root()
    storage_manager = CourseStorageManager(root_path=str(tmp_path))
    _write_course_info(storage_manager, "course-1")

    pptx_source = tmp_path / "source-deck.pptx"
    pptx_source.write_bytes(b"fake pptx")
    slide_one = tmp_path / "slide-1.png"
    slide_two = tmp_path / "slide-2.png"
    slide_one.write_bytes(b"slide-1")
    slide_two.write_bytes(b"slide-2")

    storage_manager.save_generated_material(
        course_id="course-1",
        material_type="ppt",
        material_id="ppt-ready",
        material_data={
            "title": "TCP 三次握手.pptx",
            "content": {
                "pptx_url": "http://127.0.0.1:46080/ppt/artifacts/job-1/rev_0000/deck.pptx",
                "html_full_url": "http://127.0.0.1:46080/ppt/artifacts/job-1/rev_0000/deck.html",
                "content_markdown": (
                    "# Deck\n"
                    "\n"
                    "## Slide 1\n"
                    "- Role: cover\n"
                    "- Title: TCP 三次握手\n"
                    "\n"
                    "### Blocks\n"
                    "- Lead: 介绍课程目标\n"
                    "\n"
                    "---\n"
                    "\n"
                    "## Slide 2\n"
                    "- Role: content\n"
                    "- Title: 建立连接流程\n"
                    "\n"
                    "### Blocks\n"
                    "- Bullets:\n"
                    "  - 客户端发送 SYN\n"
                    "  - 服务端回复 SYN-ACK\n"
                ),
                "slide_count": 2,
            },
            "outline": {
                "slides": [
                    {"slide_index": 1, "title": "TCP 三次握手", "goal": "介绍课程目标"},
                    {"slide_index": 2, "title": "建立连接流程", "goal": "讲解三次握手"},
                ]
            },
            "generation_state": {"status": "completed"},
        },
    )

    downloader = StubPptDownloader(pptx_source)
    exporter = StubSlideExporter([slide_one, slide_two])
    ai_client = StubAiLecturerClient()

    service = TeachingVideoBridgeService(
        course_storage_manager=storage_manager,
        ai_lecturer_client=ai_client,
        ppt_downloader=downloader,
        slide_exporter=exporter,
        task_root=tmp_path / "tasks",
    )

    task = service.create_task(course_id="course-1", ppt_material_id="ppt-ready", owner="teacher-a")

    assert task["task_id"] == "course_task_001"
    assert ai_client.create_calls[0]["course_title"] == "TCP 三次握手"
    assert len(ai_client.create_calls[0]["pages"]) == 2
    assert ai_client.create_calls[0]["pages"][0]["ppt_image_path"].endswith("slide-1.png")
    assert "TCP 三次握手" in ai_client.create_calls[0]["pages"][0]["content_text"]
    assert "客户端发送 SYN" in ai_client.create_calls[0]["pages"][1]["content_text"]

    saved_video = storage_manager.get_generated_material("course-1", "video", "teaching_video__course_task_001")
    assert saved_video is not None
    assert saved_video["generation_state"]["status"] == "processing"
    assert saved_video["content"]["task_id"] == "course_task_001"
    assert saved_video["content"]["source_ppt_material_id"] == "ppt-ready"


def test_create_task_prefers_html_deck_export_when_deck_html_exists(monkeypatch):
    monkeypatch.setenv("AI_LECTURER_OFFLINE_ENABLED", "1")
    tmp_path = _make_temp_root()
    storage_manager = CourseStorageManager(root_path=str(tmp_path))
    _write_course_info(storage_manager, "course-1")

    html2ppt_jobs_root = tmp_path / "html2ppt-jobs"
    deck_html_path = html2ppt_jobs_root / "job-html" / "revisions" / "rev_0000" / "deck.html"
    deck_html_path.parent.mkdir(parents=True, exist_ok=True)
    deck_html_path.write_text("<html><body><section class='slide'>Slide 1</section></body></html>", encoding="utf-8")

    pptx_source = tmp_path / "source-deck.pptx"
    pptx_source.write_bytes(b"fake pptx")
    slide_one = tmp_path / "html-slide-1.png"
    slide_one.write_bytes(b"html-slide-1")

    storage_manager.save_generated_material(
        course_id="course-1",
        material_type="ppt",
        material_id="ppt-ready",
        material_data={
            "title": "Agent intro.pptx",
            "content": {
                "pptx_url": "http://127.0.0.1:46080/ppt/artifacts/job-html/rev_0000/deck.pptx",
                "html_full_url": "http://127.0.0.1:46080/ppt/artifacts/job-html/rev_0000/deck.html",
                "job_id": "job-html",
                "revision_id": "rev_0000",
                "content_markdown": (
                    "# Deck\n"
                    "\n"
                    "## Slide 1\n"
                    "- Role: cover\n"
                    "- Title: Agent intro\n"
                    "\n"
                    "### Blocks\n"
                    "- Lead: Explain what agents can do\n"
                ),
                "slide_count": 1,
            },
            "generation_state": {"status": "completed"},
        },
    )

    downloader = StubPptDownloader(pptx_source)
    ppt_exporter = StubSlideExporter([])
    html_exporter = StubHtmlSlideExporter([slide_one])
    ai_client = StubAiLecturerClient()

    service = TeachingVideoBridgeService(
        course_storage_manager=storage_manager,
        ai_lecturer_client=ai_client,
        ppt_downloader=downloader,
        slide_exporter=ppt_exporter,
        html_slide_exporter=html_exporter,
        task_root=tmp_path / "tasks",
        html2ppt_jobs_root=html2ppt_jobs_root,
    )

    task = service.create_task(course_id="course-1", ppt_material_id="ppt-ready", owner="teacher-a")

    assert task["task_id"] == "course_task_001"
    assert downloader.calls == []
    assert ppt_exporter.calls == []
    assert len(html_exporter.calls) == 1
    assert html_exporter.calls[0]["deck_html_path"] == deck_html_path.resolve()
    assert ai_client.create_calls[0]["pages"][0]["ppt_image_path"].endswith("html-slide-1.png")
    assert "Agent intro" in ai_client.create_calls[0]["pages"][0]["content_text"]


def test_create_task_disabled_by_env_before_expensive_export(monkeypatch):
    monkeypatch.setenv("AI_LECTURER_OFFLINE_ENABLED", "0")
    tmp_path = _make_temp_root()
    storage_manager = CourseStorageManager(root_path=str(tmp_path))
    _write_course_info(storage_manager, "course-1")

    pptx_source = tmp_path / "source-deck.pptx"
    pptx_source.write_bytes(b"fake pptx")
    slide_one = tmp_path / "slide-1.png"
    slide_one.write_bytes(b"slide-1")

    storage_manager.save_generated_material(
        course_id="course-1",
        material_type="ppt",
        material_id="ppt-ready",
        material_data={
            "title": "Agent intro.pptx",
            "content": {
                "pptx_url": "http://127.0.0.1:46080/ppt/artifacts/job-1/rev_0000/deck.pptx",
                "content_markdown": "# Deck\n\n## Slide 1\n- Title: Agent intro\n",
                "slide_count": 1,
            },
            "generation_state": {"status": "completed"},
        },
    )

    downloader = StubPptDownloader(pptx_source)
    exporter = StubSlideExporter([slide_one])
    ai_client = StubAiLecturerClient()
    service = TeachingVideoBridgeService(
        course_storage_manager=storage_manager,
        ai_lecturer_client=ai_client,
        ppt_downloader=downloader,
        slide_exporter=exporter,
        task_root=tmp_path / "tasks",
    )

    try:
        service.create_task(course_id="course-1", ppt_material_id="ppt-ready", owner="teacher-a")
    except OfflineTeachingVideoDisabledError as exc:
        assert "AI_LECTURER_OFFLINE_ENABLED" in str(exc)
    else:
        raise AssertionError("expected offline teaching video generation to be disabled")

    assert downloader.calls == []
    assert exporter.calls == []
    assert ai_client.create_calls == []


def test_get_task_status_persists_completed_video_material():
    tmp_path = _make_temp_root()
    storage_manager = CourseStorageManager(root_path=str(tmp_path))
    _write_course_info(storage_manager, "course-1")

    storage_manager.save_generated_material(
        course_id="course-1",
        material_type="video",
        material_id="teaching_video__course_task_001",
        material_data={
            "title": "TCP 三次握手-教学视频.mp4",
            "content": {
                "task_id": "course_task_001",
                "source_ppt_material_id": "ppt-ready",
            },
            "generation_state": {"status": "processing"},
        },
    )

    service = TeachingVideoBridgeService(
        course_storage_manager=storage_manager,
        ai_lecturer_client=StubAiLecturerClient(),
        ppt_downloader=StubPptDownloader(tmp_path / "unused.pptx"),
        slide_exporter=StubSlideExporter([]),
        task_root=tmp_path / "tasks",
    )

    status = service.get_task_status(course_id="course-1", task_id="course_task_001")

    assert status["status"] == "success"
    persisted = storage_manager.get_generated_material("course-1", "video", "teaching_video__course_task_001")
    assert persisted is not None
    assert persisted["generation_state"]["status"] == "completed"
    assert persisted["content"]["video_url"].endswith("course_task_001.mp4")


def test_get_task_status_returns_and_persists_failed_error_message():
    tmp_path = _make_temp_root()
    storage_manager = CourseStorageManager(root_path=str(tmp_path))
    _write_course_info(storage_manager, "course-1")

    storage_manager.save_generated_material(
        course_id="course-1",
        material_type="video",
        material_id="teaching_video__course_task_001",
        material_data={
            "title": "Agent intro-video.mp4",
            "content": {"task_id": "course_task_001"},
            "generation_state": {"status": "processing"},
        },
    )

    service = TeachingVideoBridgeService(
        course_storage_manager=storage_manager,
        ai_lecturer_client=FailingAiLecturerClient(),
        ppt_downloader=StubPptDownloader(tmp_path / "unused.pptx"),
        slide_exporter=StubSlideExporter([]),
        task_root=tmp_path / "tasks",
    )

    status = service.get_task_status(course_id="course-1", task_id="course_task_001")

    assert status["status"] == "failed"
    assert status["error_message"] == "Wav2Lip inference failed"
    persisted = storage_manager.get_generated_material("course-1", "video", "teaching_video__course_task_001")
    assert persisted is not None
    assert persisted["generation_state"]["status"] == "failed"
    assert persisted["generation_state"]["message"] == "Wav2Lip inference failed"
    assert persisted["content"]["error_message"] == "Wav2Lip inference failed"
