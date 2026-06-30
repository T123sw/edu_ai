# AI Lecturer 远程素材传输实施计划

> **给执行型 Agent 的要求：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按任务逐项执行。步骤使用复选框（`- [ ]`）格式，方便追踪进度。

**目标：** 让 `AI_Lecturer` 可以独立运行在 GPU 服务器上，同时主 Edu-AI 后端通过网络上传幻灯片图片，不再把本机绝对路径传给远程服务。

**架构：** 保持 `AI_Lecturer` 作为独立远程服务，对外暴露 `8008` 网关端口和 `8010` LiveTalking 端口。主后端用 `multipart/form-data` 把 PPT 幻灯片图片直接上传到 `AI_Lecturer` 网关；`AI_Lecturer` 在自己的任务工作区中保存这些图片，然后用相对任务路径调用现有离线视频生成流水线。这样 GPU 服务器不需要访问外网，也不再依赖主后端机器上的 `D:\...` 绝对路径。

**技术栈：** FastAPI、Pydantic、httpx、requests、Python pathlib、pytest、FastAPI TestClient。

---

## 当前实施状态

- 已完成：Task 1 到 Task 4 的代码实现与测试覆盖。
- 已完成：`AI_Lecturer` 新增 multipart 上传接口 `/api/v1/offline/generate_full_video_upload`。
- 已完成：主后端新增 `create_offline_video_upload()`，默认通过 `AI_LECTURER_TRANSFER_MODE=upload` 使用上传模式。
- 已验证：`python -m py_compile modules\AI_Lecturer\unified_gateway.py app\teaching_video_bridge.py core\config.py` 通过。
- 已验证：`pytest tests/chat/test_ai_lecturer_remote_upload.py tests/chat/test_teaching_video_bridge.py -v` 共 8 个测试通过。
- 待执行：Task 6 的真实 GPU 服务器部署、端口连通性检查和端到端教学视频任务联调。

---

## 当前行为

- 主后端在 `Edu_AI/api/src/app/teaching_video_bridge.py` 的 `TeachingVideoBridgeService._build_pages()` 中本地导出 PPT 图片。
- 主后端现在把每一页图片按本机绝对路径发给 `AI_Lecturer`：

```json
{
  "ppt_image_path": "D:\\Edu_AI_1\\Edu_AI\\api\\storage\\temp\\teaching_videos\\...\\slide-001.png",
  "content_text": "第一页讲稿提示"
}
```

- `AI_Lecturer` 在 `Edu_AI/api/src/modules/AI_Lecturer/unified_gateway.py` 的 `SlidePage.ppt_image_path` 中接收该路径。
- `AI_Lecturer` 再通过 `background_full_course_worker()` 把这个路径传给 `offline_video_maker.build_course_video()`。
- 这种方式只适合主后端和 `AI_Lecturer` 在同一台机器上运行，或者两台机器挂载了完全一致的共享文件系统。

## 目标行为

- 主后端仍然像现在一样在本地导出 slide 图片。
- 主后端向远程 `AI_Lecturer` 提交 multipart 请求：
  - `metadata`：JSON 字符串，包含 `course_title` 和有序页面元数据。
  - `files`：有序上传的 slide 图片文件。
- `AI_Lecturer` 为每个任务创建自己的工作区：

```text
temp_export/
  tasks/
    course_ab12cd34/
      slides/
        slide-001.png
        slide-002.png
      output.mp4
```

- `AI_Lecturer` 把上传元数据转换为现有内部 `pages_data`：

```python
[
    {
        "ppt_image": "temp_export/tasks/course_ab12cd34/slides/slide-001.png",
        "outline_prompt": "第一页讲稿提示",
    }
]
```

- `offline_video_maker.build_course_video()` 可以继续接收本地文件路径，但这些路径必须是 GPU 服务器本机的任务路径，而不是调用方机器上的绝对路径。
- 旧 JSON 路径接口暂时保留，用于本地开发兼容。

## 涉及文件

- 修改：`Edu_AI/api/src/modules/AI_Lecturer/unified_gateway.py`
  - 新增 multipart 上传接口。
  - 新增任务工作区创建逻辑。
  - 保存上传图片到 GPU 服务器本地。
  - 保留现有 `/api/v1/offline/generate_full_video` 接口。
- 修改：`Edu_AI/api/src/app/teaching_video_bridge.py`
  - 给 `AiLecturerGatewayClient` 新增上传模式方法。
  - 让 `TeachingVideoBridgeService.create_task()` 使用上传图片，而不是传远程无法读取的绝对路径。
- 修改：`Edu_AI/api/src/core/config.py`
  - 新增迁移开关：`AI_LECTURER_TRANSFER_MODE=upload`。
- 修改：`Edu_AI/api/src/.env.production.example`
  - 补充远程 GPU 部署配置。
- 新增测试：`Edu_AI/api/src/tests/chat/test_ai_lecturer_remote_upload.py`
  - 验证网关可以接收 multipart 图片上传，并保存为任务素材。
- 修改测试：`Edu_AI/api/src/tests/chat/test_teaching_video_bridge.py`
  - 验证主后端在 upload 模式下发送文件，而不是发送绝对路径。

---

### Task 1：锁定网络协议

**文件：**
- 修改：`Edu_AI/api/src/modules/AI_Lecturer/unified_gateway.py`
- 新增测试：`Edu_AI/api/src/tests/chat/test_ai_lecturer_remote_upload.py`

- [ ] **Step 1：定义 multipart 请求协议**

使用下面的请求格式：

```text
POST /api/v1/offline/generate_full_video_upload
Content-Type: multipart/form-data

metadata:
{
  "course_title": "课程标题",
  "pages": [
    {
      "filename": "slide-001.png",
      "content_text": "第一页讲稿提示"
    },
    {
      "filename": "slide-002.png",
      "content_text": "第二页讲稿提示"
    }
  ]
}

files:
  slide-001.png
  slide-002.png
```

- [ ] **Step 2：新增一个先失败的网关测试**

创建 `Edu_AI/api/src/tests/chat/test_ai_lecturer_remote_upload.py`：

```python
from fastapi.testclient import TestClient


def test_offline_upload_endpoint_accepts_slide_files(monkeypatch, tmp_path):
    from modules.AI_Lecturer import unified_gateway

    calls = []

    def fake_build_course_video(course_title, pages_data, final_output_filename):
        calls.append(
            {
                "course_title": course_title,
                "pages_data": pages_data,
                "final_output_filename": final_output_filename,
            }
        )
        output_path = tmp_path / "fake-output.mp4"
        output_path.write_bytes(b"fake mp4")

    monkeypatch.setattr(unified_gateway, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(unified_gateway, "build_course_video", fake_build_course_video)

    client = TestClient(unified_gateway.app)
    response = client.post(
        "/api/v1/offline/generate_full_video_upload",
        data={
            "metadata": (
                '{"course_title":"远程课程","pages":['
                '{"filename":"slide-001.png","content_text":"第一页"},'
                '{"filename":"slide-002.png","content_text":"第二页"}'
                "]}"
            )
        },
        files=[
            ("files", ("slide-001.png", b"png-1", "image/png")),
            ("files", ("slide-002.png", b"png-2", "image/png")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"].startswith("course_")
    assert unified_gateway.OFFLINE_TASK_DB[payload["task_id"]]["status"] == "processing"
```

- [ ] **Step 3：运行测试，确认它先失败**

运行：

```bash
cd Edu_AI/api/src
pytest tests/chat/test_ai_lecturer_remote_upload.py -v
```

预期：失败，状态码为 404，因为上传接口还没有实现。

---

### Task 2：新增 AI_Lecturer 上传接口

**文件：**
- 修改：`Edu_AI/api/src/modules/AI_Lecturer/unified_gateway.py`
- 测试：`Edu_AI/api/src/tests/chat/test_ai_lecturer_remote_upload.py`

- [ ] **Step 1：新增上传模型和辅助函数**

在现有离线视频模型附近加入：

```python
from fastapi import File, Form, UploadFile
from pathlib import Path


class UploadedSlidePage(BaseModel):
    filename: str = Field(..., description="上传的幻灯片图片文件名")
    content_text: str = Field(..., description="该页讲稿提示词")


class UploadedFullCourseVideoMetadata(BaseModel):
    course_title: str = Field(..., description="课程标题")
    pages: List[UploadedSlidePage] = Field(..., description="有序页面元数据")


def _safe_upload_filename(value: str, index: int) -> str:
    suffix = Path(value or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = ".png"
    return f"slide-{index + 1:03d}{suffix}"


def _task_workspace(task_id: str) -> Path:
    root = Path(TEMP_DIR).resolve() / "tasks" / task_id
    root.mkdir(parents=True, exist_ok=True)
    return root
```

- [ ] **Step 2：新增上传任务 worker**

```python
def background_uploaded_course_worker(
    task_id: str,
    metadata: UploadedFullCourseVideoMetadata,
    slide_paths: list[Path],
):
    workspace = _task_workspace(task_id)
    output_filename = workspace / "output.mp4"
    try:
        pages_data = [
            {
                "ppt_image": str(slide_path),
                "outline_prompt": metadata.pages[index].content_text,
            }
            for index, slide_path in enumerate(slide_paths)
        ]
        build_course_video(metadata.course_title, pages_data, str(output_filename))
        final_filename = f"{task_id}.mp4"
        final_path = Path(TEMP_DIR).resolve() / final_filename
        final_path.write_bytes(output_filename.read_bytes())
        OFFLINE_TASK_DB[task_id] = {
            "status": "success",
            "video_url": f"/api/v1/offline/download/{final_filename}",
        }
    except Exception as exc:
        OFFLINE_TASK_DB[task_id] = {"status": "failed", "error": str(exc)}
```

- [ ] **Step 3：新增上传接口**

```python
@app.post("/api/v1/offline/generate_full_video_upload", tags=["离线渲染一键成片"])
async def generate_full_course_video_upload(
    bg_tasks: BackgroundTasks,
    metadata: str = Form(...),
    files: List[UploadFile] = File(...),
):
    if not is_offline_video_enabled():
        raise HTTPException(status_code=503, detail="Offline AI Lecturer video generation is disabled.")

    try:
        parsed = UploadedFullCourseVideoMetadata.model_validate_json(metadata)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid metadata: {exc}") from exc

    if len(parsed.pages) != len(files):
        raise HTTPException(status_code=400, detail="metadata.pages count must match uploaded files count")

    task_id = f"course_{uuid.uuid4().hex[:8]}"
    workspace = _task_workspace(task_id)
    slides_dir = workspace / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    slide_paths: list[Path] = []
    for index, upload in enumerate(files):
        filename = _safe_upload_filename(parsed.pages[index].filename or upload.filename or "", index)
        target = slides_dir / filename
        target.write_bytes(await upload.read())
        slide_paths.append(target)

    OFFLINE_TASK_DB[task_id] = {"status": "processing"}
    bg_tasks.add_task(background_uploaded_course_worker, task_id, parsed, slide_paths)
    return {"code": 200, "message": "教学视频任务已通过文件上传加入队列", "task_id": task_id}
```

- [ ] **Step 4：运行网关测试**

运行：

```bash
cd Edu_AI/api/src
pytest tests/chat/test_ai_lecturer_remote_upload.py -v
```

预期：通过。

---

### Task 3：给主后端新增上传客户端

**文件：**
- 修改：`Edu_AI/api/src/app/teaching_video_bridge.py`
- 修改测试：`Edu_AI/api/src/tests/chat/test_teaching_video_bridge.py`

- [ ] **Step 1：新增一个先失败的客户端测试**

加入测试，验证 `AI_Lecturer` 客户端发送 multipart 文件：

```python
def test_ai_lecturer_client_uploads_slide_files(monkeypatch, tmp_path):
    from app.teaching_video_bridge import AiLecturerGatewayClient

    slide = tmp_path / "slide-001.png"
    slide.write_bytes(b"fake png")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"task_id": "course_task_001", "status": "processing"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, path, data=None, files=None):
            captured["path"] = path
            captured["data"] = data
            captured["files"] = files
            return FakeResponse()

    monkeypatch.setattr("app.teaching_video_bridge.httpx.Client", FakeClient)

    client = AiLecturerGatewayClient(base_url="http://gpu-server:8008")
    result = client.create_offline_video_upload(
        course_title="远程课程",
        pages=[{"ppt_image_path": str(slide), "content_text": "第一页"}],
    )

    assert result["task_id"] == "course_task_001"
    assert captured["path"] == "/api/v1/offline/generate_full_video_upload"
    assert "metadata" in captured["data"]
    assert captured["files"][0][0] == "files"
```

- [ ] **Step 2：新增 `create_offline_video_upload()`**

在 `AiLecturerGatewayClient` 中加入：

```python
def create_offline_video_upload(self, *, course_title: str, pages: list[dict[str, str]]) -> dict[str, Any]:
    metadata_pages = []
    file_handles = []
    files = []
    try:
        for index, page in enumerate(pages):
            image_path = Path(str(page.get("ppt_image_path") or "")).resolve()
            filename = f"slide-{index + 1:03d}{image_path.suffix or '.png'}"
            metadata_pages.append(
                {
                    "filename": filename,
                    "content_text": str(page.get("content_text") or "").strip(),
                }
            )
            handle = image_path.open("rb")
            file_handles.append(handle)
            files.append(("files", (filename, handle, "image/png")))

        metadata = {
            "course_title": str(course_title or "").strip() or "教学视频",
            "pages": metadata_pages,
        }
        with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds, trust_env=False) as client:
            response = client.post(
                "/api/v1/offline/generate_full_video_upload",
                data={"metadata": json.dumps(metadata, ensure_ascii=False)},
                files=files,
            )
            response.raise_for_status()
            data = response.json()
    finally:
        for handle in file_handles:
            handle.close()

    task_id = str(data.get("task_id") or ((data.get("data") or {}).get("task_id")) or "").strip()
    video_url = str(data.get("video_url") or ((data.get("data") or {}).get("video_url")) or "").strip()
    return {
        "task_id": task_id,
        "status": str(data.get("status") or "processing").strip() or "processing",
        "video_url": _join_url(self.base_url, video_url) if video_url else "",
        "raw": data,
    }
```

同时在 `teaching_video_bridge.py` 顶部加入：

```python
import json
```

- [ ] **Step 3：运行客户端测试**

运行：

```bash
cd Edu_AI/api/src
pytest tests/chat/test_teaching_video_bridge.py::test_ai_lecturer_client_uploads_slide_files -v
```

预期：通过。

---

### Task 4：把教学视频创建切到上传模式

**文件：**
- 修改：`Edu_AI/api/src/core/config.py`
- 修改：`Edu_AI/api/src/app/teaching_video_bridge.py`
- 测试：`Edu_AI/api/src/tests/chat/test_teaching_video_bridge.py`

- [ ] **Step 1：新增配置开关**

在 `Config` 中加入：

```python
AI_LECTURER_TRANSFER_MODE = os.getenv("AI_LECTURER_TRANSFER_MODE", "upload").strip().lower()
```

- [ ] **Step 2：切换 `create_task()` 的调用方式**

在 `TeachingVideoBridgeService.create_task()` 中，把：

```python
task = self.ai_lecturer_client.create_offline_video(course_title=course_title, pages=pages)
```

替换为：

```python
transfer_mode = str(getattr(Config, "AI_LECTURER_TRANSFER_MODE", "upload")).strip().lower()
if transfer_mode == "path":
    task = self.ai_lecturer_client.create_offline_video(course_title=course_title, pages=pages)
else:
    task = self.ai_lecturer_client.create_offline_video_upload(course_title=course_title, pages=pages)
```

- [ ] **Step 3：验证现有 bridge 测试**

运行：

```bash
cd Edu_AI/api/src
pytest tests/chat/test_teaching_video_bridge.py -v
```

预期：通过。现有使用 fake client 的测试可能需要补充 `create_offline_video_upload()` 方法，或者在测试中覆盖 `AI_LECTURER_TRANSFER_MODE=path`。

---

### Task 5：补充远程 GPU 配置文档

**文件：**
- 修改：`Edu_AI/api/src/.env.production.example`

- [ ] **Step 1：更新 AI Lecturer 部署配置块**

替换 AI Lecturer 配置块为：

```env
# AI Lecturer remote GPU service.
# AI_Lecturer 与主后端不在同一台机器时，必须使用 upload 模式。
AI_LECTURER_AUTOSTART=0
AI_LECTURER_OFFLINE_ENABLED=1
AI_LECTURER_TRANSFER_MODE=upload
AI_LECTURER_GATEWAY_URL=http://your-gpu-server-ip:8008
AI_LECTURER_LIVETALKING_URL=http://your-gpu-server-ip:8010
AI_LECTURER_LIVETALKING_HUMAN_URL=http://your-gpu-server-ip:8010/human
AI_LECTURER_STARTUP_TIMEOUT_SEC=15
```

- [ ] **Step 2：加入本地兼容说明**

添加：

```env
# Local-only compatibility mode.
# 仅当主后端和 AI_Lecturer 共享同一套文件系统时使用。
# AI_LECTURER_TRANSFER_MODE=path
# AI_LECTURER_AUTOSTART=1
```

---

### Task 6：人工迁移检查清单

**文件：**
- 无代码修改。

- [ ] **Step 1：在 GPU 服务器启动 AI_Lecturer**

在 GPU 服务器运行：

```bash
cd Edu_AI/api/src/modules/AI_Lecturer
python start_unified.py
```

预期输出包含：

```text
Starting LiveTalking WebRTC engine on port 8010
Starting AI Lecturer unified gateway on port 8008
```

- [ ] **Step 2：确认主后端机器可以访问 GPU 服务**

在主后端机器运行：

```bash
curl http://your-gpu-server-ip:8008/openapi.json
curl http://your-gpu-server-ip:8010/webrtcapi.html
```

预期：两个命令都返回 HTTP 200。

- [ ] **Step 3：配置主后端**

设置：

```env
AI_LECTURER_AUTOSTART=0
AI_LECTURER_TRANSFER_MODE=upload
AI_LECTURER_GATEWAY_URL=http://your-gpu-server-ip:8008
AI_LECTURER_LIVETALKING_URL=http://your-gpu-server-ip:8010
AI_LECTURER_LIVETALKING_HUMAN_URL=http://your-gpu-server-ip:8010/human
```

- [ ] **Step 4：跑一次端到端教学视频任务**

使用现有 API：

```text
POST /api/courses/{course_id}/teaching-videos
GET  /api/courses/{course_id}/teaching-videos/tasks/{task_id}
```

预期返回：

```json
{
  "status": "completed",
  "video_url": "http://your-gpu-server-ip:8008/api/v1/offline/download/course_xxxxxxxx.mp4"
}
```

---

## 自检

- 本方案不要求 GPU 服务器访问外网，主后端会主动把 slide 图片字节推送到 GPU 服务器。
- 本方案移除了网络协议中的调用方机器绝对路径。
- 旧路径协议仍可通过 `AI_LECTURER_TRANSFER_MODE=path` 保留，方便本地开发兼容。
- 本方案不需要共享存储。
- 最大的剩余部署风险是 `8010` WebRTC 暴露和浏览器连通性；这部分需要在真实服务器网络环境中单独验证。
