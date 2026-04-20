from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.course_storage import CourseStorageManager, storage_manager


AI_LECTURE_SESSION_TYPE = "ai_lecture_session"


class CreateAiLectureSessionRequest(BaseModel):
    source_ppt_material_id: str = Field(..., min_length=1)
    title: Optional[str] = None


class PatchAiLectureSessionSnapshotRequest(BaseModel):
    ai_lecturer_course_id: Optional[str] = None
    outline: Optional[list[dict[str, Any]]] = None
    script: Optional[list[dict[str, Any]]] = None
    events: Optional[list[dict[str, Any]]] = None
    last_position: Optional[dict[str, int]] = None


class AiLectureRecordingRequest(BaseModel):
    livetalking_session_id: int = Field(..., ge=1)


@dataclass
class RecordingClientResult:
    ok: bool
    recording_path: Optional[str] = None
    message: str = ""


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
    def __init__(self, storage_manager: CourseStorageManager, recording_client: Optional[Any] = None):
        self.storage_manager = storage_manager
        self.recording_client = recording_client or LiveTalkingRecordingClient()

    def _now(self) -> str:
        return datetime.now().isoformat()

    def _session_dir(self, course_id: str, session_id: str) -> Path:
        return self.storage_manager.get_course_dir(course_id) / "generated_materials" / "lecture_sessions" / session_id

    def _snapshot_path(self, course_id: str, session_id: str) -> Path:
        return self._session_dir(course_id, session_id) / "snapshot.json"

    def _metadata_path(self, course_id: str, session_id: str) -> Path:
        return self._session_dir(course_id, session_id) / "metadata.json"

    def _read_json(self, path: Path) -> Dict[str, Any]:
        return self.storage_manager._read_json(path) or {}

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        self.storage_manager._write_json(path, payload)

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
        return self.storage_manager.get_generated_material(course_id, AI_LECTURE_SESSION_TYPE, session_id) or {}

    def get_session(self, course_id: str, session_id: str) -> Dict[str, Any]:
        material = self.storage_manager.get_generated_material(course_id, AI_LECTURE_SESSION_TYPE, session_id)
        if not material:
            raise ValueError("AI lecture session not found")
        return {
            "material": material,
            "snapshot": self._read_json(self._snapshot_path(course_id, session_id)),
            "metadata": self._read_json(self._metadata_path(course_id, session_id)),
        }

    def patch_snapshot(self, *, course_id: str, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        current = self._read_json(self._snapshot_path(course_id, session_id))
        if not current:
            raise ValueError("AI lecture session snapshot not found")
        for key in ("ai_lecturer_course_id", "outline", "script", "last_position"):
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


_service: Optional[AiLectureSessionService] = None


def get_ai_lecture_session_service() -> AiLectureSessionService:
    global _service
    if _service is None:
        _service = AiLectureSessionService(storage_manager=storage_manager)
    return _service
