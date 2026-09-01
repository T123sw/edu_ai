# AI Classroom Realtime Q&A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add student text Q&A that pauses an active OpenMAIC classroom at a sentence-level checkpoint, answers from trusted classroom and course context, speaks the answer through Qwen TTS, and resumes naturally.

**Architecture:** Extend the existing frontend playback runtime with suspend/resume checkpoints, then layer a classroom-specific interruption coordinator and Q&A panel above it. Add a dedicated FastAPI classroom Q&A boundary that owns per-student session persistence, trusted context reconstruction, LLM generation, OpenMAIC Qwen TTS synthesis, and protected answer audio; do not restore the retired LiveTalking/WebRTC stack.

**Tech Stack:** React 18, TypeScript, Vite, Node test runner, FastAPI, Pydantic, Python 3.12, httpx, file-backed `CourseStorageManager`, OpenMAIC sidecar Qwen TTS.

## Global Constraints

- Student input is text only; no microphone, ASR, wake word, echo cancellation, WebRTC, digital human, or lip sync.
- Opening the Q&A composer pauses teaching immediately.
- An interrupted action restarts from its beginning; a between-action checkpoint resumes at the next action.
- Q&A history is isolated by course, classroom, and student and survives refresh.
- Original classroom `scenes/actions` and exported PPTX/MP4 stay unchanged.
- Server-side Qwen TTS is always attempted before browser `SpeechSynthesis` fallback.
- Only one unfinished turn is allowed per session; no queue and no interruption of an answer.
- Question length is 1–1000 characters; history returns at most 100 turns.
- Active runtime code must not add LiveTalking, WebRTC, AI Lecturer, or GPU service dependencies.
- Preserve unrelated PostgreSQL working-tree changes; stage and commit only files listed by the current task.

---

## File Structure

### Frontend

| File | Responsibility |
| --- | --- |
| `frontend/src/openmaic/playbackEngine.ts` | Sentence-level checkpoint semantics and suspend/resume |
| `frontend/src/openmaic/actionEngine.ts` | Cancel current media without disposing the reusable action engine |
| `frontend/src/openmaic/pagePlaybackController.ts` | Bind the concrete scene runtime and coordinate interruption state |
| `frontend/src/openmaic/SceneActionPlayback.tsx` | Expose a `PlaybackRuntimeHandle` from the renderer-owned engine |
| `frontend/src/openmaic/{SlidePlayer,InteractiveScenePlayer,QuizScenePlayer,ClassroomSceneRenderer}.tsx` | Forward runtime-ready callbacks |
| `frontend/src/stitch/api/classroomQa.ts` | Session, turn, and authenticated audio API adapter |
| `frontend/src/stitch/classroomQa/classroomQaState.ts` | Pure Q&A state transitions |
| `frontend/src/stitch/classroomQa/useClassroomInterruption.ts` | Pause → submit → speak → resume orchestration |
| `frontend/src/stitch/classroomQa/ClassroomQaPanel.tsx` | Accessible question/history/status UI |
| `frontend/src/stitch/classroomQa/ClassroomQaPanel.css` | Normal, fullscreen, and narrow-layout styling |
| `frontend/src/stitch/pages/ClassroomPlayer.tsx` | Compose the playback controller and Q&A feature |

### Backend

| File | Responsibility |
| --- | --- |
| `backend/src/app/schemas/classroom_qa.py` | Pydantic request/response contracts |
| `backend/src/app/services/classroom_qa_store.py` | Per-student atomic session persistence and idempotency |
| `backend/src/app/services/classroom_qa_prompt.py` | Trusted classroom context and structured prompt/parser |
| `backend/src/app/services/classroom_qa_tts.py` | Qwen TTS call, validation, and atomic audio persistence |
| `backend/src/app/services/classroom_qa_service.py` | End-to-end turn orchestration and stable errors |
| `backend/src/app/api/classroom_qa.py` | Course-authorized session, turn, and audio routes |
| `backend/src/app/integrations/openmaic/client.py` | `/api/generate/tts` client method |
| `backend/src/core/course_storage.py` | Resolve the owner-hashed classroom Q&A directory |
| `backend/src/app/bootstrap.py` | Register the new router |

---

### Task 1: Add cancellable action execution and playback checkpoints

**Files:**
- Modify: `frontend/src/openmaic/actionEngine.ts`
- Modify: `frontend/src/openmaic/actionEngine.test.ts`
- Modify: `frontend/src/openmaic/playbackEngine.ts`
- Modify: `frontend/src/openmaic/playbackEngine.test.ts`

**Interfaces:**
- Consumes: existing `ActionMediaAdapter.cancel()`, `ActionEngine.execute()`, compiled timeline entries.
- Produces:

```ts
export type PlaybackMode = "idle" | "playing" | "suspended";

export type PlaybackCheckpoint = {
  sceneId: string;
  actionIndex: number;
  actionId: string | null;
  phase: "executing_action" | "between_actions";
};

export interface ActionExecutor {
  execute(action: Action, context?: ActionExecutionContext): Promise<void>;
  cancelCurrent(): void;
  clearEffects(): void;
  dispose(): void;
}

export class PlaybackEngine {
  start(): void;
  suspend(): PlaybackCheckpoint;
  resume(checkpoint: PlaybackCheckpoint): void;
  stop(): void;
  dispose(): void;
}
```

- [ ] **Step 1: Write failing action cancellation tests**

Add a test proving cancellation settles active speech without permanently disposing the engine:

```ts
test("cancelCurrent stops active narration and allows the next execution", async () => {
  const media = new FakeMedia();
  media.deferSpeech = true;
  const engine = new ActionEngine({}, { media });

  const first = engine.execute({ id: "s1", type: "speech", text: "first" });
  await Promise.resolve();
  engine.cancelCurrent();
  await first;

  media.deferSpeech = false;
  await engine.execute({ id: "s2", type: "speech", text: "second" });
  assert.deepEqual(media.calls, ["speech", "cancel", "speech"]);
});
```

- [ ] **Step 2: Run the cancellation test and verify failure**

Run:

```powershell
Set-Location D:\github\edu_ai\Edu_AI
pnpm exec tsx --test src/openmaic/actionEngine.test.ts
```

Expected: FAIL because `ActionEngine.cancelCurrent` does not exist.

- [ ] **Step 3: Add `ActionEngine.cancelCurrent()`**

Implement exactly this boundary:

```ts
cancelCurrent(): void {
  if (this.disposed) return;
  this.media.cancel();
  this.video?.cancel();
  this.clearEffects();
}
```

Change `dispose()` to set `disposed=true`, call `cancelCurrent()` before the disposed guard can suppress cancellation, and keep disposal idempotent.

- [ ] **Step 4: Write failing playback checkpoint tests**

Cover both required positions:

```ts
test("suspending an in-flight action resumes that action from the beginning", async () => {
  const executor = new DeferredExecutor();
  const engine = createTwoSpeechEngine(executor);
  engine.start();
  await Promise.resolve();

  const checkpoint = engine.suspend();
  assert.deepEqual(checkpoint, {
    sceneId: "scene-1",
    actionIndex: 0,
    actionId: "speech-1",
    phase: "executing_action",
  });

  executor.release();
  engine.resume(checkpoint);
  await Promise.resolve();
  assert.deepEqual(executor.executed, ["speech-1", "speech-1"]);
});

test("suspending between actions resumes at the next action", async () => {
  const executor = new PausingBetweenActionsExecutor();
  const engine = createTwoSpeechEngine(executor);
  engine.start();
  await executor.firstCompleted;

  const checkpoint = engine.suspend();
  assert.equal(checkpoint.phase, "between_actions");
  assert.equal(checkpoint.actionIndex, 1);
  engine.resume(checkpoint);
  await executor.completed;
  assert.deepEqual(executor.executed, ["speech-1", "speech-2"]);
});
```

Also add stale `sceneId`, stale `actionId`, repeated suspend, and old async completion tests.

- [ ] **Step 5: Run playback tests and verify failure**

Run:

```powershell
pnpm exec tsx --test src/openmaic/playbackEngine.test.ts
```

Expected: FAIL because the current engine increments `actionIndex` before execution and has no suspend/resume API.

- [ ] **Step 6: Refactor `PlaybackEngine` cursor semantics**

Use explicit in-flight state and only advance after a non-stale execution completes:

```ts
private inFlight: { sceneId: string; actionIndex: number; actionId: string } | null = null;

private async processNext(): Promise<void> {
  const token = this.runToken;
  if (this.mode !== "playing") return;
  const current = this.getCurrentAction();
  if (!current) return this.finish();

  this.inFlight = {
    sceneId: current.sceneId,
    actionIndex: this.actionIndex,
    actionId: current.action.id,
  };
  this.callbacks.onActionStart?.(current.action, this.clock.currentTimeMs(), current.sceneId);
  await this.actionEngine.execute(current.action, current.context);
  if (token !== this.runToken || this.mode !== "playing") return;

  this.callbacks.onActionEnd?.(current.action, this.clock.currentTimeMs(), current.sceneId);
  this.inFlight = null;
  this.actionIndex += 1;
  void this.processNext();
}
```

`suspend()` must bump `runToken`, call `cancelCurrent()`, set mode to `suspended`, and return the current or between-action checkpoint. `resume()` validates checkpoint identity against compiled entries, restores indexes, sets `playing`, and calls `processNext()`.

- [ ] **Step 7: Run Task 1 tests**

Run:

```powershell
pnpm exec tsx --test src/openmaic/actionEngine.test.ts src/openmaic/playbackEngine.test.ts
```

Expected: PASS; no existing cancellation, focus, video, ordering, or stale-run test regresses.

- [ ] **Step 8: Commit Task 1**

```powershell
git add frontend/src/openmaic/actionEngine.ts frontend/src/openmaic/actionEngine.test.ts frontend/src/openmaic/playbackEngine.ts frontend/src/openmaic/playbackEngine.test.ts
git commit -m "feat(classroom): add resumable playback checkpoints"
```

---

### Task 2: Expose the concrete playback runtime to the classroom page

**Files:**
- Modify: `frontend/src/openmaic/pagePlaybackController.ts`
- Modify: `frontend/src/openmaic/pagePlaybackController.test.ts`
- Modify: `frontend/src/openmaic/SceneActionPlayback.tsx`
- Modify: `frontend/src/openmaic/SlidePlayer.tsx`
- Modify: `frontend/src/openmaic/InteractiveScenePlayer.tsx`
- Modify: `frontend/src/openmaic/QuizScenePlayer.tsx`
- Modify: `frontend/src/openmaic/ClassroomSceneRenderer.tsx`

**Interfaces:**
- Consumes: `PlaybackEngine.suspend/resume`, `PlaybackCheckpoint` from Task 1.
- Produces:

```ts
export interface PlaybackRuntimeHandle {
  play(): void;
  suspend(): PlaybackCheckpoint;
  resume(checkpoint: PlaybackCheckpoint): void;
  cancel(): void;
  dispose(): void;
}

export type PagePlaybackCheckpoint = PlaybackCheckpoint & {
  sceneIndex: number;
  pageRevision: number;
};

export interface PagePlaybackController {
  bindRuntime(sceneIndex: number, revision: number, runtime: PlaybackRuntimeHandle): void;
  interrupt(): PagePlaybackCheckpoint | null;
  resumeInterrupted(checkpoint: PagePlaybackCheckpoint): boolean;
}
```

- [ ] **Step 1: Write failing page-controller interruption tests**

Add tests for runtime binding, checkpoint decoration, stale revision rejection, one-time resume, page navigation disposal, and manual replay reset:

```ts
test("interrupt decorates the runtime checkpoint and resumes the bound revision", async () => {
  const { controller, runtime } = createBoundHarness();
  await controller.enter(2);
  controller.bindRuntime(2, controller.snapshot().revision, runtime);
  await controller.play();

  const checkpoint = controller.interrupt();
  assert.equal(controller.snapshot().status, "interrupted");
  assert.equal(checkpoint?.sceneIndex, 2);
  assert.equal(checkpoint?.pageRevision, controller.snapshot().revision);
  assert.equal(controller.resumeInterrupted(checkpoint!), true);
  assert.equal(controller.snapshot().status, "playing");
});
```

- [ ] **Step 2: Run the page-controller test and verify failure**

```powershell
pnpm exec tsx --test src/openmaic/pagePlaybackController.test.ts
```

Expected: FAIL because `interrupted`, `bindRuntime`, and checkpoint APIs do not exist.

- [ ] **Step 3: Implement runtime binding without remounting on interrupt**

Add `interrupted` to `PagePlaybackStatus`. Increment `revision` only for page enter, hard replay, or leave. Do not increment it for `playing ↔ interrupted`, because a remount would destroy the checkpoint-owning engine.

Reject a bind if its scene index or revision is not current:

```ts
bindRuntime(sceneIndex: number, revision: number, runtime: PlaybackRuntimeHandle): void {
  if (this.disposed || sceneIndex !== this.current.sceneIndex || revision !== this.current.revision) {
    runtime.dispose();
    return;
  }
  this.runtime?.dispose();
  this.runtime = runtime;
}
```

- [ ] **Step 4: Expose the runtime from `SceneActionPlayback`**

Add `onRuntimeReady?: (runtime: PlaybackRuntimeHandle | null) => void`. Build a stable handle around the effect-owned engine:

```ts
const runtime: PlaybackRuntimeHandle = {
  play: () => engine.start(),
  suspend: () => engine.suspend(),
  resume: (checkpoint) => engine.resume(checkpoint),
  cancel: () => engine.stop(),
  dispose: () => engine.dispose(),
};
callbacksRef.current.onRuntimeReady?.(runtime);
return () => {
  callbacksRef.current.onRuntimeReady?.(null);
  engine.dispose();
};
```

Treat `autoPlay` as initial mount behavior; changing parent status to `interrupted` must not recreate the engine.

- [ ] **Step 5: Forward `onRuntimeReady` through all scene players**

Add the same optional prop to `SlidePlayer`, `InteractiveScenePlayer`, `QuizScenePlayer`, and `ClassroomSceneRenderer`. Each adapter forwards it to `SceneActionPlayback`; no scene-specific interrupt logic is allowed.

- [ ] **Step 6: Run Task 2 tests and the scene regression tests**

```powershell
pnpm exec tsx --test `
  src/openmaic/pagePlaybackController.test.ts `
  src/openmaic/playbackEngine.test.ts `
  src/openmaic/actionEngine.test.ts `
  src/openmaic/interactiveScene.test.ts `
  src/openmaic/quizScene.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```powershell
git add frontend/src/openmaic/pagePlaybackController.ts frontend/src/openmaic/pagePlaybackController.test.ts frontend/src/openmaic/SceneActionPlayback.tsx frontend/src/openmaic/SlidePlayer.tsx frontend/src/openmaic/InteractiveScenePlayer.tsx frontend/src/openmaic/QuizScenePlayer.tsx frontend/src/openmaic/ClassroomSceneRenderer.tsx
git commit -m "refactor(classroom): expose interruptible scene runtime"
```

---

### Task 3: Define classroom Q&A contracts and atomic per-student storage

**Files:**
- Create: `backend/src/app/schemas/classroom_qa.py`
- Create: `backend/src/app/services/classroom_qa_store.py`
- Create: `backend/src/tests/test_classroom_qa_store.py`
- Modify: `backend/src/core/course_storage.py`
- Modify: `backend/src/tests/core/test_course_storage_generated_materials.py`

**Interfaces:**
- Consumes: `CourseStorageManager.get_classroom_video_dir` directory conventions and atomic material persistence patterns.
- Produces:

```python
class ClassroomQaCheckpoint(BaseModel):
    scene_id: str
    scene_index: int = Field(ge=0)
    action_index: int = Field(ge=0)
    action_id: str | None = None
    phase: Literal["executing_action", "between_actions"]
    page_revision: int = Field(ge=0)

class ClassroomQaTurnRequest(BaseModel):
    client_turn_id: UUID
    question: str = Field(min_length=1, max_length=1000)
    checkpoint: ClassroomQaCheckpoint

class ClassroomQaSessionStore:
    def load_or_empty(self, *, course_id: str, classroom_id: str, owner_user_id: str) -> dict: ...
    def get_or_create(self, *, course_id: str, classroom_id: str, owner_user_id: str) -> dict: ...
    def begin_turn(self, *, session: dict, client_turn_id: str, question: str, checkpoint: dict) -> dict: ...
    def complete_turn(self, *, session: dict, client_turn_id: str, turn: dict) -> dict: ...
    def fail_turn(self, *, session: dict, client_turn_id: str, error_code: str, retryable: bool) -> dict: ...
```

- [ ] **Step 1: Write failing storage path and isolation tests**

```python
def test_classroom_qa_directory_hashes_owner(tmp_path):
    manager = CourseStorageManager(root_dir=tmp_path)
    path = manager.get_classroom_qa_dir("course-1", "classroom-1", "student@example.com")
    assert path.name == hashlib.sha256(b"student@example.com").hexdigest()[:24]
    assert "student@example.com" not in str(path)
    assert "classroom-1_media" in str(path)
```

Add store tests for read-without-write on an empty session, same owner idempotency, different owner separation, atomic JSON replacement, 100-turn truncation, stale `processing` after 120 seconds, and simultaneous different `client_turn_id` conflict.

- [ ] **Step 2: Run storage tests and verify failure**

```powershell
Set-Location D:\github\edu_ai\backend\src
python -m pytest tests/test_classroom_qa_store.py tests/core/test_course_storage_generated_materials.py -q
```

Expected: FAIL because the storage resolver and store do not exist.

- [ ] **Step 3: Add the owner-hashed directory resolver**

```python
def get_classroom_qa_dir(self, course_id: str, classroom_id: str, owner_user_id: str) -> Path:
    owner_hash = hashlib.sha256(owner_user_id.encode("utf-8")).hexdigest()[:24]
    return self.get_classroom_media_dir(course_id, classroom_id) / "qa" / owner_hash
```

Use the existing classroom media root helper if present; otherwise factor the common `{classroom_id}_media` calculation into one private method used by audio, video, and Q&A.

- [ ] **Step 4: Implement schemas with trim validation**

Use Pydantic field validators so whitespace-only questions fail with 422:

```python
@field_validator("question")
@classmethod
def normalize_question(cls, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("question must not be blank")
    return normalized
```

Define response models exactly matching SPEC-12 §8 and restrict `tts_status` to `ready | failed`.

- [ ] **Step 5: Implement the file-backed store**

Use one process lock per resolved session path, an atomic claim file, and atomic JSON replacement. Acquire `active-turn.lock` with `os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)` before starting LLM/TTS; a second process that cannot create the claim returns `CLASSROOM_QA_BUSY`. Write session JSON with:

```python
temporary = session_path.with_name(f".{session_path.name}.{uuid4().hex}.tmp")
with temporary.open("w", encoding="utf-8", newline="\n") as stream:
    json.dump(session, stream, ensure_ascii=False, indent=2)
    stream.flush()
    os.fsync(stream.fileno())
os.replace(temporary, session_path)
```

Derive `session_id` from SHA-256 of `course_id\0classroom_id\0owner_user_id`, prefixed with `cqa_`, so repeated GET is deterministic. `load_or_empty` returns an in-memory empty session without creating a file. Store the owner in JSON but never in the directory name. Remove the claim only after completed/failed session state is atomically persisted; reclaim claims older than 120 seconds under the path lock.

- [ ] **Step 6: Run Task 3 tests**

```powershell
python -m pytest tests/test_classroom_qa_store.py tests/core/test_course_storage_generated_materials.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```powershell
git add backend/src/app/schemas/classroom_qa.py backend/src/app/services/classroom_qa_store.py backend/src/tests/test_classroom_qa_store.py backend/src/core/course_storage.py backend/src/tests/core/test_course_storage_generated_materials.py
git commit -m "feat(classroom): add isolated QA session storage"
```

---

### Task 4: Add OpenMAIC Qwen TTS synthesis to the Python client

**Files:**
- Modify: `backend/src/app/integrations/openmaic/client.py`
- Modify: `backend/src/tests/test_openmaic_client.py`
- Modify: `backend/src/core/config.py`
- Modify: `backend/src/.env.example`

**Interfaces:**
- Consumes: sidecar `POST /api/generate/tts` success envelope `{success,data:{audioId,base64,format}}`.
- Produces:

```python
async def synthesize_tts(
    self,
    *,
    text: str,
    audio_id: str,
    provider_id: str,
    voice: str,
    speed: float = 1.0,
) -> tuple[bytes, str]: ...
```

- [ ] **Step 1: Write failing mock-transport tests**

```python
@pytest.mark.anyio
async def test_synthesize_tts_posts_server_managed_qwen_and_decodes_audio():
    expected = b"ID3-answer-audio"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate/tts"
        assert json.loads(request.content) == {
            "text": "回答。回到课堂。",
            "audioId": "turn-1",
            "ttsProviderId": "qwen-tts",
            "ttsVoice": "Cherry",
            "ttsSpeed": 1.0,
        }
        return httpx.Response(200, json={
            "success": True,
            "data": {
                "audioId": "turn-1",
                "base64": base64.b64encode(expected).decode("ascii"),
                "format": "mp3",
            },
        })

    client = OpenMaicClient(transport=httpx.MockTransport(handler))
    audio, format_name = await client.synthesize_tts(
        text="回答。回到课堂。",
        audio_id="turn-1",
        provider_id="qwen-tts",
        voice="Cherry",
    )
    assert audio == expected
    assert format_name == "mp3"
```

Add invalid base64, empty audio, payload above 10 MiB, 429 mapping, timeout, and `success=false` tests.

- [ ] **Step 2: Run client tests and verify failure**

```powershell
python -m pytest tests/test_openmaic_client.py -q
```

Expected: FAIL because `synthesize_tts` does not exist.

- [ ] **Step 3: Implement the client method**

Call `_request_json` with `retryable=True`, then unwrap `data`, validate `audioId`, allow formats `mp3 | wav | ogg | m4a`, decode with `base64.b64decode(..., validate=True)`, reject empty or over-limit bytes, and return `(audio_bytes, format_name)`.

- [ ] **Step 4: Add server-owned defaults**

Add Config fields:

```python
OPENMAIC_LIVE_TTS_PROVIDER = os.getenv("OPENMAIC_LIVE_TTS_PROVIDER", "qwen-tts")
OPENMAIC_LIVE_TTS_VOICE = os.getenv("OPENMAIC_LIVE_TTS_VOICE", "Cherry")
OPENMAIC_LIVE_TTS_SPEED = float(os.getenv("OPENMAIC_LIVE_TTS_SPEED", "1.0"))
```

Document the same defaults in `.env.example` without credentials. Clamp speed to `0.5..2.0` before requests.

- [ ] **Step 5: Run Task 4 tests**

```powershell
python -m pytest tests/test_openmaic_client.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```powershell
git add backend/src/app/integrations/openmaic/client.py backend/src/tests/test_openmaic_client.py backend/src/core/config.py backend/src/.env.example
git commit -m "feat(openmaic): add server-managed Qwen TTS client"
```

---

### Task 5: Build trusted classroom context and the focused answer generator

**Files:**
- Create: `backend/src/app/services/classroom_qa_prompt.py`
- Create: `backend/src/tests/test_classroom_qa_prompt.py`

**Interfaces:**
- Consumes: persisted classroom material, validated checkpoint, recent session turns, RAG payload, existing model gateway.
- Produces:

```python
@dataclass(frozen=True)
class ClassroomQaContext:
    classroom_title: str
    scene_id: str
    scene_title: str
    scene_speech: tuple[str, ...]
    completed_speech: tuple[str, ...]
    interrupted_speech: str | None
    previous_scene_speech: tuple[str, ...]
    recent_turns: tuple[dict, ...]
    rag_answer: str

def build_classroom_qa_context(*, material: dict, checkpoint: dict, recent_turns: list[dict], rag_answer: str) -> ClassroomQaContext: ...
def build_classroom_qa_messages(*, question: str, context: ClassroomQaContext) -> list[dict]: ...
def parse_classroom_qa_answer(raw: str, *, scene_title: str) -> tuple[str, str]: ...
```

- [ ] **Step 1: Write failing context validation tests**

Use a fixture with two scenes and three speech actions. Assert:

```python
context = build_classroom_qa_context(
    material=fixture,
    checkpoint={
        "scene_id": "scene-2",
        "scene_index": 1,
        "action_index": 1,
        "action_id": "speech-2b",
        "phase": "executing_action",
        "page_revision": 4,
    },
    recent_turns=history,
    rag_answer="课程知识库摘要",
)
assert context.completed_speech == ("第二页第一句",)
assert context.interrupted_speech == "第二页第二句"
assert context.previous_scene_speech == ("第一页倒数第三句", "第一页倒数第二句", "第一页最后一句")
```

Add action index out of range, action ID mismatch, scene mismatch, non-speech interrupted action, six-turn history cap, structured JSON parse, fenced JSON parse, pure-text fallback, empty answer, and length clamp tests.

- [ ] **Step 2: Run prompt tests and verify failure**

```powershell
python -m pytest tests/test_classroom_qa_prompt.py -q
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement trusted context reconstruction**

Never use client-supplied lecture text. Locate the scene by both index and ID, compile the playable action order using the persisted action array, validate the checkpoint against that array, and extract speech text from the trusted material.

- [ ] **Step 4: Implement the focused prompt**

The system message must include these hard rules:

```text
你是正在授课的 AI 教师。只回答学生当前问题，不创建课件、报告或其他资源。
优先结合当前讲授内容，再使用课程知识库参考信息。
回答正文通常为 80～300 个中文字符；信息不足时明确边界。
另写一句 10～40 个中文字符的自然衔接语，回到当前场景。
只输出 JSON：{"answer_text":"...","transition_text":"..."}。
```

The user message renders labeled classroom context, recent turns, RAG answer, and the exact question.

- [ ] **Step 5: Implement bounded parsing**

Strip code fences, parse JSON when possible, otherwise use raw text as the answer. Normalize whitespace, cap answer at 1200 characters, cap transition at 120 characters, and use:

```python
fallback_transition = f"好，我们回到刚才“{scene_title}”的讲解。"
```

- [ ] **Step 6: Run Task 5 tests**

```powershell
python -m pytest tests/test_classroom_qa_prompt.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```powershell
git add backend/src/app/services/classroom_qa_prompt.py backend/src/tests/test_classroom_qa_prompt.py
git commit -m "feat(classroom): build trusted QA teaching context"
```

---

### Task 6: Orchestrate idempotent Agent answers and Qwen audio persistence

**Files:**
- Create: `backend/src/app/services/classroom_qa_tts.py`
- Create: `backend/src/app/services/classroom_qa_service.py`
- Create: `backend/src/tests/test_classroom_qa_service.py`

**Interfaces:**
- Consumes: Task 3 store, Task 4 `OpenMaicClient.synthesize_tts`, Task 5 prompt functions, existing `rag_search_tool`, existing model gateway.
- Produces:

```python
class ClassroomQaService:
    async def get_session(self, *, course_id: str, classroom_id: str, owner_user_id: str) -> dict: ...
    async def submit_turn(self, *, course_id: str, classroom_id: str, owner_user_id: str, request: ClassroomQaTurnRequest) -> dict: ...

class ClassroomQaTtsService:
    async def synthesize_and_store(self, *, session_dir: Path, turn_id: str, text: str) -> tuple[str, str]: ...
```

- [ ] **Step 1: Write failing service tests**

Use injected fakes for material loading, RAG, gateway, TTS, clock, and store. Cover:

```python
@pytest.mark.anyio
async def test_submit_turn_is_idempotent_across_repeated_client_turn_id():
    first = await service.submit_turn(**request_args)
    second = await service.submit_turn(**request_args)
    assert first == second
    assert gateway.calls == 1
    assert tts.calls == 1

@pytest.mark.anyio
async def test_tts_failure_preserves_answer_and_marks_degraded():
    tts.error = OpenMaicUnavailable("offline")
    result = await service.submit_turn(**request_args)
    assert result["turn"]["answer_text"]
    assert result["turn"]["tts_status"] == "failed"
    assert result["turn"]["audio_url"] is None
```

Also test RAG failure degradation, LLM failure persistence, stale checkpoint, 409 busy error, no course access material, and metrics fields.

- [ ] **Step 2: Run service tests and verify failure**

```powershell
python -m pytest tests/test_classroom_qa_service.py -q
```

Expected: FAIL because the services do not exist.

- [ ] **Step 3: Implement atomic TTS persistence**

Build `speech_text = f"{answer_text}\n{transition_text}"`, cap at 1500 characters, call Qwen via Task 4, map allowed format to extension and MIME type, write into `session_dir/audio/{turn_id}.{extension}` using flush/fsync/os.replace, and return `(filename, mime_type)`.

- [ ] **Step 4: Implement orchestration order**

The method order is fixed:

```python
session = store.get_or_create(...)
existing = store.find_turn(session, client_turn_id)
if existing is not None:
    return response_for(existing)
store.begin_turn(...)
material = load_visible_classroom(...)
context = build_context(material, checkpoint, history, rag_answer)
raw_answer = gateway.chat(build_messages(question, context))
answer_text, transition_text = parse_answer(raw_answer, scene_title=context.scene_title)
try:
    filename, mime_type = await tts.synthesize_and_store(...)
    tts_status, audio_url = "ready", build_audio_url(filename)
except OpenMaicError:
    tts_status, audio_url = "failed", None
turn = build_completed_turn(...)
store.complete_turn(...)
return response_for(turn)
```

RAG failure sets a degradation flag and continues. LLM failure calls `store.fail_turn` and raises a stable `ClassroomQaError("CLASSROOM_QA_ANSWER_FAILED", retryable=True)`.

- [ ] **Step 5: Add structured timing without content logging**

Record `rag_ms`, `llm_ms`, `tts_ms`, `total_ms`, IDs, checkpoint IDs, result, and stable code. Do not log raw questions, answers, Authorization, base64, or provider bodies.

- [ ] **Step 6: Run Task 6 tests**

```powershell
python -m pytest tests/test_classroom_qa_service.py tests/test_classroom_qa_store.py tests/test_classroom_qa_prompt.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 6**

```powershell
git add backend/src/app/services/classroom_qa_tts.py backend/src/app/services/classroom_qa_service.py backend/src/tests/test_classroom_qa_service.py
git commit -m "feat(classroom): answer QA turns with Qwen speech"
```

---

### Task 7: Expose authorized classroom Q&A and audio routes

**Files:**
- Create: `backend/src/app/api/classroom_qa.py`
- Create: `backend/src/tests/test_classroom_qa_routes.py`
- Modify: `backend/src/app/bootstrap.py`

**Interfaces:**
- Consumes: `require_course_read`, Task 3 schemas/store, Task 6 service.
- Produces:

```text
GET  /api/courses/{course_id}/classrooms/{classroom_id}/qa/session
POST /api/courses/{course_id}/classrooms/{classroom_id}/qa/turns
GET  /api/courses/{course_id}/classrooms/{classroom_id}/qa/sessions/{session_id}/audio/{filename}
```

- [ ] **Step 1: Write failing route tests**

Build FastAPI TestClient tests using the existing auth/course fixtures. Assert:

```python
def test_student_can_get_own_session_and_cannot_read_another_students_audio(client, tokens):
    own = client.get(route, headers=bearer(tokens["student_a"]))
    assert own.status_code == 200
    forbidden = client.get(other_audio_route, headers=bearer(tokens["student_b"]))
    assert forbidden.status_code == 404
```

Cover 401, no course read, classroom not visible, blank/overlong question 422, busy 409 with structured detail, stale checkpoint 409, duplicate request 200 with same turn, registered audio 200, unknown filename 404, and `../` path attempts.

- [ ] **Step 2: Run route tests and verify failure**

```powershell
python -m pytest tests/test_classroom_qa_routes.py -q
```

Expected: FAIL because the router is absent.

- [ ] **Step 3: Implement the router**

Use `APIRouter(prefix="/api/courses", tags=["classroom-qa"])`. Every route depends on `require_course_read`. Pass `principal.user_id` into the service/store; never accept owner from request JSON.

Map stable service errors:

```python
except ClassroomQaError as exc:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.public_message, "retryable": exc.retryable},
    ) from exc
```

- [ ] **Step 4: Implement protected audio serving**

Load the owner session first, verify `session_id`, find the exact `audio_filename` in a completed turn, resolve beneath `session_dir/audio`, enforce `path.relative_to(audio_root)`, and return `FileResponse` with stored MIME type. Return 404 for every owner, session, registration, or path failure.

- [ ] **Step 5: Register the router**

Import it in `bootstrap.py` and call `app.include_router(classroom_qa_router)` beside the other course APIs. Do not add routes to the already large `courses.py`.

- [ ] **Step 6: Run Task 7 and existing authorization tests**

```powershell
python -m pytest `
  tests/test_classroom_qa_routes.py `
  tests/test_student_classroom_permissions.py `
  tests/test_course_route_authorization.py `
  -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 7**

```powershell
git add backend/src/app/api/classroom_qa.py backend/src/tests/test_classroom_qa_routes.py backend/src/app/bootstrap.py
git commit -m "feat(api): expose student classroom QA sessions"
```

---

### Task 8: Add the frontend Q&A API and pure state machine

**Files:**
- Create: `frontend/src/stitch/api/classroomQa.ts`
- Create: `frontend/src/stitch/api/classroomQa.test.ts`
- Create: `frontend/src/stitch/classroomQa/classroomQaState.ts`
- Create: `frontend/src/stitch/classroomQa/classroomQaState.test.ts`
- Modify: `frontend/src/stitch/api/types.ts`

**Interfaces:**
- Consumes: Task 7 HTTP contracts and existing `apiRequest`, `apiBlob` patterns.
- Produces:

```ts
export function getClassroomQaSession(courseId: string, classroomId: string): Promise<ClassroomQaSession>;
export function submitClassroomQaTurn(courseId: string, classroomId: string, request: ClassroomQaTurnRequest): Promise<ClassroomQaTurnResponse>;
export function fetchClassroomQaAudioBlobUrl(path: string): Promise<string>;
export function reduceClassroomQa(state: ClassroomQaState, event: ClassroomQaEvent): ClassroomQaState;
```

- [ ] **Step 1: Write failing API path tests**

Extract pure path builders and assert encoded course/classroom/session IDs. Mock fetch to assert Authorization is present for audio fetch and non-2xx responses revoke no URLs.

- [ ] **Step 2: Write failing state transition tests**

```ts
test("a second submit is rejected while a turn is active", () => {
  const submitting = reduceClassroomQa(draftingState, { type: "submit", question: "为什么？" });
  assert.throws(
    () => reduceClassroomQa(submitting, { type: "submit", question: "第二问" }),
    /turn already active/,
  );
});
```

Cover all SPEC-12 §7 transitions, stale async result IDs, retry with the same client turn ID, and reset on navigation.

- [ ] **Step 3: Run Task 8 tests and verify failure**

```powershell
pnpm exec tsx --test src/stitch/api/classroomQa.test.ts src/stitch/classroomQa/classroomQaState.test.ts
```

Expected: FAIL because the modules do not exist.

- [ ] **Step 4: Add exact frontend types**

Mirror snake_case API fields at the network boundary. Do not invent a second camelCase DTO. The orchestration hook may map to view models internally.

- [ ] **Step 5: Implement API and reducer**

Use `apiRequest` for JSON and a dedicated authenticated blob helper patterned after `getClassroom` audio hydration. Return the object URL to the caller; ownership of `URL.revokeObjectURL` belongs to the interruption hook. The GET session request is read-only; the backend returns an in-memory empty session until the first POST turn.

- [ ] **Step 6: Run Task 8 tests**

```powershell
pnpm exec tsx --test src/stitch/api/classroomQa.test.ts src/stitch/classroomQa/classroomQaState.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit Task 8**

```powershell
git add frontend/src/stitch/api/classroomQa.ts frontend/src/stitch/api/classroomQa.test.ts frontend/src/stitch/classroomQa/classroomQaState.ts frontend/src/stitch/classroomQa/classroomQaState.test.ts frontend/src/stitch/api/types.ts
git commit -m "feat(classroom): add QA client state and API"
```

---

### Task 9: Implement the interruption coordinator

**Files:**
- Create: `frontend/src/stitch/classroomQa/useClassroomInterruption.ts`
- Create: `frontend/src/stitch/classroomQa/useClassroomInterruption.test.ts`

**Interfaces:**
- Consumes: Task 2 page controller/runtime, Task 8 API/reducer, browser Audio and SpeechSynthesis adapters.
- Produces:

```ts
export type ClassroomInterruptionController = {
  state: ClassroomQaState;
  openQuestion(): void;
  cancelDraft(): void;
  submitQuestion(question: string): Promise<void>;
  stopAnswerAndResume(): void;
  retry(): Promise<void>;
  closePanel(): void;
};
```

- [ ] **Step 1: Write failing orchestration tests with injected adapters**

```ts
test("open pauses immediately and successful audio resumes exactly once", async () => {
  const harness = createInterruptionHarness();
  harness.controller.openQuestion();
  assert.equal(harness.playback.interruptCalls, 1);

  await harness.controller.submitQuestion("为什么要选基准值？");
  assert.equal(harness.answerAudio.playCalls, 1);
  harness.answerAudio.finish();
  await Promise.resolve();
  assert.equal(harness.playback.resumeCalls, 1);
});
```

Also cover cancel-before-submit, server TTS failed → browser speech, both TTS paths failed → manual resume, stop answer, duplicate audio end events, rejected stale checkpoint, navigation cancellation, response arriving after unmount, and blob revocation.

- [ ] **Step 2: Run the hook test and verify failure**

```powershell
pnpm exec tsx --test src/stitch/classroomQa/useClassroomInterruption.test.ts
```

Expected: FAIL because the hook/coordinator is absent.

- [ ] **Step 3: Implement dependency-injected orchestration core**

Keep the asynchronous workflow in a pure `ClassroomInterruptionCoordinator` class and expose a thin React hook around it. Inject:

```ts
type InterruptionDependencies = {
  playback: Pick<PagePlaybackController, "interrupt" | "resumeInterrupted">;
  loadSession: typeof getClassroomQaSession;
  submitTurn: typeof submitClassroomQaTurn;
  loadAudio: typeof fetchClassroomQaAudioBlobUrl;
  createAudio: (url: string) => AnswerAudioHandle;
  speakBrowser: (text: string) => Promise<"ended" | "failed">;
  createClientTurnId: () => string;
};
```

This keeps browser APIs out of unit tests and makes one-time resume enforceable.

- [ ] **Step 4: Enforce stale-result ownership**

Every async turn captures `{clientTurnId, sceneIndex, pageRevision}`. Before consuming a result or resuming, compare it to the active turn and current page snapshot. Mismatch means cleanup only; no audio and no resume.

- [ ] **Step 5: Run Task 9 tests**

```powershell
pnpm exec tsx --test `
  src/stitch/classroomQa/useClassroomInterruption.test.ts `
  src/stitch/classroomQa/classroomQaState.test.ts `
  src/openmaic/pagePlaybackController.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 9**

```powershell
git add frontend/src/stitch/classroomQa/useClassroomInterruption.ts frontend/src/stitch/classroomQa/useClassroomInterruption.test.ts
git commit -m "feat(classroom): orchestrate QA interruption and resume"
```

---

### Task 10: Add the Q&A panel and integrate it into Classroom Player

**Files:**
- Create: `frontend/src/stitch/classroomQa/ClassroomQaPanel.tsx`
- Create: `frontend/src/stitch/classroomQa/ClassroomQaPanel.css`
- Create: `frontend/src/stitch/classroomQa/ClassroomQaPanel.test.ts`
- Modify: `frontend/src/stitch/pages/ClassroomPlayer.tsx`
- Modify: `frontend/src/stitch/styles.css`

**Interfaces:**
- Consumes: Task 2 runtime-ready callback, Task 9 hook controller.
- Produces: accessible desktop/fullscreen/narrow Q&A experience with no change to no-Q&A playback behavior.

- [ ] **Step 1: Write failing component contract tests**

Since the repository uses Node tests rather than a DOM-heavy component stack, assert the exported presentation model and static component contract:

```ts
test("submitting and answering phases disable the composer", () => {
  assert.equal(toClassroomQaPresentation({ ...state, phase: "submitting" }).canSubmit, false);
  assert.equal(toClassroomQaPresentation({ ...state, phase: "playing_answer" }).canSubmit, false);
  assert.equal(toClassroomQaPresentation({ ...state, phase: "drafting" }).canSubmit, true);
});
```

Add a source contract test asserting `ClassroomPlayer` renders `ClassroomQaPanel`, binds `onRuntimeReady`, and does not hide Q&A in presentation mode.

- [ ] **Step 2: Run component tests and verify failure**

```powershell
pnpm exec tsx --test src/stitch/classroomQa/ClassroomQaPanel.test.ts
```

Expected: FAIL because the panel and integration do not exist.

- [ ] **Step 3: Implement panel behavior**

Required controls and accessibility:

```text
“提问” floating/button entry
dialog/aside labelled “课堂实时问答”
scrollable history with question and answer text
textarea maxLength=1000
取消提问 / 发送
停止回答并继续授课
重试 / 放弃并继续授课
aria-live polite status for drafting/submitting/loading-audio/playing/resuming/error
Escape cancels only an unsent draft; it must not silently discard an active answer
```

- [ ] **Step 4: Integrate the runtime and hook in `ClassroomPlayer`**

Replace the dummy runtime factory with the concrete bind flow from Task 2. Pass `onRuntimeReady` to `ClassroomSceneRenderer`, bind only the current `sceneIndex/revision`, and construct the Q&A hook with `courseId/classroomId`.

Opening the panel calls `controller.interrupt()` before changing focus. Manual previous/play/next controls are disabled while Q&A phase is `submitting | loading_audio | playing_answer | resuming`.

- [ ] **Step 5: Add responsive/fullscreen CSS**

Desktop: a right-side overlay panel no wider than 380px, leaving core stage visible. Presentation mode: compact floating question button and overlay panel inside the fullscreen root. Narrow width: bottom sheet capped at 70vh, with controls above safe-area inset. Do not reuse the teacher “当前页提示” panel because students and teachers both use the shared player.

- [ ] **Step 6: Run Task 10 frontend gates**

```powershell
pnpm exec tsx --test `
  src/stitch/classroomQa/ClassroomQaPanel.test.ts `
  src/stitch/classroomQa/useClassroomInterruption.test.ts `
  src/openmaic/pagePlaybackController.test.ts
pnpm run lint
pnpm run build
```

Expected: tests PASS, lint 0 errors, build success.

- [ ] **Step 7: Commit Task 10**

```powershell
git add frontend/src/stitch/classroomQa/ClassroomQaPanel.tsx frontend/src/stitch/classroomQa/ClassroomQaPanel.css frontend/src/stitch/classroomQa/ClassroomQaPanel.test.ts frontend/src/stitch/pages/ClassroomPlayer.tsx frontend/src/stitch/styles.css
git commit -m "feat(classroom): add realtime student QA panel"
```

---

### Task 11: Run integration, security, regression, and acceptance gates

**Files:**
- Modify: `docs/acceptance/ACC-12_AI课堂实时问答与中断恢复_验收.md`
- Modify: `docs/spec/SPEC-12_AI课堂实时问答与中断恢复.md` only if implementation revealed a contract correction
- Modify: `项目总览地图.md`

**Interfaces:**
- Consumes: all Tasks 1–10 and ACC-12.
- Produces: signed evidence with exact commands, pass counts, real classroom checkpoint IDs, and Qwen TTS proof.

- [ ] **Step 1: Run all focused frontend tests**

```powershell
Set-Location D:\github\edu_ai\Edu_AI
pnpm exec tsx --test `
  src/openmaic/actionEngine.test.ts `
  src/openmaic/playbackEngine.test.ts `
  src/openmaic/pagePlaybackController.test.ts `
  src/stitch/classroomQa/classroomQaState.test.ts `
  src/stitch/classroomQa/useClassroomInterruption.test.ts `
  src/stitch/classroomQa/ClassroomQaPanel.test.ts `
  src/stitch/api/classroomQa.test.ts
```

Expected: exit 0.

- [ ] **Step 2: Run all focused backend tests**

```powershell
Set-Location D:\github\edu_ai\backend\src
python -m pytest `
  tests/test_openmaic_client.py `
  tests/test_classroom_qa_store.py `
  tests/test_classroom_qa_prompt.py `
  tests/test_classroom_qa_service.py `
  tests/test_classroom_qa_routes.py `
  tests/test_student_classroom_permissions.py `
  tests/test_course_route_authorization.py `
  -q
```

Expected: exit 0.

- [ ] **Step 3: Run full frontend gates**

```powershell
Set-Location D:\github\edu_ai\Edu_AI
pnpm test
pnpm run lint
pnpm run build
```

Expected: all commands exit 0; lint has no new warnings attributable to this feature.

- [ ] **Step 4: Run classroom backend regressions**

```powershell
Set-Location D:\github\edu_ai\backend\src
python -m pytest `
  tests/test_classroom_media.py `
  tests/test_classroom_persistence.py `
  tests/test_classroom_service.py `
  tests/test_classroom_validation.py `
  tests/app/test_legacy_services_retired.py `
  -q
```

Expected: exit 0.

- [ ] **Step 5: Run the retired-stack static gate**

```powershell
Set-Location D:\github\edu_ai
rg -n -S "LiveTalking|teaching_video_bridge|ai_lecturer_bridge|RTCPeerConnection" frontend/src backend/src/app .env.example backend/src/.env.example
```

Expected: no new runtime dependency; document any pre-existing retirement assertion hit.

- [ ] **Step 6: Perform ACC-12 real-browser scenarios**

Execute ACC-12 §5.1–§5.6 with two student accounts and a real multi-speech classroom. Record the course ID, classroom ID, scene ID, action ID, sentence-middle behavior, between-sentence behavior, isolation result, degraded TTS result, and layout result.

- [ ] **Step 7: Capture Qwen TTS evidence**

Record a sidecar log or trace tied to the browser turn:

```text
provider=qwen-tts
audioId=turn_<id>
tts_status=ready
```

Confirm the browser fetches only the edu_ai protected audio route and never consumes a sidecar temporary URL.

- [ ] **Step 8: Update and self-review acceptance evidence**

Append a dated ACC-12 signing section with commit hash, exact command results, pass counts, real IDs, TTS evidence, and known non-blocking limitations. Change ACC-12 status to “通过” and SPEC-12 status to “完成” only if every required item passes.

Search the spec and acceptance files for unfinished-marker terms and remove any unresolved implementation marker. Pre-implementation status words that were replaced during signing must be absent.

- [ ] **Step 9: Update the project map**

Add the completed realtime Q&A path under the OpenMAIC classroom product mainline and state explicitly that it uses text input + Qwen TTS without restoring digital-human services.

- [ ] **Step 10: Commit Task 11**

```powershell
git add docs/acceptance/ACC-12_AI课堂实时问答与中断恢复_验收.md docs/spec/SPEC-12_AI课堂实时问答与中断恢复.md 项目总览地图.md
git commit -m "docs(classroom): sign realtime QA acceptance"
```

---

## Plan Self-Review

- **Spec coverage:** Tasks 1–2 cover precise interruption and recovery; Tasks 3–7 cover isolation, trusted context, Agent, Qwen TTS, APIs, security, idempotency, and persistence; Tasks 8–10 cover client state, orchestration, UI, fullscreen, cleanup, and fallback; Task 11 covers regression and evidence.
- **Boundary check:** No task restores retired AI Lecturer code, modifies exported classroom material, or couples the feature to the in-progress PostgreSQL foundation.
- **Type consistency:** `PlaybackCheckpoint` is created by `PlaybackEngine`, decorated as `PagePlaybackCheckpoint` by the page controller, serialized as the snake_case `ClassroomQaCheckpoint` API DTO, and used only as trusted identifiers by the backend.
- **Failure consistency:** Qwen TTS failure is degraded success with answer text; LLM failure is a retryable failed turn; stale checkpoint and every concurrent unfinished turn are stable 409 errors.
- **Execution order:** Each task consumes only interfaces produced by earlier tasks and ends with a focused test gate and isolated commit.
