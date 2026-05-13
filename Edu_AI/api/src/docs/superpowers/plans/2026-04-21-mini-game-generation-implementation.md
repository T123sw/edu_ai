# Mini-Game Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new teacher workbench feature that generates one of three knowledge-base mini-games, previews it inside the workbench, opens the generated HTML in a dedicated play page, and persists the game as a course material.

**Architecture:** Add a new backend direct-generation pipeline under `/api/chat/v2/game/direct` that maps a user-selected `game_type` to a local HTML template and JSON schema, generates validated structured game data from selected documents, renders a stored standalone HTML file, and returns a `game` artifact with an authenticated `html_url`. On the frontend, add a dedicated game entry modal, parse `game` artifacts into `GeneratedFile`, preview them in an iframe-based `GameArtifactPreview`, and reopen persisted games from course materials without regenerating them.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, TypeScript, React, Ant Design, Zustand, Node test runner, existing `app.chat` v2 services

---

## File Structure

### Create

- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/game_template_registry.py`
  Purpose: define the three supported game types and map them to local HTML template and schema files under `dynamic-templates/games`.
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_direct_game_service_v2.py`
  Purpose: generate validated mini-game artifacts from selected knowledge-base documents, render standalone HTML, and persist course materials.
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_knowledge_base_direct_game_service_v2.py`
  Purpose: lock backend game generation, schema validation retry behavior, and persistence wiring.
- `D:/Edu_AI_1/Edu_AI/src/components/teacher/GameEntryModal.tsx`
  Purpose: let the teacher choose one of the three supported mini-games before generation.
- `D:/Edu_AI_1/Edu_AI/src/components/teacher/GameArtifactPreview.tsx`
  Purpose: preview generated game HTML inside the workbench and expose the “全屏播放” action.
- `D:/Edu_AI_1/Edu_AI/tests/frontend/studioPanel.game-entry.test.ts`
  Purpose: assert the workbench exposes the game entry flow and wires the new modal and direct API call.
- `D:/Edu_AI_1/Edu_AI/tests/frontend/gameArtifactPreview.test.ts`
  Purpose: assert the preview component loads an iframe and opens the standalone HTML URL for play mode.

### Modify

- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
  Purpose: add request and response models for direct game generation.
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
  Purpose: add the game direct POST route, authenticated HTML-serving GET route, and local path helpers.
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`
  Purpose: lock the new routes and response payloads.
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`
  Purpose: lock the new Pydantic request and response contracts.
- `D:/Edu_AI_1/Edu_AI/src/services/teacher/chatV2.ts`
  Purpose: add frontend request/response types and the `generateKnowledgeBaseGameV2` API helper.
- `D:/Edu_AI_1/Edu_AI/src/services/teacher/chatV2.helpers.ts`
  Purpose: parse `game` artifacts into `GeneratedFile` instances.
- `D:/Edu_AI_1/Edu_AI/src/services/teacher/materials.helpers.ts`
  Purpose: restore persisted `game` course materials into previewable generated files.
- `D:/Edu_AI_1/Edu_AI/src/store/teacher/useStore.ts`
  Purpose: extend `GeneratedFile['type']` to include `game`.
- `D:/Edu_AI_1/Edu_AI/src/components/teacher/StudioPanel.tsx`
  Purpose: expose the game generation card, open the modal, submit direct generation, and route preview rendering to `GameArtifactPreview`.

---

### Task 1: Extend The Game API Contract And Routes

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`

- [ ] **Step 1: Write the failing schema tests**

```python
def test_game_direct_request_requires_supported_game_type():
    payload = KnowledgeBaseDirectGameRequestV2(
        course_id="course-1",
        selected_doc_ids=["doc-1"],
        game_type="drag_match",
    )

    assert payload.game_type == "drag_match"
    assert payload.selected_doc_ids == ["doc-1"]


def test_game_direct_response_accepts_game_artifact_payload():
    response = ChatDirectGameResponseV2(
        action={"name": "generate.game.direct"},
        artifacts=[
            {
                "artifact_id": "game-1",
                "artifact_type": "game",
                "title": "历史概念配对.html",
                "content": {
                    "game_type": "drag_match",
                    "template_id": "drag-match",
                    "game_data": {"title": "历史概念配对", "pairs": []},
                    "html_url": "/api/chat/v2/games/html?path=u1/course-1/game-1/index.html",
                },
            }
        ],
        trace={"path": "direct"},
    )

    assert response.action["name"] == "generate.game.direct"
    assert response.artifacts[0]["artifact_type"] == "game"
    assert response.artifacts[0]["content"]["html_url"].startswith("/api/chat/v2/games/html")
```

- [ ] **Step 2: Run schema tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_schemas_v2.py -q
```

Expected: FAIL because `KnowledgeBaseDirectGameRequestV2` and `ChatDirectGameResponseV2` do not exist yet.

- [ ] **Step 3: Add the minimal schema models**

```python
GameType = Literal["category_sort", "drag_match", "memory_flip"]


class KnowledgeBaseDirectGameRequestV2(BaseModel):
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    selected_doc_ids: List[str] = Field(default_factory=list)
    game_type: GameType


class ChatDirectGameResponseV2(BaseModel):
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    trace: DirectTraceMetaV2
```

- [ ] **Step 4: Write the failing route tests**

```python
def test_game_direct_route_returns_game_artifact(monkeypatch):
    class DummyService:
        def generate(self, payload):
            return {
                "action": {"name": "generate.game.direct"},
                "artifacts": [
                    {
                        "artifact_id": "game-1",
                        "artifact_type": "game",
                        "title": "历史概念配对.html",
                        "content": {
                            "game_type": "drag_match",
                            "template_id": "drag-match",
                            "game_data": {"title": "历史概念配对", "pairs": []},
                            "html_url": "/api/chat/v2/games/html?path=tester/course-1/game-1/index.html",
                        },
                    }
                ],
                "trace": {"path": "direct"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_direct_game_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/game/direct",
        json={"course_id": "course-1", "selected_doc_ids": ["doc-1"], "game_type": "drag_match"},
    )

    assert response.status_code == 200
    assert response.json()["artifacts"][0]["artifact_type"] == "game"


def test_game_html_route_uses_authenticated_path_resolution(monkeypatch, tmp_path):
    owner_dir = tmp_path / "tester" / "course-1" / "game-1"
    owner_dir.mkdir(parents=True)
    html_path = owner_dir / "index.html"
    html_path.write_text("<html><body>game</body></html>", encoding="utf-8")

    monkeypatch.setattr("app.chat.api.routes_v2._chat_games_root", lambda: tmp_path)
    client = TestClient(app)
    response = client.get("/api/chat/v2/games/html", params={"path": "tester/course-1/game-1/index.html"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
```

- [ ] **Step 5: Run route tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py -q
```

Expected: FAIL because `/api/chat/v2/game/direct` and `/api/chat/v2/games/html` are not registered.

- [ ] **Step 6: Add the minimal route wiring and storage-path helpers**

```python
def _get_direct_game_service():
    from app.chat.application.knowledge_base_direct_game_service_v2 import (
        build_default_knowledge_base_direct_game_service_v2,
    )

    return build_default_knowledge_base_direct_game_service_v2()


def _chat_games_root() -> Path:
    root = (Config.STORAGE_ROOT / "chat_games").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _build_chat_game_url(relative_path: str) -> str:
    return f"/api/chat/v2/games/html?path={quote(relative_path, safe='')}"


def _resolve_chat_game_path(*, owner: str, relative_path: str) -> Path:
    root = _chat_games_root()
    requested = (root / str(relative_path or "")).resolve()
    expected_owner_root = (root / _safe_segment(owner, "anonymous")).resolve()
    if not str(requested).startswith(str(expected_owner_root)):
        raise HTTPException(status_code=403, detail="forbidden_game_path")
    if not requested.exists() or not requested.is_file():
        raise HTTPException(status_code=404, detail="game_not_found")
    return requested


@router.post("/game/direct", response_model=ChatDirectGameResponseV2)
async def direct_game(payload: KnowledgeBaseDirectGameRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_direct_game_service().generate(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id="",
            trace_path="direct",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


@router.get("/games/html")
async def get_chat_game(path: str = Query(...), current_user: dict = Depends(get_current_user)):
    owner = str(current_user.get("username") or "")
    resolved = _resolve_chat_game_path(owner=owner, relative_path=unquote(path))
    return FileResponse(path=str(resolved), media_type="text/html", filename=resolved.name)
```

- [ ] **Step 7: Run the contract tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_schemas_v2.py D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py -q
```

Expected: PASS with the new game schema and route contracts in place.

- [ ] **Step 8: Commit**

```powershell
git add D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py
git commit -m "feat: add mini game API contract and routes"
```

---

### Task 2: Implement Backend Game Generation, Validation, And Persistence

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/game_template_registry.py`
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_direct_game_service_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_knowledge_base_direct_game_service_v2.py`

- [ ] **Step 1: Write the failing backend service tests**

```python
def test_direct_game_service_generates_drag_match_artifact(tmp_path):
    service = KnowledgeBaseDirectGameServiceV2(
        content_provider=StubContentProvider(),
        llm=StubLlm([
            '{"title":"历史概念配对","pairs":[{"id":"p1","left":"郡县制","right":"中央直接任免地方官的制度"}]}'
        ]),
        course_storage_manager=StubCourseStorageManager(),
        storage_root=tmp_path,
    )

    result = service.generate(
        SimpleNamespace(
            selected_doc_ids=["doc-1"],
            game_type="drag_match",
            course_id="course-1",
            scope_type="course",
            scope_id="course-1",
            owner="tester",
        )
    )

    artifact = result["artifacts"][0]
    assert artifact["artifact_type"] == "game"
    assert artifact["content"]["template_id"] == "drag-match"
    assert artifact["content"]["html_url"].startswith("/api/chat/v2/games/html")


def test_direct_game_service_retries_once_when_schema_validation_fails(tmp_path):
    service = KnowledgeBaseDirectGameServiceV2(
        content_provider=StubContentProvider(),
        llm=StubLlm([
            '{"title":"历史概念配对","pairs":[{"id":"p1","left":"郡县制"}]}',
            '{"title":"历史概念配对","pairs":[{"id":"p1","left":"郡县制","right":"中央直接任免地方官的制度"}]}',
        ]),
        course_storage_manager=StubCourseStorageManager(),
        storage_root=tmp_path,
    )

    result = service.generate(
        SimpleNamespace(selected_doc_ids=["doc-1"], game_type="drag_match", course_id="course-1", owner="tester")
    )

    assert result["artifacts"][0]["content"]["game_data"]["pairs"][0]["right"] == "中央直接任免地方官的制度"


def test_direct_game_service_raises_after_second_invalid_payload(tmp_path):
    service = KnowledgeBaseDirectGameServiceV2(
        content_provider=StubContentProvider(),
        llm=StubLlm([
            '{"title":"翻牌记忆","matches":[{"pair_id":"m1","card_a":"光合作用"}]}',
            '{"title":"翻牌记忆","matches":[{"pair_id":"m1","card_a":"光合作用"}]}',
        ]),
        course_storage_manager=StubCourseStorageManager(),
        storage_root=tmp_path,
    )

    with pytest.raises(ValueError, match="game_generation_invalid_schema"):
        service.generate(SimpleNamespace(selected_doc_ids=["doc-1"], game_type="memory_flip", owner="tester"))
```

- [ ] **Step 2: Run the backend service tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_knowledge_base_direct_game_service_v2.py -q
```

Expected: FAIL because the registry and direct game service do not exist yet.

- [ ] **Step 3: Add the template registry**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameTemplateSpec:
    game_type: str
    template_id: str
    display_name: str
    html_template_path: Path
    schema_path: Path


_BASE_DIR = Path(__file__).resolve().parents[2] / "dynamic-templates" / "games"

_GAME_TEMPLATES = {
    "category_sort": GameTemplateSpec(
        game_type="category_sort",
        template_id="category-sort",
        display_name="分类归纳",
        html_template_path=_BASE_DIR / "category-sort.html",
        schema_path=_BASE_DIR / "category-sort.schema.json",
    ),
    "drag_match": GameTemplateSpec(
        game_type="drag_match",
        template_id="drag-match",
        display_name="拖拽配对",
        html_template_path=_BASE_DIR / "drag-match.html",
        schema_path=_BASE_DIR / "drag-match.schema.json",
    ),
    "memory_flip": GameTemplateSpec(
        game_type="memory_flip",
        template_id="memory-flip",
        display_name="翻牌记忆",
        html_template_path=_BASE_DIR / "memory-flip.html",
        schema_path=_BASE_DIR / "memory-flip.schema.json",
    ),
}


def get_game_template_spec(game_type: str) -> GameTemplateSpec:
    try:
        return _GAME_TEMPLATES[str(game_type or "").strip()]
    except KeyError as exc:
        raise ValueError("unsupported_game_type") from exc
```

- [ ] **Step 4: Implement the direct game service**

```python
class KnowledgeBaseDirectGameServiceV2:
    def __init__(self, *, content_provider=None, llm=None, course_storage_manager=None, storage_root=None):
        self.content_provider = content_provider or KnowledgeBaseDocumentContentProvider()
        self.llm = llm or get_fallback_llm()
        self.course_storage_manager = course_storage_manager or default_course_storage_manager
        self.storage_root = Path(storage_root or (Config.STORAGE_ROOT / "chat_games"))

    def generate(self, payload):
        selected_doc_ids = [_clean(item) for item in list(getattr(payload, "selected_doc_ids", []) or []) if _clean(item)]
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")
        if self.llm is None:
            raise RuntimeError("game_llm_unavailable")

        template = get_game_template_spec(_clean(getattr(payload, "game_type", "")))
        documents = self._load_documents(selected_doc_ids=selected_doc_ids, owner=_clean(getattr(payload, "owner", "")) or None)
        game_data = self._generate_validated_game_data(template=template, documents=documents)
        html_relative_path, html_url = self._render_html(
            owner=_clean(getattr(payload, "owner", "")) or "anonymous",
            course_id=_clean(getattr(payload, "course_id", "")) or "direct",
            artifact_id=f"game-{uuid4().hex[:12]}",
            template=template,
            game_data=game_data,
        )
        artifact = {
            "artifact_id": Path(html_relative_path).parts[-2],
            "artifact_type": "game",
            "title": f"{game_data.get('title') or template.display_name}.html",
            "content": {
                "game_type": template.game_type,
                "template_id": template.template_id,
                "game_data": game_data,
                "html_path": html_relative_path,
                "html_url": html_url,
            },
            "generation_state": {
                "status": "completed",
                "mode": "knowledge_base_direct",
                "selected_doc_count": len(selected_doc_ids),
            },
        }
        self._persist_game(payload=payload, artifact=artifact, selected_doc_ids=selected_doc_ids, documents=documents)
        return {
            "action": {"name": "generate.game.direct"},
            "artifacts": [artifact],
            "trace": {"path": "direct", "generation_mode": "knowledge_base_direct_game", "selected_doc_count": len(selected_doc_ids), "content_doc_count": len(documents)},
        }
```

- [ ] **Step 5: Add validation retry and HTML rendering helpers**

```python
    def _generate_validated_game_data(self, *, template, documents):
        schema = json.loads(template.schema_path.read_text(encoding="utf-8"))
        messages = self._build_generate_messages(template=template, documents=documents, schema=schema)
        first_text = _extract_text_from_response(self.llm.invoke(messages))
        try:
            return self._parse_and_validate_json(first_text, schema=schema)
        except ValueError as exc:
            repair_messages = self._build_repair_messages(template=template, documents=documents, schema=schema, invalid_json=first_text, error_text=str(exc))
            second_text = _extract_text_from_response(self.llm.invoke(repair_messages))
            try:
                return self._parse_and_validate_json(second_text, schema=schema)
            except ValueError as repair_exc:
                raise ValueError("game_generation_invalid_schema") from repair_exc

    def _render_html(self, *, owner, course_id, artifact_id, template, game_data):
        owner_segment = _safe_segment(owner, "anonymous")
        course_segment = _safe_segment(course_id, "direct")
        target_dir = self.storage_root / owner_segment / course_segment / artifact_id
        target_dir.mkdir(parents=True, exist_ok=True)
        html = template.html_template_path.read_text(encoding="utf-8").replace(
            "__GAME_DATA_JSON__",
            json.dumps(game_data, ensure_ascii=False),
        )
        target_path = target_dir / "index.html"
        target_path.write_text(html, encoding="utf-8")
        relative_path = target_path.relative_to(self.storage_root).as_posix()
        return relative_path, f"/api/chat/v2/games/html?path={quote(relative_path, safe='')}"
```

- [ ] **Step 6: Run backend tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_knowledge_base_direct_game_service_v2.py D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py -q
```

Expected: PASS, including the one-retry schema repair behavior and generated `html_url`.

- [ ] **Step 7: Commit**

```powershell
git add D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/game_template_registry.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_direct_game_service_v2.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_knowledge_base_direct_game_service_v2.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py
git commit -m "feat: implement direct mini game generation service"
```

---

### Task 3: Extend Frontend API Types And Artifact Parsing

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/src/services/teacher/chatV2.ts`
- Modify: `D:/Edu_AI_1/Edu_AI/src/services/teacher/chatV2.helpers.ts`
- Modify: `D:/Edu_AI_1/Edu_AI/src/services/teacher/materials.helpers.ts`
- Modify: `D:/Edu_AI_1/Edu_AI/src/store/teacher/useStore.ts`
- Create: `D:/Edu_AI_1/Edu_AI/tests/frontend/gameArtifactPreview.test.ts`

- [ ] **Step 1: Write the failing helper test for `game` artifact parsing**

```ts
import assert from 'node:assert/strict';
import { extractGeneratedFilesFromV2Response } from '../../src/services/teacher/chatV2.helpers.ts';

const files = extractGeneratedFilesFromV2Response({
  artifacts: [
    {
      artifact_id: 'game-1',
      artifact_type: 'game',
      title: '历史概念配对.html',
      content: {
        game_type: 'drag_match',
        template_id: 'drag-match',
        game_data: { title: '历史概念配对', pairs: [] },
        html_url: '/api/chat/v2/games/html?path=tester/course-1/game-1/index.html',
      },
      generation_state: { status: 'completed' },
    },
  ],
});

assert.equal(files.length, 1);
assert.equal(files[0].type, 'game');
assert.equal(files[0].meta?.htmlUrl, '/api/chat/v2/games/html?path=tester/course-1/game-1/index.html');
assert.equal(files[0].meta?.gameType, 'drag_match');
```

- [ ] **Step 2: Run the helper test to verify it fails**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\gameArtifactPreview.test.ts
```

Expected: FAIL because `game` artifacts are not yet parsed and `GeneratedFile['type']` does not include `game`.

- [ ] **Step 3: Add the frontend request, response, and store types**

```ts
export type GameTypeV2 = 'category_sort' | 'drag_match' | 'memory_flip';

export interface KnowledgeBaseDirectGameRequestV2 {
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids?: string[];
  game_type: GameTypeV2;
}

export interface ChatDirectGameResponseV2 {
  action: { name: string };
  artifacts: Array<Record<string, unknown>>;
  trace: Record<string, unknown>;
}

export async function generateKnowledgeBaseGameV2(
  payload: KnowledgeBaseDirectGameRequestV2,
): Promise<ChatDirectGameResponseV2> {
  return postV2<ChatDirectGameResponseV2, KnowledgeBaseDirectGameRequestV2>('/api/chat/v2/game/direct', payload);
}
```

```ts
export interface GeneratedFile {
  id: string;
  name: string;
  type: 'report' | 'ppt' | 'quiz' | 'blog' | 'lesson_plan' | 'audio' | 'graph' | 'video' | 'ai_lecture_session' | 'flashcard' | 'game';
  content?: any;
  meta?: Record<string, unknown>;
}
```

- [ ] **Step 4: Add `game` artifact parsing and course-material restoration**

```ts
function mergeGameArtifacts(artifacts: V2ArtifactLike[]): GeneratedFileLike[] {
  const gameArtifact = artifacts.find((artifact) => String(artifact.artifact_type || '').trim() === 'game');
  if (!gameArtifact) {
    return [];
  }

  const artifactId = normalizeGeneratedFileId(String(gameArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
  const content = gameArtifact.content && typeof gameArtifact.content === 'object'
    ? (gameArtifact.content as Record<string, unknown>)
    : {};

  return [
    {
      id: artifactId,
      name: String(gameArtifact.title || '小游戏.html').trim() || '小游戏.html',
      type: 'game',
      content,
      meta: {
        kind: 'game',
        htmlUrl: String(content.html_url || '').trim() || undefined,
        gameType: String(content.game_type || '').trim() || undefined,
        templateId: String(content.template_id || '').trim() || undefined,
        originalArtifactId: String(gameArtifact.artifact_id || '').trim() || undefined,
        generationState: gameArtifact.generation_state && typeof gameArtifact.generation_state === 'object'
          ? gameArtifact.generation_state
          : undefined,
      },
    },
  ];
}
```

```ts
if (type === 'game') {
  return {
    id,
    name: String(material.name || '小游戏.html'),
    type: 'game',
    content: material.content,
    meta: {
      origin: 'course_material',
      courseId: material.courseId,
      scopeType: material.scopeType,
      scopeId: material.scopeId,
      isPinned: Boolean(material.isPinned),
      pinnedAt: material.pinnedAt,
      addedAt: material.addedAt,
      kind: 'game',
      htmlUrl: String((material.content as any)?.html_url || '').trim() || undefined,
      gameType: String((material.content as any)?.game_type || '').trim() || undefined,
      templateId: String((material.content as any)?.template_id || '').trim() || undefined,
      originalArtifactId: id,
      generationState: material.generationState && typeof material.generationState === 'object'
        ? material.generationState
        : undefined,
    },
  };
}
```

- [ ] **Step 5: Run the helper test to verify it passes**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\gameArtifactPreview.test.ts
```

Expected: PASS with `game` artifacts parsed into previewable generated files.

- [ ] **Step 6: Commit**

```powershell
git add D:/Edu_AI_1/Edu_AI/src/services/teacher/chatV2.ts D:/Edu_AI_1/Edu_AI/src/services/teacher/chatV2.helpers.ts D:/Edu_AI_1/Edu_AI/src/services/teacher/materials.helpers.ts D:/Edu_AI_1/Edu_AI/src/store/teacher/useStore.ts D:/Edu_AI_1/Edu_AI/tests/frontend/gameArtifactPreview.test.ts
git commit -m "feat: parse mini game artifacts on the frontend"
```

---

### Task 4: Add The Game Entry Modal And StudioPanel Generation Flow

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/src/components/teacher/GameEntryModal.tsx`
- Modify: `D:/Edu_AI_1/Edu_AI/src/components/teacher/StudioPanel.tsx`
- Create: `D:/Edu_AI_1/Edu_AI/tests/frontend/studioPanel.game-entry.test.ts`

- [ ] **Step 1: Write the failing StudioPanel entry-flow test**

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');
const gameEntryModal = readFileSync(new URL('../../src/components/teacher/GameEntryModal.tsx', import.meta.url), 'utf8');

assert.match(studioPanel, /type:\s*'game'/, 'StudioPanel should expose a dedicated game generation action');
assert.match(studioPanel, /setGameEntryVisible\(true\)/, 'StudioPanel should open the game entry modal for game generation');
assert.match(studioPanel, /generateKnowledgeBaseGameV2\(/, 'StudioPanel should call the direct mini game API');
assert.match(studioPanel, /<GameEntryModal/, 'StudioPanel should render the game entry modal');

assert.match(gameEntryModal, /category_sort/, 'GameEntryModal should list the category sort option');
assert.match(gameEntryModal, /drag_match/, 'GameEntryModal should list the drag match option');
assert.match(gameEntryModal, /memory_flip/, 'GameEntryModal should list the memory flip option');
assert.match(gameEntryModal, /生成小游戏/, 'GameEntryModal should expose the submit CTA');
```

- [ ] **Step 2: Run the StudioPanel test to verify it fails**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\studioPanel.game-entry.test.ts
```

Expected: FAIL because the modal, action card, and generation handler do not exist yet.

- [ ] **Step 3: Create the game entry modal**

```tsx
const GAME_OPTIONS: Array<{ value: GameTypeV2; title: string; description: string; sampleUseCase: string }> = [
  { value: 'category_sort', title: '分类归纳', description: '把知识点拖入正确类别中。', sampleUseCase: '适合章节概念、史实归类、语法分类。' },
  { value: 'drag_match', title: '拖拽配对', description: '把概念和定义、人物和事件配对。', sampleUseCase: '适合术语释义、人物事件、公式含义。' },
  { value: 'memory_flip', title: '翻牌记忆', description: '通过翻牌找到知识点对应关系。', sampleUseCase: '适合术语记忆、英汉对应、定义复习。' },
];

export default function GameEntryModal({ open, selectedDocIds, submitting = false, onCancel, onSubmit }: Props) {
  const [selectedGameType, setSelectedGameType] = useState<GameTypeV2 | null>(null);
  const canSubmit = selectedDocIds.length > 0 && Boolean(selectedGameType);

  return (
    <Modal title="生成小游戏" open={open} onCancel={onCancel} footer={null} width={760} destroyOnClose>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Alert type={selectedDocIds.length > 0 ? 'info' : 'warning'} showIcon message={selectedDocIds.length > 0 ? `已选 ${selectedDocIds.length} 份资料，请选择一种小游戏。` : '请先勾选至少一份知识库文档。'} />
        <div className="game-entry-modal__grid">
          {GAME_OPTIONS.map((option) => (
            <button key={option.value} type="button" className={`game-entry-modal__card${selectedGameType === option.value ? ' is-selected' : ''}`} onClick={() => setSelectedGameType(option.value)}>
              <span className="game-entry-modal__title">{option.title}</span>
              <span className="game-entry-modal__description">{option.description}</span>
              <span className="game-entry-modal__sample">{option.sampleUseCase}</span>
            </button>
          ))}
        </div>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Button onClick={onCancel} disabled={submitting}>取消</Button>
          <Button type="primary" disabled={!canSubmit} loading={submitting} onClick={() => selectedGameType && onSubmit({ gameType: selectedGameType })}>生成小游戏</Button>
        </Space>
      </Space>
    </Modal>
  );
}
```

- [ ] **Step 4: Wire StudioPanel to the new direct game flow**

```tsx
import GameEntryModal from './GameEntryModal';
import { generateKnowledgeBaseGameV2, type GameTypeV2 } from '../../services/teacher/chatV2';

const STUDIO_ACTIONS = [
  // existing actions...
  {
    type: 'game' as const,
    icon: <PlayCircleOutlined />,
    title: '小游戏生成',
    description: '把当前资料快速转成可预览、可播放的互动小游戏。',
    color: '#2f8f6b',
    featured: false,
  },
];

const [gameEntryVisible, setGameEntryVisible] = useState(false);

const handleGameEntrySubmit = async ({ gameType }: { gameType: GameTypeV2 }) => {
  setGenerating(true);
  try {
    const response = await generateKnowledgeBaseGameV2({
      course_id: courseId,
      scope_type: workspaceScopeApiParams.scopeType,
      scope_id: workspaceScopeApiParams.scopeId,
      selected_doc_ids: selectedDocs,
      game_type: gameType,
    });

    const generatedGameFiles = extractGeneratedFilesFromV2Response(response).map((file) => ({
      ...file,
      meta: {
        ...(file.meta || {}),
        origin: 'knowledge_base_direct',
        entryMode: 'knowledge_base_game',
      },
    }));

    generatedGameFiles.forEach((file) => addGeneratedFile(file as GeneratedFile));
    if (generatedGameFiles.length > 0) {
      const latestFile = generatedGameFiles[generatedGameFiles.length - 1] as GeneratedFile;
      setViewingFile(latestFile);
      if (courseId) {
        addMaterial({ ...latestFile, addedAt: new Date().toISOString(), courseId });
        await refreshCourseMaterials();
      }
    }
    setGameEntryVisible(false);
    message.success(generatedGameFiles.length > 0 ? '小游戏已生成并在右侧打开。' : '小游戏生成任务已启动。');
  } catch (error: any) {
    message.error(`小游戏生成失败: ${error.message || '未知错误'}`);
    throw error;
  } finally {
    setGenerating(false);
  }
};
```

- [ ] **Step 5: Run the StudioPanel test to verify it passes**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\studioPanel.game-entry.test.ts
```

Expected: PASS with the action card, modal render, and direct game API wiring in place.

- [ ] **Step 6: Commit**

```powershell
git add D:/Edu_AI_1/Edu_AI/src/components/teacher/GameEntryModal.tsx D:/Edu_AI_1/Edu_AI/src/components/teacher/StudioPanel.tsx D:/Edu_AI_1/Edu_AI/tests/frontend/studioPanel.game-entry.test.ts
git commit -m "feat: add mini game entry flow to StudioPanel"
```

---

### Task 5: Add Game Preview Rendering And Course-Material Reopen Support

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/src/components/teacher/GameArtifactPreview.tsx`
- Modify: `D:/Edu_AI_1/Edu_AI/src/components/teacher/StudioPanel.tsx`
- Modify: `D:/Edu_AI_1/Edu_AI/tests/frontend/gameArtifactPreview.test.ts`

- [ ] **Step 1: Write the failing preview test**

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const preview = readFileSync(new URL('../../src/components/teacher/GameArtifactPreview.tsx', import.meta.url), 'utf8');
const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(preview, /iframe/, 'GameArtifactPreview should render an iframe for HTML preview');
assert.match(preview, /全屏播放/, 'GameArtifactPreview should expose a play-mode button');
assert.match(preview, /window\.open\(/, 'GameArtifactPreview should open the standalone HTML URL');
assert.match(studioPanel, /viewingFile\.type === 'game'/, 'StudioPanel should route game files into the dedicated preview');
assert.match(studioPanel, /<GameArtifactPreview/, 'StudioPanel should render GameArtifactPreview for game files');
```

- [ ] **Step 2: Run the preview test to verify it fails**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\gameArtifactPreview.test.ts
```

Expected: FAIL because the preview component and `viewingFile.type === 'game'` branch do not exist yet.

- [ ] **Step 3: Create the iframe-based preview component**

```tsx
export default function GameArtifactPreview({ file, onBack, onToggleCollapsed }: Props) {
  const htmlUrl = String(file.meta?.htmlUrl || '').trim();

  return (
    <div className="studio-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack} style={{ marginLeft: -12 }}>返回</Button>
        <Space>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            disabled={!htmlUrl}
            onClick={() => htmlUrl && window.open(htmlUrl, '_blank', 'noopener,noreferrer')}
          >
            全屏播放
          </Button>
          <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作台" />
        </Space>
      </div>
      <Title level={4} style={{ marginTop: 8 }}>{file.name}</Title>
      <Divider />
      {htmlUrl ? (
        <iframe title={file.name} src={htmlUrl} style={{ width: '100%', flex: 1, minHeight: 0, border: '1px solid #f0f0f0', borderRadius: 16, background: '#fff' }} />
      ) : (
        <Alert type="warning" showIcon message="页面资源不存在，请重新生成小游戏。" />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Route `game` files into the preview component**

```tsx
import GameArtifactPreview from './GameArtifactPreview';

if (viewingFile.type === 'game') {
  return (
    <GameArtifactPreview
      file={viewingFile}
      onBack={() => setViewingFile(null)}
      onToggleCollapsed={onToggleCollapsed}
    />
  );
}
```

- [ ] **Step 5: Run the preview test to verify it passes**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\gameArtifactPreview.test.ts
```

Expected: PASS with iframe preview and standalone play-page opening in place.

- [ ] **Step 6: Run the full targeted verification suite**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_schemas_v2.py D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_knowledge_base_direct_game_service_v2.py -q
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\studioPanel.game-entry.test.ts D:\Edu_AI_1\Edu_AI\tests\frontend\gameArtifactPreview.test.ts
```

Expected: PASS for all targeted backend and frontend mini-game tests.

- [ ] **Step 7: Commit**

```powershell
git add D:/Edu_AI_1/Edu_AI/src/components/teacher/GameArtifactPreview.tsx D:/Edu_AI_1/Edu_AI/src/components/teacher/StudioPanel.tsx D:/Edu_AI_1/Edu_AI/tests/frontend/gameArtifactPreview.test.ts
git commit -m "feat: add mini game preview in the workbench"
```

---

## Self-Review

### Spec coverage

- Workbench entry card: covered by Task 4.
- Three fixed game templates: covered by Task 2 registry and Task 4 modal.
- Direct backend generation only: covered by Task 1 route contract and Task 2 service.
- Schema validation with one repair retry: covered by Task 2 tests and service helpers.
- Standalone HTML generation and authenticated HTML serving: covered by Tasks 1 and 2.
- Workbench iframe preview: covered by Task 5.
- “全屏播放” opening the standalone HTML page: covered by Task 5.
- Persistence into course materials and reopen behavior: covered by Tasks 2 and 3.

No spec gaps found.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every code-changing step includes concrete code snippets.
- Every test step includes an exact command and expected outcome.

### Type consistency

- Backend request type uses `game_type` and frontend request mirrors the same name.
- Supported values stay consistent across spec and plan: `category_sort`, `drag_match`, `memory_flip`.
- Artifact parsing consistently uses `artifact_type = 'game'`, frontend `type = 'game'`, and `meta.htmlUrl`.

No naming inconsistencies found.
