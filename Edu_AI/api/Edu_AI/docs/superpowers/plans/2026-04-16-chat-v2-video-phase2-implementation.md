## Phase 2 Goal

让 `chat v2` 支持“用户在对话框内直接上传视频并参与当前轮对话”，同时把视频元数据持久化到消息历史与当前会话状态中，前端可恢复视频消息卡片。

## Scope

- 新增 `POST /api/chat/v2/videos/upload`
- `ChatReplyRequestV2` / `ChatRequestV2` 增加 `input_videos`
- 会话存储支持消息级 `input_videos`
- conversation state 支持 `last_input_videos` / `last_input_video_count`
- `ChatPanel` 支持待发送视频、发送 payload、历史回放视频卡片
- `fast_chat_runtime` 支持当前轮 `input_videos` 注入多模态 user content

## Out Of Scope

- 知识库视频检索排序优化
- 视频摘要、抽帧、ASR、OCR 增强
- 大文件分片上传或转码
- 完整替换主对话链路为 `query_stream`

## Backend Changes

1. `app/chat/domain/contracts.py`
   - 新增 `ChatInputVideoPayload`
   - 在 `ChatRequestV2` 中新增 `input_videos`

2. `app/chat/api/schemas_v2.py`
   - 在 `ChatReplyRequestV2` 中新增 `input_videos`

3. `app/chat/application/request_normalizer.py`
   - 把 `payload.input_videos` 规范化进入 `ChatRequestV2`

4. `app/chat/api/routes_v2.py`
   - 新增 `chat_videos` 存储目录与安全路径校验
   - 新增 `/videos/upload`
   - 新增 `/videos` 预览路由
   - 上传响应返回：
     - `video_id`
     - `file_name`
     - `mime_type`
     - `storage_path`
     - `relative_path`
     - `video_url`
     - `source`

5. `core/conversation_storage.py`
   - message 级别支持 `input_videos`
   - 读取旧记录时兼容默认空数组

6. `app/chat/persistence/conversation_store_adapter.py`
   - 归一化 `input_videos`
   - 用户消息写入 `input_videos`
   - state 写入 `last_input_videos` 与 `last_input_video_count`

7. `app/chat/runtime/fast_chat_runtime.py`
   - 当前轮请求支持 `input_videos`
   - 多模态 user content 在文本之后追加 `video_url` block
   - 历史回放先兼容消息级 `input_videos`

## Frontend Changes

1. `src/services/teacher/chatV2.ts`
   - 新增 `ChatInputVideoV2`
   - 新增 `ChatVideoUploadResponseV2`
   - 新增 `uploadChatVideosV2`
   - `ChatReplyRequestV2` / `buildChatReplyPayload` 支持 `input_videos`

2. `src/services/teacher/api.ts`
   - 历史消息结构增加 `input_videos`

3. `src/store/teacher/useStore.ts`
   - 聊天消息结构增加 `inputVideos`

4. `src/components/teacher/ChatPanel.tsx`
   - 新增待发送视频状态
   - 新增视频文件选择入口
   - 发送时把 `inputVideos` 挂到用户消息与 reply payload
   - 历史加载时恢复 `msg.input_videos`
   - 用认证媒体预览方式加载视频 blob URL
   - 在用户消息上方显示视频卡片

## Tests First

### Backend

- `tests/chat/test_routes_v2.py`
  - `reply` 透传 `input_videos`
  - `/api/chat/v2/videos/upload` 返回标准元数据
  - `/api/chat/v2/videos` 可读取上传视频

- `tests/chat/test_reply_service_v2.py`
  - `ReplyServiceV2` 归一化 `input_videos`

- `tests/chat/test_persistence_and_compat.py`
  - 用户消息历史持久化 `input_videos`
  - state 正确写入 `last_input_videos`

- `tests/chat/test_fast_chat_runtime.py`
  - 当前轮 `input_videos` 注入多模态 content
  - 历史用户视频可回放进模型上下文

### Frontend

- `tests/frontend/chatPanel.video-input.test.ts`
  - `ChatPanel` 维护 pending videos
  - 调用 `uploadChatVideosV2`
  - payload 带 `input_videos`

- `tests/frontend/chatPanel.message-video-history.test.ts`
  - 历史消息可恢复 `inputVideos`
  - 用户消息可显示视频卡片
  - 使用认证媒体加载 helper

## Verification

- `PYTHONPATH=d:\Edu_AI_1\Edu_AI\api\Edu_AI pytest tests/chat/test_routes_v2.py tests/chat/test_reply_service_v2.py tests/chat/test_persistence_and_compat.py tests/chat/test_fast_chat_runtime.py -q`
- `python -m py_compile app/chat/api/routes_v2.py app/chat/api/schemas_v2.py app/chat/domain/contracts.py app/chat/application/request_normalizer.py app/chat/persistence/conversation_store_adapter.py core/conversation_storage.py app/chat/runtime/fast_chat_runtime.py`
- `node tests/frontend/chatPanel.video-input.test.ts`
- `node tests/frontend/chatPanel.message-video-history.test.ts`
- `node tests/frontend/useStore.persistence.test.ts`
- `npm run build`
