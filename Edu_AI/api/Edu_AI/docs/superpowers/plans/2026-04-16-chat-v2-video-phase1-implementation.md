# Chat V2 Video Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让知识库视频沿用现有 `/api/video` 上传与检索底座，并把命中的视频片段接入 `chat v2` 主回答链路和前端证据展示。

**Architecture:** 保留当前 `chat v2 -> FastChatRuntime -> rag_retriever/web_retriever` 主链路，不切到 `query_stream`。Phase 1 新增一个“视频检索器”并把其结果并入 `sources`，同时补齐前端对视频来源的预览卡片渲染；不在本阶段处理聊天直传视频与历史持久化。

**Tech Stack:** FastAPI, Pydantic, existing chat-v2 runtime, local video ingestion search API, React, TypeScript, Vite, node static tests, pytest

---

## File Map

- Modify: `Edu_AI/api/Edu_AI/app/chat/runtime/fast_chat_runtime.py`
  - 在 runtime 中接入视频检索结果聚合，并把视频资料并入 `sources`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
  - 装配 runtime 时注入视频检索器
- Modify: `Edu_AI/api/Edu_AI/app/chat/tools/video_search.py`
  - 提供可供 `chat v2` 直接复用的结构化视频检索函数，返回统一 `sources`
- Modify: `Edu_AI/api/Edu_AI/src/components/teacher/ChatPanel.tsx`
  - 在 AI 消息证据区渲染视频来源卡片
- Modify: `Edu_AI/api/Edu_AI/src/services/teacher/chatV2.ts`
  - 明确 `sources` 中视频字段的类型，供前端渲染使用
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py`
  - 增加 runtime 聚合视频来源的失败测试与通过测试
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`
  - 验证 reply service 把视频检索器注入 runtime
- Test: `Edu_AI/tests/frontend/chatPanel.video-sources.test.ts`
  - 验证前端消息证据区能识别并渲染视频来源

### Task 1: Runtime 接入视频检索结果

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/runtime/fast_chat_runtime.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py`

- [ ] **Step 1: Write the failing runtime test**

```python
def test_run_includes_video_sources_when_rag_allowed():
    captured = {}

    def fake_model_gateway(*, messages, metadata):
        captured["messages"] = messages
        captured["metadata"] = metadata
        return {"answer": "ok"}

    def fake_rag_retriever(*args, **kwargs):
        return {"answer": "", "sources": [{"content": "文本资料", "metadata": {"modality": "text"}}]}

    def fake_video_retriever(*args, **kwargs):
        return {
            "sources": [
                {
                    "content": "第 12 秒到 24 秒讲解了关羽生平",
                    "source": "课程视频",
                    "metadata": {
                        "modality": "video",
                        "video_url": "/api/video/stream?rel_path=videos%2Fteacher%2Fclip.mp4",
                        "title": "关羽人物解析",
                        "start_time": 12,
                        "end_time": 24,
                    },
                }
            ]
        }

    runtime = FastChatRuntime(
        model_gateway=fake_model_gateway,
        rag_retriever=fake_rag_retriever,
        video_retriever=fake_video_retriever,
    )

    request = ChatRequestV2(message="总结视频里的人物信息", mode="chat")
    capability = SimpleNamespace(allow_rag=True, allow_web=False)

    result = runtime.run(
        request=request,
        capability=capability,
        conversation_messages=[],
        system_prompt="你是老师助手",
    )

    assert result["answer"] == "ok"
    assert any(source.get("metadata", {}).get("modality") == "video" for source in result["sources"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py -k video_sources -q`
Expected: FAIL because `FastChatRuntime` does not accept `video_retriever` yet or does not merge video sources.

- [ ] **Step 3: Write minimal runtime implementation**

```python
class FastChatRuntime:
    def __init__(self, *, model_gateway, rag_retriever=None, web_retriever=None, video_retriever=None):
        self.model_gateway = model_gateway
        self.rag_retriever = rag_retriever
        self.web_retriever = web_retriever
        self.video_retriever = video_retriever

    def run(...):
        sources: list[dict[str, Any]] = []
        if self.rag_retriever is not None and bool(getattr(capability, "allow_rag", False)):
            ...
            sources.extend(rag_sources)
        if self.video_retriever is not None and bool(getattr(capability, "allow_rag", False)):
            video_result = self.video_retriever(question=request.message)
            video_sources = list((video_result or {}).get("sources") or [])
            sources.extend(video_sources)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py -k video_sources -q`
Expected: PASS

- [ ] **Step 5: Refactor source aggregation only if needed**

```python
def _extend_sources(target: list[dict[str, Any]], payload: dict[str, Any] | None) -> None:
    if not isinstance(payload, dict):
        return
    sources = payload.get("sources") or []
    if isinstance(sources, list):
        target.extend(sources)
```

- [ ] **Step 6: Re-run focused runtime tests**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py -q`
Expected: PASS

### Task 2: Reply Service 装配视频检索器

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/tools/video_search.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`

- [ ] **Step 1: Write the failing reply service test**

```python
def test_build_runtime_injects_video_retriever(monkeypatch):
    captured = {}

    class FakeRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(reply_service_module, "FastChatRuntime", FakeRuntime)

    service = ReplyServiceV2(...)
    service._build_runtime()

    assert callable(captured["video_retriever"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -k video_retriever -q`
Expected: FAIL because `ReplyServiceV2` only injects `rag_retriever` and `web_retriever`.

- [ ] **Step 3: Add minimal structured video retriever**

```python
def search_video_segments_for_runtime(*, question: str, course_id: str | None = None, top_k: int = 3) -> dict[str, Any]:
    hits = search_video_segments_for_chat(question=question, course_id=course_id, top_k=top_k)
    sources = []
    for hit in hits:
        sources.append(
            {
                "content": hit.get("content") or hit.get("summary") or "",
                "source": hit.get("title") or "视频资料",
                "metadata": {
                    "modality": "video",
                    "video_url": hit.get("stream_url"),
                    "title": hit.get("title"),
                    "start_time": hit.get("start_time"),
                    "end_time": hit.get("end_time"),
                },
            }
        )
    return {"answer": "", "sources": sources}
```

- [ ] **Step 4: Inject the retriever into runtime**

```python
return FastChatRuntime(
    model_gateway=self._model_gateway,
    rag_retriever=rag_search_tool,
    web_retriever=web_search_tool,
    video_retriever=video_search_tool,
)
```

- [ ] **Step 5: Run focused reply service test**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -k video_retriever -q`
Expected: PASS

- [ ] **Step 6: Run related service tests**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py -q`
Expected: PASS

### Task 3: 前端证据区显示视频来源卡片

**Files:**
- Modify: `Edu_AI/src/components/teacher/ChatPanel.tsx`
- Modify: `Edu_AI/src/services/teacher/chatV2.ts`
- Test: `Edu_AI/tests/frontend/chatPanel.video-sources.test.ts`

- [ ] **Step 1: Write the failing frontend test**

```ts
assert.match(
  source,
  /source\\.metadata\\?\\.modality === 'video'/,
  'ChatPanel should detect video sources in AI evidence cards',
);

assert.match(
  source,
  /<video[^>]*controls/,
  'ChatPanel should render a playable video preview for video sources',
);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node Edu_AI/tests/frontend/chatPanel.video-sources.test.ts`
Expected: FAIL because `ChatPanel` does not render video sources yet.

- [ ] **Step 3: Add minimal front-end rendering**

```tsx
const isVideoSource = source.metadata?.modality === 'video' && source.metadata?.video_url;

{isVideoSource ? (
  <div className="teacher-chat-video-source">
    <div>{source.metadata?.title || source.source || '视频资料'}</div>
    <video controls preload="metadata" src={resolvedVideoUrl} style={{ width: '100%', borderRadius: 12 }} />
  </div>
) : (
  existingSourceCard
)}
```

- [ ] **Step 4: Add source typing for video metadata**

```ts
export type ChatSourceV2 = Record<string, unknown> & {
  metadata?: {
    modality?: string;
    video_url?: string;
    title?: string;
    start_time?: number;
    end_time?: number;
  };
};
```

- [ ] **Step 5: Run focused frontend test**

Run: `node Edu_AI/tests/frontend/chatPanel.video-sources.test.ts`
Expected: PASS

- [ ] **Step 6: Re-run existing chat image/video-adjacent frontend tests**

Run: `node Edu_AI/tests/frontend/chatPanel.image-input.test.ts`
Expected: PASS

### Task 4: End-to-end verification for Phase 1

**Files:**
- No additional production files
- Test: existing targeted test files above

- [ ] **Step 1: Run backend targeted suite**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend targeted suite**

Run: `node Edu_AI/tests/frontend/chatPanel.video-sources.test.ts`
Expected: PASS

- [ ] **Step 3: Build frontend**

Run: `npm run build`
Expected: PASS with at most existing chunk-size warning

- [ ] **Step 4: Smoke-scan for unexpected regressions**

Run: `rg -n "video_retriever|input_videos|video_url" Edu_AI/api/Edu_AI/app/chat Edu_AI/src/components/teacher`
Expected: only intentional additions and existing video references

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/runtime/fast_chat_runtime.py \
        Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py \
        Edu_AI/api/Edu_AI/app/chat/tools/video_search.py \
        Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py \
        Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py \
        Edu_AI/src/components/teacher/ChatPanel.tsx \
        Edu_AI/src/services/teacher/chatV2.ts \
        Edu_AI/tests/frontend/chatPanel.video-sources.test.ts \
        Edu_AI/api/Edu_AI/docs/superpowers/plans/2026-04-16-chat-v2-video-phase1-implementation.md
git commit -m "feat: surface knowledge-base video sources in chat v2"
```

## Self-Review

- Spec coverage: Phase 1 的三项要求已覆盖到任务中
  - 保持 `/api/video/upload` 不变：没有改动该路由，只复用既有搜索能力
  - 将视频命中结果接入 `chat v2` 回答链路：Task 1 + Task 2
  - 在证据区显示视频来源：Task 3
- Placeholder scan: 没有使用 TBD/TODO/“自行实现”等占位语句
- Type consistency: 全文统一使用 `video_retriever`、`video_url`、`modality=video` 作为 Phase 1 字段名

Plan complete and saved to `docs/superpowers/plans/2026-04-16-chat-v2-video-phase1-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints
