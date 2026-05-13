# Chat V2 Multimodal Image Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add chat v2 image input so users can paste/upload images and the answer stage can use them with `qwen3.5-plus`.

**Architecture:** Keep the existing JSON reply contract and add a pre-uploaded `input_images` field. Backend stores guarded chat images locally, the reply normalizer carries image metadata into `ChatRequestV2`, and `FastChatRuntime` upgrades to a multimodal message only when image input exists.

**Tech Stack:** FastAPI, Pydantic, React, Zustand, Ant Design, Vitest/Node test runner, pytest

---

### Task 1: Add Backend Contract Tests

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`

- [ ] **Step 1: Write the failing runtime test**

```python
def test_fast_runtime_uses_multimodal_user_blocks_when_input_images_exist():
    ...
    assert gateway.last_messages[-1]["content"][1]["type"] == "image_url"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/chat/test_fast_chat_runtime.py -q`
Expected: FAIL because `ChatRequestV2` and `FastChatRuntime` do not yet know `input_images`

- [ ] **Step 3: Write route/service failing tests**

```python
response = client.post("/api/chat/v2/reply", json={"question": "look", "input_images": [...]})
assert response.status_code == 200
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/chat/test_reply_service_v2.py tests/chat/test_routes_v2.py -q`
Expected: FAIL because schema rejects or drops `input_images`

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py
git commit -m "test: cover chat v2 image input contract"
```

### Task 2: Implement Backend Image Input Contract

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/domain/contracts.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/domain/capability_policy.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/request_normalizer.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`

- [ ] **Step 1: Add shared image payload model**

```python
class ChatInputImageV2(BaseModel):
    image_id: str
    file_name: str
    mime_type: str
    storage_path: str
    relative_path: str
    image_url: str
    source: Literal["upload", "paste"] = "upload"
```

- [ ] **Step 2: Thread `input_images` through request/domain models**

```python
class ChatReplyRequestV2(BaseModel):
    ...
    input_images: List[ChatInputImageV2] = Field(default_factory=list)
```

- [ ] **Step 3: Normalize into `ChatRequestV2`**

```python
input_images=list(getattr(payload, "input_images", None) or [])
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/chat/test_reply_service_v2.py tests/chat/test_routes_v2.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py Edu_AI/api/Edu_AI/app/chat/domain/contracts.py Edu_AI/api/Edu_AI/app/chat/domain/capability_policy.py Edu_AI/api/Edu_AI/app/chat/application/request_normalizer.py Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py
git commit -m "feat: carry chat image input through v2 request models"
```

### Task 3: Add Backend Chat Image Upload + Multimodal Runtime

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/runtime/fast_chat_runtime.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py`
- Modify: `Edu_AI/api/Edu_AI/core/conversation_storage.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`

- [ ] **Step 1: Write failing upload route test**

```python
response = client.post("/api/chat/v2/images/upload", files={"files": ("a.png", b"...", "image/png")})
assert response.status_code == 200
assert response.json()["images"][0]["image_url"].startswith("/api/chat/v2/images/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/chat/test_routes_v2.py -q`
Expected: FAIL because route does not exist

- [ ] **Step 3: Implement upload route and guarded file serving**

```python
@router.post("/images/upload")
async def upload_chat_images(...)
```

- [ ] **Step 4: Implement multimodal block assembly in runtime**

```python
if request.input_images:
    user_content = [{"type": "text", "text": ...}, {"type": "image_url", "image_url": {"url": ...}}]
```

- [ ] **Step 5: Persist lightweight image metadata**

```python
state_patch["last_input_images"] = [...]
```

- [ ] **Step 6: Run backend tests**

Run: `pytest tests/chat/test_fast_chat_runtime.py tests/chat/test_routes_v2.py tests/chat/test_reply_service_v2.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py Edu_AI/api/Edu_AI/app/chat/runtime/fast_chat_runtime.py Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py Edu_AI/api/Edu_AI/core/conversation_storage.py Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py
git commit -m "feat: add chat image upload and multimodal fast runtime"
```

### Task 4: Add Frontend Tests For Pending Chat Images

**Files:**
- Modify: `Edu_AI/src/components/teacher/ChatPanel.tsx`
- Modify: `Edu_AI/src/services/teacher/chatV2.ts`
- Create: `Edu_AI/tests/frontend/chatPanel.image-input.test.tsx`

- [ ] **Step 1: Write failing test for paste/upload preview**

```tsx
expect(screen.getByText("已添加 1 张图片")).toBeInTheDocument()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test Edu_AI/tests/frontend/chatPanel.image-input.test.tsx`
Expected: FAIL because component has no image input UX

- [ ] **Step 3: Write failing test for send payload**

```tsx
expect(sendChatReplyV2).toHaveBeenCalledWith(expect.objectContaining({ input_images: [...] }))
```

- [ ] **Step 4: Run test to verify it fails**

Run: `node --test Edu_AI/tests/frontend/chatPanel.image-input.test.tsx`
Expected: FAIL because payload omits images

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/tests/frontend/chatPanel.image-input.test.tsx
git commit -m "test: cover chat panel image input flow"
```

### Task 5: Implement Frontend Image Input UX

**Files:**
- Modify: `Edu_AI/src/components/teacher/ChatPanel.tsx`
- Modify: `Edu_AI/src/services/teacher/chatV2.ts`
- Modify: `Edu_AI/src/store/teacher/useStore.ts`

- [ ] **Step 1: Add upload service**

```ts
export async function uploadChatImagesV2(files: File[]): Promise<ChatImageUploadResponseV2> { ... }
```

- [ ] **Step 2: Add pending image state and preview UI**

```tsx
const [pendingImages, setPendingImages] = useState<ChatInputImageV2[]>([])
```

- [ ] **Step 3: Handle paste and file select**

```tsx
onPaste={(event) => { ... }}
```

- [ ] **Step 4: Include `input_images` in reply payload and clear on success**

```ts
payload.input_images = pendingImages
```

- [ ] **Step 5: Run frontend tests**

Run: `node --test Edu_AI/tests/frontend/chatPanel.image-input.test.tsx`
Expected: PASS

- [ ] **Step 6: Run build**

Run: `npm run build`
Expected: build succeeds

- [ ] **Step 7: Commit**

```bash
git add Edu_AI/src/components/teacher/ChatPanel.tsx Edu_AI/src/services/teacher/chatV2.ts Edu_AI/src/store/teacher/useStore.ts Edu_AI/tests/frontend/chatPanel.image-input.test.tsx
git commit -m "feat: add chat image input and preview"
```

### Task 6: Full Verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend targeted verification**

Run: `pytest tests/chat/test_fast_chat_runtime.py tests/chat/test_reply_service_v2.py tests/chat/test_routes_v2.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `node --test Edu_AI/tests/frontend/chatPanel.image-input.test.tsx`
Expected: PASS

- [ ] **Step 3: Run syntax/build checks**

Run: `python -m py_compile Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py Edu_AI/api/Edu_AI/app/chat/runtime/fast_chat_runtime.py Edu_AI/api/Edu_AI/app/chat/application/request_normalizer.py Edu_AI/api/Edu_AI/app/chat/domain/contracts.py Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
Expected: no output

- [ ] **Step 4: Commit**

```bash
git add Edu_AI/api/Edu_AI/docs/superpowers/specs/2026-04-16-chat-v2-multimodal-image-input-design.md Edu_AI/api/Edu_AI/docs/superpowers/plans/2026-04-16-chat-v2-multimodal-image-input-implementation.md
git commit -m "docs: add chat multimodal image input spec and plan"
```
