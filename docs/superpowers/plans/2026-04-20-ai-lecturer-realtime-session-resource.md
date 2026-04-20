# AI Lecturer Realtime Session Resource Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI Lecturer course resource that supports realtime WebRTC interaction, recorded replay, and resumable interaction from a persisted session snapshot.

**Architecture:** Add a backend `ai_lecture_session` material type and a focused session service that owns snapshots, recording metadata, and course-resource persistence. Replace the Stitch realtime player iframe with React-managed WebRTC so the returned `sessionid` drives every speak, stop, and interrupt call. Course resources render `ai_lecture_session` as a dual-entry resource: replay recording or continue interaction.

**Tech Stack:** FastAPI, Pydantic, filesystem-backed `CourseStorageManager`, LiveTalking/aiohttp recording API, React, TypeScript, WebRTC, Node test runner, pytest.

---

## File Structure

- Modify `Edu_AI/api/Edu_AI/core/course_storage.py`: add `ai_lecture_session` to generated material storage mapping.
- Create `Edu_AI/api/Edu_AI/app/ai_lecture_sessions.py`: service, request models, response models, snapshot helpers, recording client, and recording file persistence.
- Modify `Edu_AI/api/Edu_AI/app/courses.py`: expose lecture-session routes and delegate to the new service.
- Modify `Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/avatars/base_avatar.py`: make recording output session-specific instead of `data/record.mp4`.
- Modify `Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/server/routes.py`: return recording file metadata from `/record`.
- Create `Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/server/recording_paths.py`: pure helper for safe recording output paths.
- Create `Edu_AI/api/Edu_AI/tests/chat/test_ai_lecture_session_service.py`: backend service tests.
- Create `Edu_AI/api/Edu_AI/tests/chat/test_ai_lecture_session_routes.py`: route tests.
- Create `Edu_AI/api/Edu_AI/tests/chat/test_livetalking_recording_paths.py`: path-contract test for LiveTalking recording helper.
- Modify `Edu_AI/src/stitch/api/types.ts`: add AI lecture session, snapshot, and WebRTC offer types.
- Modify `Edu_AI/src/stitch/api/video.ts`: add AI lecture session APIs and `offer` URL helper.
- Create `Edu_AI/src/stitch/hooks/useAiLecturerWebRtc.ts`: React hook that owns `RTCPeerConnection`, media streams, `sessionId`, and cleanup.
- Modify `Edu_AI/src/stitch/pages/VideoPlayer.tsx`: remove iframe path, use hook session id, load snapshots, patch events.
- Modify `Edu_AI/src/stitch/pages/CourseResources.tsx`: render `ai_lecture_session` details with replay and continue-interaction entries.
- Modify `Edu_AI/src/stitch/api/courses.ts`: add helper functions for lecture-session URLs and type-aware markdown fallback.
- Create `Edu_AI/tests/frontend/aiLecturerApi.session.test.ts`: static API contract tests.
- Create `Edu_AI/tests/frontend/aiLecturerWebRtcHook.test.ts`: static WebRTC hook contract tests.
- Create `Edu_AI/tests/frontend/stitchCourseResources.aiLectureSession.test.ts`: static resource rendering tests.
- Create `Edu_AI/tests/frontend/stitchVideoPlayer.aiLecturerSession.test.ts`: static VideoPlayer session-id tests.

---

### Task 1: Add Storage Type For AI Lecture Sessions

**Files:**
- Modify: `Edu_AI/api/Edu_AI/core/course_storage.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_ai_lecture_session_service.py`

- [ ] **Step 1: Write the failing storage test**

Add this test file with the first test:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_ai_lecture_session_service.py::test_storage_maps_ai_lecture_sessions_to_dedicated_directory -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: FAIL because `ai_lecture_session` currently maps to `generated_materials/others`.

- [ ] **Step 3: Add the storage mapping**

In `Edu_AI/api/Edu_AI/core/course_storage.py`, update `TYPE_MAPPING`:

```python
TYPE_MAPPING = {
    "audio": "audio",
    "lesson_plan": "lesson_plans",
    "graph": "graphs",
    "report": "reports",
    "ppt": "ppts",
    "video": "videos",
    "ai_lecture_session": "lecture_sessions",
    "blog": "blogs",
    "quiz": "quizzes",
}
```

In `create_course_structure`, add the directory:

```python
(course_dir / "generated_materials" / "lecture_sessions").mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_ai_lecture_session_service.py::test_storage_maps_ai_lecture_sessions_to_dedicated_directory -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git -C D:\Edu_AI_1 add Edu_AI/api/Edu_AI/core/course_storage.py Edu_AI/api/Edu_AI/tests/chat/test_ai_lecture_session_service.py
git -C D:\Edu_AI_1 commit -m "Add AI lecture session material storage"
```

---

### Task 2: Build Backend AI Lecture Session Service

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/ai_lecture_sessions.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_ai_lecture_session_service.py`

- [ ] **Step 1: Extend service tests**

Append these tests:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_ai_lecture_session_service.py -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: FAIL because `app.ai_lecture_sessions` does not exist.

- [ ] **Step 3: Create the service**

Create `Edu_AI/api/Edu_AI/app/ai_lecture_sessions.py` with these definitions:

```python
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
            return RecordingClientResult(ok=False, message=str(payload.get("msg") or payload.get("detail") or "recording failed"))
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        return RecordingClientResult(ok=True, recording_path=data.get("recording_path"), message=str(payload.get("msg") or "ok"))

    def start_recording(self, *, livetalking_session_id: int) -> RecordingClientResult:
        return self._post_record(livetalking_session_id=livetalking_session_id, action="start_record")

    def stop_recording(self, *, livetalking_session_id: int) -> RecordingClientResult:
        return self._post_record(livetalking_session_id=livetalking_session_id, action="end_record")


class AiLectureSessionService:
    def __init__(self, storage_manager: CourseStorageManager, recording_client: Optional[LiveTalkingRecordingClient] = None):
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

    def create_session(self, *, course_id: str, source_ppt_material_id: str, title: Optional[str], owner: str = "") -> Dict[str, Any]:
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
        metadata.update({"recording_status": "recording", "livetalking_session_id": livetalking_session_id, "updated_at": self._now()})
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
                "generation_state": {"status": "completed", "phase": "recording_ready", "message": "AI 讲解录播已生成，可继续互动"},
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
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_ai_lecture_session_service.py -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git -C D:\Edu_AI_1 add Edu_AI/api/Edu_AI/app/ai_lecture_sessions.py Edu_AI/api/Edu_AI/tests/chat/test_ai_lecture_session_service.py
git -C D:\Edu_AI_1 commit -m "Add AI lecture session service"
```

---

### Task 3: Expose AI Lecture Session Course Routes

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/courses.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_ai_lecture_session_routes.py`

- [ ] **Step 1: Write route tests**

Create `Edu_AI/api/Edu_AI/tests/chat/test_ai_lecture_session_routes.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import courses as courses_module


class DummyManager:
    def get_course_info(self, course_id: str):
        return {"id": course_id, "title": "计算思维"} if course_id == "course-1" else None


class DummyAiLectureSessionService:
    def __init__(self):
        self.create_calls = []
        self.patch_calls = []
        self.start_calls = []
        self.stop_calls = []

    def create_session(self, *, course_id: str, source_ppt_material_id: str, title: str | None, owner: str):
        self.create_calls.append(
            {
                "course_id": course_id,
                "source_ppt_material_id": source_ppt_material_id,
                "title": title,
                "owner": owner,
            }
        )
        return {
            "material_id": "ai_session_001",
            "material_type": "ai_lecture_session",
            "title": title,
            "content": {"session_snapshot_id": "ai_session_001", "can_continue_interactive": True},
            "generation_state": {"status": "created"},
        }

    def get_session(self, course_id: str, session_id: str):
        return {
            "material": {"material_id": session_id, "material_type": "ai_lecture_session"},
            "snapshot": {"snapshot_id": session_id, "events": []},
            "metadata": {"recording_status": "not_started"},
        }

    def patch_snapshot(self, *, course_id: str, session_id: str, payload: dict):
        self.patch_calls.append({"course_id": course_id, "session_id": session_id, "payload": payload})
        return {"snapshot_id": session_id, "events": payload["events"], "last_position": payload["last_position"]}

    def start_recording(self, course_id: str, session_id: str, *, livetalking_session_id: int):
        self.start_calls.append({"course_id": course_id, "session_id": session_id, "livetalking_session_id": livetalking_session_id})
        return {"recording_status": "recording"}

    def stop_recording(self, course_id: str, session_id: str, *, livetalking_session_id: int):
        self.stop_calls.append({"course_id": course_id, "session_id": session_id, "livetalking_session_id": livetalking_session_id})
        return {"recording_status": "completed", "recording_url": "/recording.mp4"}


def _client(service: DummyAiLectureSessionService) -> TestClient:
    app = FastAPI()
    app.include_router(courses_module.router)
    app.dependency_overrides[courses_module.get_current_user] = lambda: {"username": "teacher-a"}
    courses_module.get_ai_lecture_session_service = lambda: service
    courses_module._get_manager = lambda: DummyManager()
    return TestClient(app)


def test_ai_lecture_session_routes_create_get_patch_and_record():
    service = DummyAiLectureSessionService()
    client = _client(service)

    created = client.post(
        "/api/courses/course-1/lecture-sessions",
        json={"source_ppt_material_id": "ppt-ready", "title": "AI 实时讲解"},
    )
    fetched = client.get("/api/courses/course-1/lecture-sessions/ai_session_001")
    patched = client.patch(
        "/api/courses/course-1/lecture-sessions/ai_session_001/snapshot",
        json={
            "events": [{"type": "speak", "text": "第一句"}],
            "last_position": {"page_index": 0, "sentence_index": 0},
        },
    )
    started = client.post(
        "/api/courses/course-1/lecture-sessions/ai_session_001/recording/start",
        json={"livetalking_session_id": 123456},
    )
    stopped = client.post(
        "/api/courses/course-1/lecture-sessions/ai_session_001/recording/stop",
        json={"livetalking_session_id": 123456},
    )

    assert created.status_code == 200
    assert created.json()["material_type"] == "ai_lecture_session"
    assert service.create_calls[0]["owner"] == "teacher-a"
    assert fetched.status_code == 200
    assert fetched.json()["snapshot"]["snapshot_id"] == "ai_session_001"
    assert patched.status_code == 200
    assert patched.json()["events"][0]["type"] == "speak"
    assert started.json()["recording_status"] == "recording"
    assert stopped.json()["recording_status"] == "completed"
```

- [ ] **Step 2: Run route test to verify it fails**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_ai_lecture_session_routes.py -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: FAIL because routes are missing.

- [ ] **Step 3: Add imports and route handlers**

In `Edu_AI/api/Edu_AI/app/courses.py`, add imports:

```python
from fastapi.responses import FileResponse
from app.ai_lecture_sessions import (
    AiLectureRecordingRequest,
    CreateAiLectureSessionRequest,
    PatchAiLectureSessionSnapshotRequest,
    get_ai_lecture_session_service,
)
```

Add route handlers after the teaching-video routes:

```python
@router.post("/{course_id}/lecture-sessions", summary="Create an AI lecture session resource")
def create_ai_lecture_session(
    course_id: str,
    payload: CreateAiLectureSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    return get_ai_lecture_session_service().create_session(
        course_id=course_id,
        source_ppt_material_id=payload.source_ppt_material_id,
        title=payload.title,
        owner=str(current_user.get("username") or "").strip(),
    )


@router.get("/{course_id}/lecture-sessions/{session_id}", summary="Get an AI lecture session")
def get_ai_lecture_session(
    course_id: str,
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().get_session(course_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{course_id}/lecture-sessions/{session_id}/snapshot", summary="Patch an AI lecture session snapshot")
def patch_ai_lecture_session_snapshot(
    course_id: str,
    session_id: str,
    payload: PatchAiLectureSessionSnapshotRequest,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().patch_snapshot(
            course_id=course_id,
            session_id=session_id,
            payload=payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{course_id}/lecture-sessions/{session_id}/recording/start", summary="Start AI lecture recording")
def start_ai_lecture_session_recording(
    course_id: str,
    session_id: str,
    payload: AiLectureRecordingRequest,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().start_recording(
            course_id,
            session_id,
            livetalking_session_id=payload.livetalking_session_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{course_id}/lecture-sessions/{session_id}/recording/stop", summary="Stop AI lecture recording")
def stop_ai_lecture_session_recording(
    course_id: str,
    session_id: str,
    payload: AiLectureRecordingRequest,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().stop_recording(
            course_id,
            session_id,
            livetalking_session_id=payload.livetalking_session_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{course_id}/lecture-sessions/{session_id}/recording", response_class=FileResponse, summary="Download AI lecture recording")
def get_ai_lecture_session_recording(
    course_id: str,
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        return get_ai_lecture_session_service().recording_response(course_id, session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 4: Run route tests**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_ai_lecture_session_routes.py tests/chat/test_ai_lecture_session_service.py -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git -C D:\Edu_AI_1 add Edu_AI/api/Edu_AI/app/courses.py Edu_AI/api/Edu_AI/tests/chat/test_ai_lecture_session_routes.py
git -C D:\Edu_AI_1 commit -m "Expose AI lecture session routes"
```

---

### Task 4: Make LiveTalking Recording Output Session-Specific

**Files:**
- Create: `Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/server/recording_paths.py`
- Modify: `Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/avatars/base_avatar.py`
- Modify: `Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/server/routes.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_livetalking_recording_paths.py`

- [ ] **Step 1: Write path-contract test**

Create `Edu_AI/api/Edu_AI/tests/chat/test_livetalking_recording_paths.py`:

```python
import importlib.util
from pathlib import Path


def _load_recording_paths_module():
    module_path = (
        Path("D:/Edu_AI_1/Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/server/recording_paths.py")
        .resolve()
    )
    spec = importlib.util.spec_from_file_location("livetalking_recording_paths", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_recording_output_paths_are_session_specific_and_safe():
    module = _load_recording_paths_module()

    paths = module.recording_paths_for_session("123/../456")

    assert paths.video.name == "temp123__..__456.mp4"
    assert paths.audio.name == "temp123__..__456.aac"
    assert paths.final.name == "record_123__..__456.mp4"
    assert "recordings" in str(paths.final)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_livetalking_recording_paths.py -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: FAIL because helper does not exist.

- [ ] **Step 3: Add recording path helper**

Create `Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/server/recording_paths.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
RECORDINGS_DIR = BASE_DIR / "data" / "recordings"


@dataclass(frozen=True)
class RecordingPaths:
    video: Path
    audio: Path
    final: Path


def safe_session_id(sessionid) -> str:
    value = str(sessionid or "0").strip() or "0"
    for char in '<>:"\\\\|?*/':
        value = value.replace(char, "__")
    return value


def recording_paths_for_session(sessionid) -> RecordingPaths:
    safe_id = safe_session_id(sessionid)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return RecordingPaths(
        video=RECORDINGS_DIR / f"temp{safe_id}.mp4",
        audio=RECORDINGS_DIR / f"temp{safe_id}.aac",
        final=RECORDINGS_DIR / f"record_{safe_id}.mp4",
    )
```

- [ ] **Step 4: Update BaseAvatar recording methods**

In `base_avatar.py`, import:

```python
from server.recording_paths import recording_paths_for_session
```

In `start_recording`, replace `temp{self.opt.sessionid}.mp4` and `temp{self.opt.sessionid}.aac` with:

```python
paths = recording_paths_for_session(self.opt.sessionid)
self._recording_paths = paths
```

Use `str(paths.video)` as the ffmpeg video output and `str(paths.audio)` as the ffmpeg audio output.

In `stop_recording`, replace the fixed combine command with:

```python
paths = getattr(self, "_recording_paths", recording_paths_for_session(self.opt.sessionid))
cmd_combine_audio = f'ffmpeg -y -i "{paths.audio}" -i "{paths.video}" -c:v copy -c:a copy "{paths.final}"'
os.system(cmd_combine_audio)
return str(paths.final)
```

- [ ] **Step 5: Update `/record` route response**

In `server/routes.py`, change the `record` handler branch:

```python
        recording_path = None
        if params['type'] == 'start_record':
            avatar_session.start_recording()
        elif params['type'] == 'end_record':
            recording_path = avatar_session.stop_recording()
        return json_ok(data={"recording_path": recording_path})
```

- [ ] **Step 6: Run path test**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_livetalking_recording_paths.py -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git -C D:\Edu_AI_1 add Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/server/recording_paths.py Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/avatars/base_avatar.py Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/server/routes.py Edu_AI/api/Edu_AI/tests/chat/test_livetalking_recording_paths.py
git -C D:\Edu_AI_1 commit -m "Make LiveTalking recordings session specific"
```

---

### Task 5: Add Frontend AI Lecture Session API Contracts

**Files:**
- Modify: `Edu_AI/src/stitch/api/types.ts`
- Modify: `Edu_AI/src/stitch/api/video.ts`
- Create: `Edu_AI/tests/frontend/aiLecturerApi.session.test.ts`

- [ ] **Step 1: Write static API test**

Create `Edu_AI/tests/frontend/aiLecturerApi.session.test.ts`:

```typescript
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const types = readFileSync(new URL('../../src/stitch/api/types.ts', import.meta.url), 'utf8');
const api = readFileSync(new URL('../../src/stitch/api/video.ts', import.meta.url), 'utf8');

assert.match(types, /export type AiLectureSessionMaterial/, 'types should export AiLectureSessionMaterial');
assert.match(types, /export type AiLectureSessionSnapshot/, 'types should export AiLectureSessionSnapshot');
assert.match(types, /export type AiLecturerOfferAnswer/, 'types should export AiLecturerOfferAnswer');

assert.match(api, /export function getAiLecturerOfferUrl/, 'video API should expose the LiveTalking offer URL');
assert.match(api, /VITE_AI_LECTURER_LIVETALKING_URL/, 'offer URL should be configurable separately from the gateway');
assert.match(api, /export function createAiLectureSession/, 'video API should create AI lecture sessions');
assert.match(api, /\/api\/courses\/\$\{courseId\}\/lecture-sessions`/, 'create call should use lecture-sessions endpoint');
assert.match(api, /export function getAiLectureSession/, 'video API should load AI lecture session details');
assert.match(api, /export function patchAiLectureSessionSnapshot/, 'video API should patch session snapshots');
assert.match(api, /export function startAiLectureSessionRecording/, 'video API should start recording');
assert.match(api, /export function stopAiLectureSessionRecording/, 'video API should stop recording');

console.log('aiLecturerApi.session tests passed');
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/aiLecturerApi.session.test.ts
```

Expected: FAIL because types and functions do not exist.

- [ ] **Step 3: Add frontend types**

Append to `Edu_AI/src/stitch/api/types.ts`:

```typescript
export type AiLectureSessionSnapshotEvent = {
  type: "speak" | "interrupt_question" | "interrupt_answer";
  page_index?: number;
  sentence_index?: number;
  text?: string;
  question?: string;
  answer?: string;
  timestamp_ms?: number;
};

export type AiLectureSessionSnapshot = {
  snapshot_id: string;
  course_id: string;
  source_ppt_material_id: string;
  ai_lecturer_course_id?: string | null;
  outline: AiLecturerCoursePage[];
  script: Array<{ page_index: number; sentences: string[] }>;
  events: AiLectureSessionSnapshotEvent[];
  last_position: { page_index: number; sentence_index: number };
};

export type AiLectureSessionMaterial = CourseMaterial & {
  material_type: "ai_lecture_session";
  content?: {
    source_ppt_material_id?: string;
    session_snapshot_id?: string;
    recording_asset_id?: string | null;
    recording_url?: string | null;
    can_continue_interactive?: boolean;
  };
  generation_state?: {
    status?: string;
    phase?: string;
    message?: string;
  };
};

export type AiLectureSessionDetail = {
  material: AiLectureSessionMaterial;
  snapshot: AiLectureSessionSnapshot;
  metadata: {
    recording_status?: string;
    recording_url?: string | null;
    livetalking_session_id?: number;
  };
};

export type AiLecturerOfferAnswer = {
  sdp: string;
  type: RTCSdpType;
  sessionid: number;
};
```

- [ ] **Step 4: Add frontend API functions**

In `Edu_AI/src/stitch/api/video.ts`, import the new types and add:

```typescript
const AI_LECTURER_LIVETALKING_URL = (import.meta.env.VITE_AI_LECTURER_LIVETALKING_URL || "http://127.0.0.1:8010").replace(/\/$/, "");

export function getAiLecturerOfferUrl() {
  return `${AI_LECTURER_LIVETALKING_URL}/offer`;
}

export function createAiLectureSession(courseId: string, payload: { source_ppt_material_id: string; title?: string }) {
  return apiRequest<AiLectureSessionMaterial>(`/api/courses/${courseId}/lecture-sessions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAiLectureSession(courseId: string, sessionId: string) {
  return apiRequest<AiLectureSessionDetail>(`/api/courses/${courseId}/lecture-sessions/${sessionId}`);
}

export function patchAiLectureSessionSnapshot(
  courseId: string,
  sessionId: string,
  payload: Partial<AiLectureSessionSnapshot>,
) {
  return apiRequest<AiLectureSessionSnapshot>(`/api/courses/${courseId}/lecture-sessions/${sessionId}/snapshot`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function startAiLectureSessionRecording(courseId: string, sessionId: string, livetalkingSessionId: number) {
  return apiRequest<Record<string, unknown>>(`/api/courses/${courseId}/lecture-sessions/${sessionId}/recording/start`, {
    method: "POST",
    body: JSON.stringify({ livetalking_session_id: livetalkingSessionId }),
  });
}

export function stopAiLectureSessionRecording(courseId: string, sessionId: string, livetalkingSessionId: number) {
  return apiRequest<Record<string, unknown>>(`/api/courses/${courseId}/lecture-sessions/${sessionId}/recording/stop`, {
    method: "POST",
    body: JSON.stringify({ livetalking_session_id: livetalkingSessionId }),
  });
}
```

- [ ] **Step 5: Run frontend API test**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/aiLecturerApi.session.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git -C D:\Edu_AI_1 add Edu_AI/src/stitch/api/types.ts Edu_AI/src/stitch/api/video.ts Edu_AI/tests/frontend/aiLecturerApi.session.test.ts
git -C D:\Edu_AI_1 commit -m "Add Stitch AI lecture session API"
```

---

### Task 6: Add React WebRTC Hook For LiveTalking

**Files:**
- Create: `Edu_AI/src/stitch/hooks/useAiLecturerWebRtc.ts`
- Create: `Edu_AI/tests/frontend/aiLecturerWebRtcHook.test.ts`

- [ ] **Step 1: Write static hook test**

Create `Edu_AI/tests/frontend/aiLecturerWebRtcHook.test.ts`:

```typescript
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const hook = readFileSync(new URL('../../src/stitch/hooks/useAiLecturerWebRtc.ts', import.meta.url), 'utf8');

assert.match(hook, /new RTCPeerConnection/, 'hook should create RTCPeerConnection');
assert.match(hook, /addTransceiver\("video", \{ direction: "recvonly" \}\)/, 'hook should receive video');
assert.match(hook, /addTransceiver\("audio", \{ direction: "recvonly" \}\)/, 'hook should receive audio');
assert.match(hook, /getAiLecturerOfferUrl\(\)/, 'hook should use configured offer URL');
assert.match(hook, /setSessionId\(answer\.sessionid\)/, 'hook should store returned session id');
assert.match(hook, /videoRef\.current\.srcObject = evt\.streams\[0\]/, 'hook should bind remote video stream');
assert.match(hook, /audioRef\.current\.srcObject = evt\.streams\[0\]/, 'hook should bind remote audio stream');
assert.match(hook, /pc\.close\(\)/, 'hook should close peer connection');

console.log('aiLecturerWebRtcHook tests passed');
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/aiLecturerWebRtcHook.test.ts
```

Expected: FAIL because hook does not exist.

- [ ] **Step 3: Create the hook**

Create `Edu_AI/src/stitch/hooks/useAiLecturerWebRtc.ts`:

```typescript
import { useRef, useState } from "react";
import { getAiLecturerOfferUrl } from "../api/video";
import type { AiLecturerOfferAnswer } from "../api/types";

export type AiLecturerWebRtcStatus = "idle" | "connecting" | "connected" | "failed" | "closed";

export function useAiLecturerWebRtc() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [status, setStatus] = useState<AiLecturerWebRtcStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  async function connect() {
    close();
    setStatus("connecting");
    setError(null);

    const pc = new RTCPeerConnection({ sdpSemantics: "unified-plan" } as RTCConfiguration);
    peerConnectionRef.current = pc;
    pc.addTransceiver("video", { direction: "recvonly" });
    pc.addTransceiver("audio", { direction: "recvonly" });

    pc.addEventListener("track", (evt) => {
      if (evt.track.kind === "video" && videoRef.current) {
        videoRef.current.srcObject = evt.streams[0];
      }
      if (evt.track.kind === "audio" && audioRef.current) {
        audioRef.current.srcObject = evt.streams[0];
      }
    });

    pc.addEventListener("connectionstatechange", () => {
      if (pc.connectionState === "connected") setStatus("connected");
      if (pc.connectionState === "failed") setStatus("failed");
      if (pc.connectionState === "closed") setStatus("closed");
    });

    try {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await waitForIceGathering(pc);
      const response = await fetch(getAiLecturerOfferUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sdp: pc.localDescription?.sdp, type: pc.localDescription?.type }),
      });
      const answer = (await response.json()) as AiLecturerOfferAnswer;
      await pc.setRemoteDescription(answer);
      setSessionId(answer.sessionid);
      setStatus("connected");
      return answer.sessionid;
    } catch (err) {
      setError(err instanceof Error ? err.message : "WebRTC connection failed");
      setStatus("failed");
      pc.close();
      peerConnectionRef.current = null;
      setSessionId(null);
      return null;
    }
  }

  function close() {
    const pc = peerConnectionRef.current;
    if (pc) {
      pc.close();
      peerConnectionRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
    if (audioRef.current) audioRef.current.srcObject = null;
    setSessionId(null);
    setStatus("closed");
  }

  return { videoRef, audioRef, sessionId, status, error, connect, close };
}

function waitForIceGathering(pc: RTCPeerConnection) {
  return new Promise<void>((resolve) => {
    if (pc.iceGatheringState === "complete") {
      resolve();
      return;
    }
    const checkState = () => {
      if (pc.iceGatheringState === "complete") {
        pc.removeEventListener("icegatheringstatechange", checkState);
        resolve();
      }
    };
    pc.addEventListener("icegatheringstatechange", checkState);
  });
}
```

- [ ] **Step 4: Run hook test**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/aiLecturerWebRtcHook.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git -C D:\Edu_AI_1 add Edu_AI/src/stitch/hooks/useAiLecturerWebRtc.ts Edu_AI/tests/frontend/aiLecturerWebRtcHook.test.ts
git -C D:\Edu_AI_1 commit -m "Add AI Lecturer WebRTC hook"
```

---

### Task 7: Wire VideoPlayer To Real Session IDs And Snapshots

**Files:**
- Modify: `Edu_AI/src/stitch/pages/VideoPlayer.tsx`
- Create: `Edu_AI/tests/frontend/stitchVideoPlayer.aiLecturerSession.test.ts`

- [ ] **Step 1: Write VideoPlayer static test**

Create `Edu_AI/tests/frontend/stitchVideoPlayer.aiLecturerSession.test.ts`:

```typescript
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(page, /useAiLecturerWebRtc/, 'VideoPlayer should use the React WebRTC hook');
assert.doesNotMatch(page, /<iframe[\s\S]*webrtcUrl/, 'VideoPlayer should not embed webrtcapi iframe for realtime mode');
assert.doesNotMatch(page, /session_id:\s*0/, 'VideoPlayer should not send hard-coded session_id 0');
assert.doesNotMatch(page, /stopAiLecturerSpeaking\(0\)/, 'VideoPlayer should not stop hard-coded session 0');
assert.match(page, /sessionId == null/, 'VideoPlayer should guard controls until WebRTC session id exists');
assert.match(page, /speakAiLecturerSentence\(\{ text: sentence, session_id: sessionId \}\)/, 'speak should use real session id');
assert.match(page, /stopAiLecturerSpeaking\(sessionId\)/, 'stop should use real session id');
assert.match(page, /session_id: sessionId/, 'interrupt should use real session id');
assert.match(page, /patchAiLectureSessionSnapshot/, 'VideoPlayer should persist session events');
assert.match(page, /startAiLectureSessionRecording/, 'VideoPlayer should start backend recording');
assert.match(page, /stopAiLectureSessionRecording/, 'VideoPlayer should stop backend recording');

console.log('stitchVideoPlayer.aiLecturerSession tests passed');
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/stitchVideoPlayer.aiLecturerSession.test.ts
```

Expected: FAIL because VideoPlayer still uses iframe and hard-coded session id.

- [ ] **Step 3: Import hook and APIs**

In `VideoPlayer.tsx`, remove `getAiLecturerWebRtcUrl` usage and add:

```typescript
import { useAiLecturerWebRtc } from "../hooks/useAiLecturerWebRtc";
import {
  getAiLectureSession,
  patchAiLectureSessionSnapshot,
  startAiLectureSessionRecording,
  stopAiLectureSessionRecording,
} from "../api/video";
```

- [ ] **Step 4: Add route-param parsing**

Add a helper near the top of `VideoPlayer.tsx`:

```typescript
function getVideoRouteParams() {
  const [, query = ""] = window.location.hash.split("?");
  const params = new URLSearchParams(query);
  return {
    courseId: params.get("courseId"),
    materialId: params.get("materialId"),
    snapshotId: params.get("snapshotId"),
  };
}
```

- [ ] **Step 5: Replace iframe state with hook state**

Inside `VideoPlayerPage`, add:

```typescript
const {
  videoRef,
  audioRef,
  sessionId,
  status: webRtcStatus,
  error: webRtcError,
  connect,
  close,
} = useAiLecturerWebRtc();
const [lectureSessionMaterialId, setLectureSessionMaterialId] = useState<string | null>(getVideoRouteParams().materialId);
const [recordingActive, setRecordingActive] = useState(false);
```

Replace online media panel with:

```tsx
{mode === "online" ? (
  <div className="relative aspect-video w-full bg-black">
    <video ref={videoRef} autoPlay playsInline className="h-full w-full object-cover" />
    <audio ref={audioRef} autoPlay />
    <div className="absolute left-4 top-4 rounded-full bg-black/70 px-3 py-2 text-xs font-bold text-white">
      WebRTC: {webRtcStatus}{sessionId ? ` · session ${sessionId}` : ""}
    </div>
    <button
      type="button"
      onClick={() => void connect()}
      className="absolute bottom-4 left-4 rounded-full bg-white px-4 py-2 text-sm font-bold text-slate-900"
    >
      连接实时讲解
    </button>
  </div>
) : offlineVideoUrl ? (
  <video controls className="aspect-video w-full bg-black" src={offlineVideoUrl} />
) : (
  <div className="aspect-video bg-[radial-gradient(circle_at_20%_20%,rgba(96,165,250,0.32),transparent_24%),radial-gradient(circle_at_75%_58%,rgba(14,165,233,0.22),transparent_30%),linear-gradient(135deg,#020617_0%,#0f172a_45%,#1d4ed8_100%)]" />
)}
```

- [ ] **Step 6: Guard speak, stop, interrupt with real session id**

Change handlers:

```typescript
async function handleSpeak(sentence: string) {
  if (sessionId == null) {
    setError("请先连接实时讲解会话");
    return;
  }
  await withBusy("speak", async () => {
    await speakAiLecturerSentence({ text: sentence, session_id: sessionId });
    setCurrentSentence(sentence);
    await persistSessionEvents([{ type: "speak", text: sentence, timestamp_ms: Date.now() }]);
  });
}

async function handleStop() {
  if (sessionId == null) {
    setError("请先连接实时讲解会话");
    return;
  }
  await withBusy("stop", async () => {
    await stopAiLecturerSpeaking(sessionId);
  });
}

async function handleInterruptAsk() {
  if (sessionId == null) {
    setError("请先连接实时讲解会话");
    return;
  }
  if (!studentQuestion.trim()) {
    setError("请输入要打断提问的问题");
    return;
  }
  await withBusy("ask", async () => {
    await persistSessionEvents([{ type: "interrupt_question", question: studentQuestion.trim(), timestamp_ms: Date.now() }]);
    const result = await askAiLecturer({
      question: studentQuestion.trim(),
      slide_context: activeSlide?.content || "",
      interrupted_sentence: currentSentence || "",
      session_id: sessionId,
    });
    setAnswerText(result.answer || "");
    await persistSessionEvents([{ type: "interrupt_answer", answer: result.answer || "", timestamp_ms: Date.now() }]);
  });
}
```

Add helper:

```typescript
async function persistSessionEvents(events: Array<Record<string, unknown>>) {
  if (!lectureSessionMaterialId) return;
  await patchAiLectureSessionSnapshot(course.id, lectureSessionMaterialId, {
    events,
    last_position: { page_index: activeSlideIndex, sentence_index: Math.max(scriptSentences.indexOf(currentSentence), 0) },
  } as never);
}
```

- [ ] **Step 7: Add recording controls**

Add handlers:

```typescript
async function handleStartRecording() {
  if (!lectureSessionMaterialId || sessionId == null) {
    setError("请先打开 AI 讲解资源并连接实时会话");
    return;
  }
  await withBusy("record-start", async () => {
    await startAiLectureSessionRecording(course.id, lectureSessionMaterialId, sessionId);
    setRecordingActive(true);
  });
}

async function handleStopRecording() {
  if (!lectureSessionMaterialId || sessionId == null) {
    setError("请先打开 AI 讲解资源并连接实时会话");
    return;
  }
  await withBusy("record-stop", async () => {
    await stopAiLectureSessionRecording(course.id, lectureSessionMaterialId, sessionId);
    setRecordingActive(false);
  });
}
```

Render two buttons near realtime controls:

```tsx
<button type="button" onClick={() => void handleStartRecording()} disabled={recordingActive || sessionId == null}>
  开始录制
</button>
<button type="button" onClick={() => void handleStopRecording()} disabled={!recordingActive || sessionId == null}>
  结束录制并入库
</button>
```

- [ ] **Step 8: Load existing session snapshot**

Add effect:

```typescript
useEffect(() => {
  const params = getVideoRouteParams();
  if (!params.courseId || !params.materialId) return;
  let cancelled = false;
  async function loadLectureSession() {
    try {
      const detail = await getAiLectureSession(params.courseId!, params.materialId!);
      if (cancelled) return;
      setLectureSessionMaterialId(detail.material.material_id);
      setOutline(detail.snapshot.outline || []);
      setScriptSentences(detail.snapshot.script?.[detail.snapshot.last_position?.page_index || 0]?.sentences || []);
      setActiveSlideIndex(detail.snapshot.last_position?.page_index || 0);
    } catch (err) {
      if (!cancelled) setError(err instanceof Error ? err.message : "AI 讲解会话加载失败");
    }
  }
  void loadLectureSession();
  return () => {
    cancelled = true;
  };
}, []);
```

- [ ] **Step 9: Run VideoPlayer test**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/stitchVideoPlayer.aiLecturerSession.test.ts
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git -C D:\Edu_AI_1 add Edu_AI/src/stitch/pages/VideoPlayer.tsx Edu_AI/tests/frontend/stitchVideoPlayer.aiLecturerSession.test.ts
git -C D:\Edu_AI_1 commit -m "Wire Stitch AI Lecturer to realtime session ids"
```

---

### Task 8: Render AI Lecture Session In Course Resources

**Files:**
- Modify: `Edu_AI/src/stitch/pages/CourseResources.tsx`
- Modify: `Edu_AI/src/stitch/api/courses.ts`
- Create: `Edu_AI/tests/frontend/stitchCourseResources.aiLectureSession.test.ts`

- [ ] **Step 1: Write static resource test**

Create `Edu_AI/tests/frontend/stitchCourseResources.aiLectureSession.test.ts`:

```typescript
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/CourseResources.tsx', import.meta.url), 'utf8');
const api = readFileSync(new URL('../../src/stitch/api/courses.ts', import.meta.url), 'utf8');

assert.match(page, /ai_lecture_session/, 'CourseResources should recognize AI lecture session resources');
assert.match(page, /回看录播|recording_url/, 'CourseResources should expose recording replay');
assert.match(page, /继续互动|session_snapshot_id/, 'CourseResources should expose continue interaction');
assert.match(page, /routeHref\(routes\.video\)/, 'Continue interaction should navigate to video route');
assert.match(page, /snapshotId/, 'Continue interaction should pass snapshot id');
assert.match(page, /recording_url[^]*<video|<video[^]*recording_url/, 'Replay branch should render a video element for recordings');
assert.match(api, /ai_lecture_session/, 'course API helpers should include AI lecture session markdown fallback');

console.log('stitchCourseResources.aiLectureSession tests passed');
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/stitchCourseResources.aiLectureSession.test.ts
```

Expected: FAIL because CourseResources does not render `ai_lecture_session`.

- [ ] **Step 3: Update type labels and helper**

In `CourseResources.tsx`, add:

```typescript
ai_lecture_session: "AI 讲解会话",
```

In `courses.ts`, update `courseMaterialToMarkdown` before the default return:

```typescript
if (material.material_type === "ai_lecture_session") {
  const content = material.content && typeof material.content === "object" ? material.content as Record<string, unknown> : {};
  return [
    `# ${material.title || "AI 讲解会话"}`,
    "",
    material.summary || "该资源包含录播回看和继续互动入口。",
    "",
    `- 来源 PPT: ${content.source_ppt_material_id || "--"}`,
    `- 快照 ID: ${content.session_snapshot_id || "--"}`,
    `- 录播状态: ${content.recording_url ? "已生成" : "未生成"}`,
  ].join("\n");
}
```

- [ ] **Step 4: Add detail renderer**

In `CourseResources.tsx`, add helper inside the component:

```typescript
function renderAiLectureSessionDetail(material: CourseMaterial) {
  const content = material.content && typeof material.content === "object" ? material.content as Record<string, unknown> : {};
  const recordingUrl = typeof content.recording_url === "string" ? content.recording_url : "";
  const snapshotId = typeof content.session_snapshot_id === "string" ? content.session_snapshot_id : "";
  const continueUrl = `${routeHref(routes.video)}?courseId=${encodeURIComponent(course.id)}&materialId=${encodeURIComponent(material.material_id)}&snapshotId=${encodeURIComponent(snapshotId)}`;

  return (
    <div className="space-y-5">
      {recordingUrl ? (
        <video controls preload="metadata" className="aspect-video w-full rounded-[24px] bg-black" src={recordingUrl} />
      ) : (
        <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-6 text-sm text-[var(--muted-text)]">
          录播还没有生成，可以进入实时讲解继续互动。
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        {recordingUrl ? (
          <a href={recordingUrl} target="_blank" rel="noreferrer" className="rounded-full border border-[var(--shell-border)] bg-white px-5 py-3 text-sm font-bold text-[var(--accent-strong)]">
            回看录播
          </a>
        ) : null}
        {snapshotId ? (
          <a href={continueUrl} className="rounded-full bg-[var(--accent)] px-5 py-3 text-sm font-bold text-white">
            继续互动
          </a>
        ) : null}
      </div>
      <MarkdownPreview content={courseMaterialToMarkdown(material)} />
    </div>
  );
}
```

Replace the detail body:

```tsx
<div className="mt-6 max-h-[calc(100vh-220px)] overflow-y-auto pr-2">
  {activeMaterial.material_type === "ai_lecture_session"
    ? renderAiLectureSessionDetail(activeMaterial)
    : <MarkdownPreview content={markdown} />}
</div>
```

- [ ] **Step 5: Run resource test**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/stitchCourseResources.aiLectureSession.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git -C D:\Edu_AI_1 add Edu_AI/src/stitch/pages/CourseResources.tsx Edu_AI/src/stitch/api/courses.ts Edu_AI/tests/frontend/stitchCourseResources.aiLectureSession.test.ts
git -C D:\Edu_AI_1 commit -m "Render AI lecture sessions in course resources"
```

---

### Task 9: Add Workbench Entry Path For AI Lecture Sessions

**Files:**
- Modify: `Edu_AI/src/services/teacher/api.ts`
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx`
- Modify: `Edu_AI/tests/frontend/teacherApi.teaching-video.test.ts`
- Modify: `Edu_AI/tests/frontend/studioPanel.teaching-video-entry.test.ts`

- [ ] **Step 1: Extend teacher API static test**

Append to `teacherApi.teaching-video.test.ts`:

```typescript
assert.match(api, /export interface AiLectureSessionResponse/, 'Teacher API should export AI lecture session response type');
assert.match(api, /export const createAiLectureSession = async\s*\(/, 'Teacher API should create AI lecture sessions');
assert.match(api, /\/lecture-sessions`/, 'Teacher API should call lecture-sessions endpoint');
```

- [ ] **Step 2: Extend StudioPanel static test**

Append to `studioPanel.teaching-video-entry.test.ts`:

```typescript
assert.match(
  studioPanel,
  /createAiLectureSession\(/,
  'StudioPanel should create AI lecture session resources for realtime teaching videos',
);
assert.match(
  studioPanel,
  /ai_lecture_session/,
  'StudioPanel should treat realtime teaching output as AI lecture session material',
);
assert.match(
  studioPanel,
  /#resources\?courseId=/,
  'StudioPanel should jump completed AI lecture sessions to course resources',
);
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/teacherApi.teaching-video.test.ts tests/frontend/studioPanel.teaching-video-entry.test.ts
```

Expected: FAIL because teacher API and StudioPanel still use teaching-video task semantics only.

- [ ] **Step 4: Add teacher API wrapper**

In `Edu_AI/src/services/teacher/api.ts`, add:

```typescript
export interface AiLectureSessionResponse {
  material_id: string;
  material_type: "ai_lecture_session";
  title?: string;
  content?: {
    source_ppt_material_id?: string;
    session_snapshot_id?: string;
    recording_url?: string | null;
    can_continue_interactive?: boolean;
  };
  generation_state?: {
    status?: string;
    phase?: string;
    message?: string;
  };
}

export const createAiLectureSession = async (
  courseId: string,
  payload: { source_ppt_material_id: string; title?: string },
): Promise<AiLectureSessionResponse> => {
  return apiRequest<AiLectureSessionResponse>(`/api/courses/${courseId}/lecture-sessions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
};
```

- [ ] **Step 5: Update StudioPanel submit path**

In `StudioPanel.tsx`, import `createAiLectureSession`. In the teaching video submit handler, create the AI lecture session resource instead of treating the output as a completed `video` preview:

```typescript
const created = await createAiLectureSession(activeCourseId, {
  source_ppt_material_id: selectedPpt.material_id,
  title: `${selectedPpt.title || "PPT"} - AI 实时讲解`,
});

const nextFile = {
  id: created.material_id,
  name: created.title || "AI 实时讲解",
  type: "ai_lecture_session",
  meta: {
    courseId: activeCourseId,
    materialId: created.material_id,
    sessionSnapshotId: created.content?.session_snapshot_id,
    generationState: created.generation_state,
    origin: "course_material",
  },
};
```

For completed click behavior:

```typescript
if (item.type === "ai_lecture_session") {
  const courseId = item.meta?.courseId || activeCourseId;
  const materialId = item.meta?.materialId || item.id;
  window.location.hash = `#resources?courseId=${encodeURIComponent(courseId)}&materialId=${encodeURIComponent(materialId)}`;
  return;
}
```

- [ ] **Step 6: Run workbench tests**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/teacherApi.teaching-video.test.ts tests/frontend/studioPanel.teaching-video-entry.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git -C D:\Edu_AI_1 add Edu_AI/src/services/teacher/api.ts Edu_AI/src/components/teacher/StudioPanel.tsx Edu_AI/tests/frontend/teacherApi.teaching-video.test.ts Edu_AI/tests/frontend/studioPanel.teaching-video-entry.test.ts
git -C D:\Edu_AI_1 commit -m "Create AI lecture sessions from workbench"
```

---

### Task 10: Full Verification

**Files:**
- No code files expected.

- [ ] **Step 1: Run backend lecture-session tests**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_ai_lecture_session_service.py tests/chat/test_ai_lecture_session_routes.py tests/chat/test_livetalking_recording_paths.py -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: all tests PASS.

- [ ] **Step 2: Run existing teaching-video regression tests**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI\api\Edu_AI
python -m pytest tests/chat/test_teaching_video_bridge.py tests/chat/test_teaching_video_routes.py -q -o cache_dir=D:\Edu_AI_1\tmp\pytest_cache
```

Expected: all tests PASS.

- [ ] **Step 3: Run frontend session tests**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/aiLecturerApi.session.test.ts tests/frontend/aiLecturerWebRtcHook.test.ts tests/frontend/stitchVideoPlayer.aiLecturerSession.test.ts tests/frontend/stitchCourseResources.aiLectureSession.test.ts
```

Expected: all tests PASS.

- [ ] **Step 4: Run workbench regression tests**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
node --test tests/frontend/teacherApi.teaching-video.test.ts tests/frontend/studioPanel.teaching-video-entry.test.ts tests/frontend/materials.helpers.test.ts
```

Expected: all tests PASS.

- [ ] **Step 5: Run frontend build**

Run:

```powershell
cd D:\Edu_AI_1\Edu_AI
npm run build
```

Expected: build completes without TypeScript or bundling errors.

- [ ] **Step 6: Inspect changed files**

Run:

```powershell
git -C D:\Edu_AI_1 status --short
git -C D:\Edu_AI_1 diff --stat
```

Expected: only files touched by this plan are modified.

- [ ] **Step 7: Commit verification cleanup if any**

If verification required small test or type fixes, commit them:

```powershell
git -C D:\Edu_AI_1 add Edu_AI/api/Edu_AI Edu_AI/src Edu_AI/tests/frontend
git -C D:\Edu_AI_1 commit -m "Verify AI lecture session resource flow"
```

---

## Self-Review

Spec coverage:

- Realtime WebRTC instead of mp4-only playback: covered by Tasks 6 and 7.
- Real `sessionid` drives speak, stop, and interrupt: covered by Task 7.
- Course resource stores dual replay and continue-interaction entries: covered by Tasks 2, 3, and 8.
- Recording output is unique and persistent: covered by Tasks 2 and 4.
- Workbench entry path: covered by Task 9.
- Backend route and persistence tests: covered by Tasks 1, 2, 3, and 10.
- Frontend contract tests: covered by Tasks 5, 6, 7, 8, 9, and 10.

Placeholder scan:

- No unresolved placeholder sections are present.
- Every task includes explicit files, test command, implementation target, and commit command.

Type consistency:

- Backend material type is consistently `ai_lecture_session`.
- Snapshot id, material id, and session id use the same persisted `material_id` for course-resource identity.
- LiveTalking realtime `sessionid` remains separate as `livetalking_session_id`.
