from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi.responses import FileResponse

from app.schemas.ai_lecture_sessions import (
    AiLectureRecordingRequest,
    CreateAiLectureSessionRequest,
    PatchAiLectureSessionSnapshotRequest,
    RecordingClientResult,
)
from app.teaching_video_bridge import HtmlDeckSlideImageExporter
from core.config import Config
from core.course_storage import CourseStorageManager, storage_manager

AI_LECTURE_SESSION_TYPE = "ai_lecture_session"


class LiveTalkingRecordingClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8010"):
        self.base_url = base_url.rstrip("/")

    def _post_record(self, *, livetalking_session_id: int, action: str) -> RecordingClientResult:
        response = requests.post(
            f"{self.base_url}/record",
            json={"sessionid": livetalking_session_id, "type": action},
            timeout=10,
        )
        payload = response.json()
        if not response.ok or payload.get("code") not in (0, 200):
            return RecordingClientResult(
                ok=False,
                message=str(payload.get("msg") or payload.get("detail") or "recording failed"),
            )
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        return RecordingClientResult(
            ok=True,
            recording_path=data.get("recording_path"),
            message=str(payload.get("msg") or "ok"),
        )

    def start_recording(self, *, livetalking_session_id: int) -> RecordingClientResult:
        return self._post_record(livetalking_session_id=livetalking_session_id, action="start_record")

    def stop_recording(self, *, livetalking_session_id: int) -> RecordingClientResult:
        return self._post_record(livetalking_session_id=livetalking_session_id, action="end_record")


class AiLectureSessionService:
    def __init__(
        self,
        storage_manager: CourseStorageManager,
        recording_client: Optional[Any] = None,
        html_slide_exporter: Optional[Any] = None,
        html2ppt_jobs_root: Optional[Path] = None,
    ):
        self.storage_manager = storage_manager
        self.recording_client = recording_client or LiveTalkingRecordingClient()
        self.html_slide_exporter = html_slide_exporter or HtmlDeckSlideImageExporter()
        self.html2ppt_jobs_root = Path(html2ppt_jobs_root or Config.HTML2PPT_JOBS_ROOT).resolve()

    def _now(self) -> str:
        return datetime.now().isoformat()

    def _session_dir(self, course_id: str, session_id: str) -> Path:
        return self.storage_manager.get_course_dir(course_id) / "generated_materials" / "lecture_sessions" / session_id

    def _snapshot_path(self, course_id: str, session_id: str) -> Path:
        return self._session_dir(course_id, session_id) / "snapshot.json"

    def _metadata_path(self, course_id: str, session_id: str) -> Path:
        return self._session_dir(course_id, session_id) / "metadata.json"

    def _slides_dir(self, course_id: str, session_id: str) -> Path:
        return self._session_dir(course_id, session_id) / "slides"

    def _read_json(self, path: Path) -> Dict[str, Any]:
        return self.storage_manager._read_json(path) or {}

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        self.storage_manager._write_json(path, payload)

    def _extract_job_ref(self, html_full_url: str) -> tuple[str, str]:
        import re

        match = re.search(r"/ppt/artifacts/([^/]+)/([^/]+)/", str(html_full_url or "").strip())
        if not match:
            return "", ""
        return match.group(1).strip(), match.group(2).strip()

    def _resolve_source_deck_path(self, *, course_id: str, source_ppt_material_id: str) -> Path | None:
        material = self.storage_manager.get_generated_material(course_id, "ppt", source_ppt_material_id)
        if not material:
            return None
        content = material.get("content")
        if not isinstance(content, dict):
            return None
        job_id, revision_id = self._extract_job_ref(str(content.get("html_full_url") or content.get("html_url") or ""))
        if not job_id or not revision_id:
            return None
        try:
            deck_path = (self.html2ppt_jobs_root / job_id / "revisions" / revision_id / "deck.html").resolve()
            deck_path.relative_to(self.html2ppt_jobs_root)
        except Exception:
            return None
        return deck_path if deck_path.is_file() else None

    def _slide_image_url(self, *, course_id: str, session_id: str, slide_name: str) -> str:
        return f"/api/courses/{course_id}/lecture-sessions/{session_id}/slides/{slide_name}"

    def _ensure_slide_images(self, *, course_id: str, session_id: str, source_ppt_material_id: str) -> Dict[str, Any]:
        snapshot = self._read_json(self._snapshot_path(course_id, session_id))
        if not snapshot or not source_ppt_material_id:
            return snapshot

        existing_urls = snapshot.get("slide_image_urls")
        if isinstance(existing_urls, list) and existing_urls:
            return snapshot

        slides_dir = self._slides_dir(course_id, session_id)
        slide_paths = sorted(slides_dir.glob("slide-*.png"))
        if not slide_paths:
            deck_path = self._resolve_source_deck_path(course_id=course_id, source_ppt_material_id=source_ppt_material_id)
            if deck_path is None:
                return snapshot
            slides_dir.mkdir(parents=True, exist_ok=True)
            slide_paths = list(self.html_slide_exporter.export(deck_html_path=deck_path, output_dir=slides_dir))

        if slide_paths:
            snapshot["slide_image_urls"] = [
                self._slide_image_url(course_id=course_id, session_id=session_id, slide_name=path.name)
                for path in slide_paths
            ]
            snapshot["slide_count"] = len(slide_paths)
            snapshot["updated_at"] = self._now()
            self._write_json(self._snapshot_path(course_id, session_id), snapshot)
        return snapshot

    def create_session(
        self,
        *,
        course_id: str,
        source_ppt_material_id: str,
        title: Optional[str],
        owner: str = "",
    ) -> Dict[str, Any]:
        session_id = f"ai_session_{uuid.uuid4().hex[:12]}"
        now = self._now()
        self._session_dir(course_id, session_id).mkdir(parents=True, exist_ok=True)
        snapshot = {
            "snapshot_id": session_id,
            "course_id": course_id,
            "source_ppt_material_id": source_ppt_material_id,
            "ai_lecturer_course_id": None,
            "outline": [],
            "script": [],
            "events": [],
            "last_position": {"page_index": 0, "sentence_index": 0},
            "created_at": now,
            "updated_at": now,
        }
        metadata = {
            "session_id": session_id,
            "source_ppt_material_id": source_ppt_material_id,
            "recording_status": "not_started",
            "recording_url": None,
            "created_by": owner,
            "created_at": now,
            "updated_at": now,
        }
        material = {
            "title": title or "AI 实时讲解",
            "summary": "由 PPT 生成的 AI 实时讲解会话，包含录播回看和继续互动入口。",
            "content": {
                "source_ppt_material_id": source_ppt_material_id,
                "session_snapshot_id": session_id,
                "recording_asset_id": None,
                "recording_url": None,
                "can_continue_interactive": True,
            },
            "generation_state": {
                "status": "created",
                "phase": "created",
                "message": "AI 讲解会话已创建",
            },
        }
        self._write_json(self._snapshot_path(course_id, session_id), snapshot)
        self._write_json(self._metadata_path(course_id, session_id), metadata)
        self.storage_manager.save_generated_material(course_id, AI_LECTURE_SESSION_TYPE, session_id, material)
        self._ensure_slide_images(
            course_id=course_id,
            session_id=session_id,
            source_ppt_material_id=source_ppt_material_id,
        )
        return self.storage_manager.get_generated_material(course_id, AI_LECTURE_SESSION_TYPE, session_id) or {}

    def get_session(self, course_id: str, session_id: str) -> Dict[str, Any]:
        material = self.storage_manager.get_generated_material(course_id, AI_LECTURE_SESSION_TYPE, session_id)
        if not material:
            raise ValueError("AI lecture session not found")
        content = material.get("content")
        source_ppt_material_id = str(content.get("source_ppt_material_id") or "").strip() if isinstance(content, dict) else ""
        snapshot = self._ensure_slide_images(
            course_id=course_id,
            session_id=session_id,
            source_ppt_material_id=source_ppt_material_id,
        )
        return {
            "material": material,
            "snapshot": snapshot,
            "metadata": self._read_json(self._metadata_path(course_id, session_id)),
        }

    def patch_snapshot(self, *, course_id: str, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        current = self._read_json(self._snapshot_path(course_id, session_id))
        if not current:
            raise ValueError("AI lecture session snapshot not found")
        for key in ("ai_lecturer_course_id", "outline", "script", "last_position", "slide_image_urls", "slide_count"):
            if key in payload and payload[key] is not None:
                current[key] = payload[key]
        if payload.get("events"):
            current["events"] = [*current.get("events", []), *payload["events"]]
        current["updated_at"] = self._now()
        self._write_json(self._snapshot_path(course_id, session_id), current)
        return current

    def start_recording(self, course_id: str, session_id: str, *, livetalking_session_id: int) -> Dict[str, Any]:
        result = self.recording_client.start_recording(livetalking_session_id=livetalking_session_id)
        if not result.ok:
            raise RuntimeError(result.message)
        metadata = self._read_json(self._metadata_path(course_id, session_id))
        metadata.update(
            {
                "recording_status": "recording",
                "livetalking_session_id": livetalking_session_id,
                "updated_at": self._now(),
            }
        )
        self._write_json(self._metadata_path(course_id, session_id), metadata)
        return metadata

    def stop_recording(self, course_id: str, session_id: str, *, livetalking_session_id: int) -> Dict[str, Any]:
        result = self.recording_client.stop_recording(livetalking_session_id=livetalking_session_id)
        if not result.ok or not result.recording_path:
            raise RuntimeError(result.message or "recording output missing")
        source_path = Path(result.recording_path)
        target_path = self._session_dir(course_id, session_id) / "recording.mp4"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)
        recording_url = f"/api/courses/{course_id}/lecture-sessions/{session_id}/recording"
        metadata = self._read_json(self._metadata_path(course_id, session_id))
        metadata.update({"recording_status": "completed", "recording_url": recording_url, "updated_at": self._now()})
        self._write_json(self._metadata_path(course_id, session_id), metadata)
        material = self.storage_manager.get_generated_material(course_id, AI_LECTURE_SESSION_TYPE, session_id) or {}
        content = dict(material.get("content") or {})
        content.update({"recording_asset_id": session_id, "recording_url": recording_url, "can_continue_interactive": True})
        material.update(
            {
                "content": content,
                "generation_state": {
                    "status": "completed",
                    "phase": "recording_ready",
                    "message": "AI 讲解录播已生成，可继续互动",
                },
            }
        )
        self.storage_manager.save_generated_material(course_id, AI_LECTURE_SESSION_TYPE, session_id, material)
        return metadata

    def recording_response(self, course_id: str, session_id: str) -> FileResponse:
        path = self._session_dir(course_id, session_id) / "recording.mp4"
        if not path.exists():
            raise FileNotFoundError(str(path))
        return FileResponse(path=path, filename=f"{session_id}.mp4", media_type="video/mp4")

    def slide_image_response(self, course_id: str, session_id: str, slide_name: str) -> FileResponse:
        if not str(slide_name or "").strip() or "/" in slide_name or "\\" in slide_name:
            raise FileNotFoundError(slide_name)
        slides_root = self._slides_dir(course_id, session_id).resolve()
        path = (slides_root / slide_name).resolve()
        try:
            path.relative_to(slides_root)
        except Exception as exc:
            raise FileNotFoundError(slide_name) from exc
        if not path.exists():
            raise FileNotFoundError(str(path))
        return FileResponse(path=path, filename=path.name, media_type="image/png")


_service: Optional[AiLectureSessionService] = None


def get_ai_lecture_session_service() -> AiLectureSessionService:
    global _service
    if _service is None:
        _service = AiLectureSessionService(storage_manager=storage_manager)
    return _service
