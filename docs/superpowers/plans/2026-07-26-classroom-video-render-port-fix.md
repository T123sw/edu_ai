# AI Classroom Video Render Port Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make classroom MP4 export reuse the Edu-AI frontend running on port `5173`.

**Architecture:** Keep the existing Playwright/FFmpeg export pipeline unchanged. Align its backend fallback, environment example, and unified startup environment around the existing `FRONTEND_PORT`, while preserving `CLASSROOM_VIDEO_FRONTEND_URL` as an explicit deployment override.

**Tech Stack:** Python/FastAPI, pytest, Windows batch, Node.js/Playwright, Vite, FFmpeg

---

### Task 1: Lock the unified video render URL with failing tests

**Files:**
- Modify: `Edu_AI/api/src/tests/test_classroom_video_export.py`
- Modify: `Edu_AI/api/src/tests/chat/test_start_api_bat.py`

- [ ] **Step 1: Make the existing export orchestration test exercise the default URL**

In `test_video_job_maps_process_progress_and_persists_artifact_urls`, clear any inherited override, omit the injected `base_url`, and assert the subprocess receives port `5173`:

```python
monkeypatch.delenv("CLASSROOM_VIDEO_FRONTEND_URL", raising=False)

result = await run_classroom_video_export_job(
    job,
    course_id="course-1",
    classroom_id="classroom-1",
    auth_token="secret-token",
    current_user={"username": "teacher"},
    course_storage_manager=manager,
    frontend_root=tmp_path / "frontend",
    node_executable="node-test",
    ffmpeg_path="ffmpeg-test",
)

base_url_index = captured["command"].index("--base-url") + 1
assert captured["command"][base_url_index] == "http://127.0.0.1:5173"
```

- [ ] **Step 2: Add startup and environment consistency tests**

Add:

```python
def test_start_api_bat_routes_video_export_to_frontend_port():
    script = _read(API_ROOT / "start_api.bat")

    assert 'set "frontend_port=5173"' in script
    assert (
        'set "classroom_video_frontend_url=http://127.0.0.1:%frontend_port%"'
        in script
    )


def test_backend_env_example_matches_unified_video_frontend_port():
    env_example = _read(API_ROOT / ".env.example")

    assert "classroom_video_frontend_url=http://127.0.0.1:5173" in env_example
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_classroom_video_export.py tests/chat/test_start_api_bat.py -q
```

Expected: failures show the backend fallback, startup environment, and environment example still use or imply `4173`.

### Task 2: Align the backend and startup configuration

**Files:**
- Modify: `Edu_AI/api/src/app/services/classroom_video_export.py`
- Modify: `Edu_AI/api/src/.env.example`
- Modify: `Edu_AI/api/src/start_api.bat`

- [ ] **Step 1: Change the backend local fallback**

```python
active_base_url = (
    base_url
    or os.getenv("CLASSROOM_VIDEO_FRONTEND_URL", "").strip()
    or "http://127.0.0.1:5173"
)
```

- [ ] **Step 2: Align the environment example**

```dotenv
CLASSROOM_VIDEO_FRONTEND_URL=http://127.0.0.1:5173
```

- [ ] **Step 3: Export the unified URL from the startup script**

Immediately after defining `FRONTEND_PORT`, add:

```bat
set "CLASSROOM_VIDEO_FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%"
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_classroom_video_export.py tests/chat/test_start_api_bat.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Verify the startup script and commit**

Run:

```powershell
cmd.exe /d /c start_api.bat --check
git diff --check
git add Edu_AI/api/src/app/services/classroom_video_export.py Edu_AI/api/src/.env.example Edu_AI/api/src/start_api.bat Edu_AI/api/src/tests/test_classroom_video_export.py Edu_AI/api/src/tests/chat/test_start_api_bat.py
git commit -m "fix(video): align classroom renderer with frontend port"
```

Expected: startup check succeeds and the fix is committed without unrelated files.

### Task 3: Verify the complete export path

**Files:**
- Verify: `Edu_AI/api/course_data/courses/computational-thinking/generated_materials/classrooms/Ii0-7a0bpN_media/video/`

- [ ] **Step 1: Run the backend regression suite**

Run:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_classroom_video_export.py tests/chat/test_start_api_bat.py -q
```

Expected: all selected backend tests pass.

- [ ] **Step 2: Run frontend video tests and the full frontend suite**

Run:

```powershell
node --import tsx --test scripts/videoPipeline.test.ts src/openmaic/videoExportJob.test.ts
npm test
```

Expected: all tests pass.

- [ ] **Step 3: Run lint and production build**

Run:

```powershell
npm run lint
npm run build
```

Expected: lint has no errors and the build exits successfully.

- [ ] **Step 4: Merge the verified fix into `main`**

From the original repository, merge the isolated branch without including the user's existing `Edu_AI/package.json` change:

```powershell
git merge --ff-only fix/classroom-video-render-port
```

Expected: `main` fast-forwards to the tested fix commit and `Edu_AI/package.json` remains modified but uncommitted.

- [ ] **Step 5: Run a real classroom export against port `5173`**

From `Edu_AI/api/src`, run:

```powershell
@'
import asyncio
import json

from core import Config
from core.auth import auth_manager
from app.services import course_service
from app.services.classroom_video_export import run_classroom_video_export_job
from app.services.job_store import JobKind, create_job


async def main():
    user = {"username": "teacher", "role": "teacher"}
    token = auth_manager.create_token(user["username"], user["role"])
    job = create_job(kind=JobKind.RENDER_VIDEO, owner=user["username"])
    result = await run_classroom_video_export_job(
        job,
        course_id="computational-thinking",
        classroom_id="Ii0-7a0bpN",
        auth_token=token,
        current_user=user,
        course_storage_manager=course_service._get_manager(),
    )
    print(json.dumps({
        "job_id": result.edu_job_id,
        "status": result.status.value,
        "error": result.error,
        "result_ref": result.result_ref,
    }, ensure_ascii=False))


asyncio.run(main())
'@ | D:\anaconda\envs\edu-ai\python.exe -
```

Expected final job state: `succeeded`.

- [ ] **Step 6: Verify generated artifacts**

Confirm all files exist and are non-empty:

```text
Ii0-7a0bpN_media/video/classroom.mp4
Ii0-7a0bpN_media/video/classroom.srt
Ii0-7a0bpN_media/video/timeline.json
```

Report their sizes and the final video duration.
