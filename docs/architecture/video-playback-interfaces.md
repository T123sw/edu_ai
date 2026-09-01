# 视频播放前后端接口记录

## 1. 前端调用入口

### 1.1 主前端视频服务
文件：`src/services/video.ts`

- `uploadVideo(params)`
  - 请求：`POST /api/video/upload`
  - Query：
    - `course_id`
    - `window_seconds`
    - `stride_seconds`
  - Body：`multipart/form-data`，字段名 `file`
  - 返回：`VideoUploadResponse`

- `getVideoJobStatus(jobId)`
  - 请求：`GET /api/video/jobs/{job_id}`
  - 返回：`VideoJobStatusResponse`

- `searchVideoSegments(req)`
  - 请求：`POST /api/video/search`
  - Body：
    - `query`
    - `top_k`
    - `course_id`
  - 返回：`VideoSearchResponse`

### 1.2 Stitch / AI Lecturer 视频入口
文件：`src/stitch/api/video.ts`

- `searchVideoSegments(query, courseId?)`
  - 对接：`POST /api/video/search`

- `getAiLecturerVideoUrl(path)`
  - 作用：将 AI Lecturer 返回的视频相对路径拼成可直接播放的完整 URL
  - 规则：
    - 如果传入的是完整 `http/https` 地址，直接返回
    - 如果是相对路径，则拼到 `VITE_AI_LECTURER_BASE_URL`

### 1.3 前端页面中的实际播放位置

- `src/components/teacher/StudioPanel.tsx`
  - 当生成文件类型为 `video` 时，读取 `viewingFile.content.video_url`
  - 用原生 `<video controls src={videoUrl} />` 直接播放

- `src/stitch/pages/VideoPlayer.tsx`
  - 使用 `playbackUrl(url)` 统一兼容三类地址：
    - 完整外链地址
    - `/api/...` 形式的主后端地址
    - AI Lecturer 相对路径
  - 最终也是通过 `<video>` 标签播放

## 2. 后端接口

文件：`backend/src/app/video_routes.py`

### 2.1 视频流播放

- 路径：`GET /api/video/stream`
- 参数：
  - `rel_path`：当前用户视频目录下的相对路径
- Header：
  - 支持 `Range`
- 行为：
  - 无 `Range` 时返回完整流
  - 有 `Range` 时返回 `206 Partial Content`
- 返回：
  - `StreamingResponse`
  - Header 包含：
    - `Accept-Ranges: bytes`
    - `Content-Length`
    - `Content-Range`（分片时）

### 2.2 上传视频并建立检索任务

- 路径：`POST /api/video/upload`
- Query：
  - `course_id`
  - `window_seconds`
  - `stride_seconds`
- Body：
  - `file`
- 鉴权：
  - 依赖 `get_current_user`
- 返回：
  - `job_id`
  - `status`
  - `message`
  - `saved_video_path`

### 2.3 查询视频处理任务状态

- 路径：`GET /api/video/jobs/{job_id}`
- 鉴权：
  - 依赖 `get_current_user`
- 返回：
  - `job_id`
  - `status`
  - `stage`
  - `progress`
  - `message`
  - `result`

### 2.4 视频分段检索

- 路径：`POST /api/video/search`
- Body：
  - `query`
  - `top_k`
  - `course_id`
- 返回字段：
  - `id`
  - `score`
  - `transcript`
  - `course_id`
  - `source_original_path`
  - `source_chunk_path`
  - `start_time`
  - `end_time`
  - `stream_url`
  - `playback_url`

## 3. 播放链路说明

### 3.1 本地课程视频 / 检索视频

1. 前端上传视频到 `POST /api/video/upload`
2. 后端异步切片并建立向量检索数据
3. 前端轮询 `GET /api/video/jobs/{job_id}`
4. 检索时调用 `POST /api/video/search`
5. 命中结果返回 `stream_url` 或 `playback_url`
6. 前端将返回地址放入 `<video src="...">` 播放

### 3.2 AI Lecturer 生成视频 / 录课回放

1. AI Lecturer 或录课流程把 `video_url` / `recording_url` 写回课程材料
2. 前端读取材料内容中的：
   - `video_url`
   - `recording_url`
3. 前端通过 `getAiLecturerVideoUrl()` 或 `playbackUrl()` 转成可播放地址
4. 最终仍由原生 `<video>` 组件播放

## 4. 当前替换时需要保留的关键接口点

- 主前端上传与检索必须继续保留：
  - `/api/video/upload`
  - `/api/video/jobs/{job_id}`
  - `/api/video/search`
  - `/api/video/stream`

- AI Lecturer 视频回放必须继续保留：
  - `getAiLecturerVideoUrl(path)`
  - 材料里的 `video_url`
  - 材料里的 `recording_url`

- 页面替换时不要改动：
  - 鉴权头 `Authorization: Bearer <token>`
  - `course_id` 传参方式
  - 视频检索返回结构
  - `<video>` 播放来源字段名
