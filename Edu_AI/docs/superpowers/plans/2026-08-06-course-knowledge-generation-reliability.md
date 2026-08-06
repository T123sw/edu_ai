# Course Knowledge, Generation Sources, and Job Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make course knowledge a dependable source of truth for all nine generation workflows, allow generation with automatic course context, selected documents, or no document context, and ensure one slow task cannot block the generation queue.

**Architecture:** Keep the course knowledge base as the canonical document store and make the knowledge graph a structural view whose evidence points back to those documents. Add a single source-resolution service that translates public course document IDs into ready RAG indexes before any generator runs. Carry an immutable source snapshot through durable jobs and artifacts. Replace the single durable worker with a bounded pool, explicit deadlines, and deterministic cancellation/recovery rules.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLite task store, filesystem course store, pytest, React/TypeScript contract tests.

## Global Constraints

- This plan implements SPEC stages 2 and 3 and the backend part of stage 5 from `docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md`.
- Complete Plan 1 before applying this plan; every source lookup and artifact publication assumes course authorization already exists.
- Public APIs and manifests use stable course document IDs. Filesystem paths and vector-store keys remain internal implementation details.
- Source mode is always explicit: `course_auto`, `selected_documents`, or `none`.
- `selected_documents` accepts only ready documents belonging to the current course. It never silently drops an invalid selection.
- `course_auto` may run with zero ready documents; the job records that no course evidence was available.
- `none` must not read course documents or query RAG.
- Job ownership stays per user. Published course artifacts are shared according to Plan 1.
- Tests use fake generation providers and deterministic blockers; the acceptance suite must not call a live model or external network.
- Use TDD and keep every commit independently reviewable.

## Priority and Command Locations

- **P0 / release blocking:** Tasks 1–10. Tasks 1–6 close the course-document/source contract; Tasks 7–8 close queue isolation and terminal-state reliability; Tasks 9–10 prevent invalid frontend submissions and prove the full matrix.
- Run pytest commands from `D:\github\edu_ai\Edu_AI\api\src`.
- Run every git command from repository root `D:\github\edu_ai`; therefore git paths include the `Edu_AI/` prefix.

---

## Shared Contracts

Create these contracts once in Task 1 and reuse them unchanged in later tasks:

```python
GenerationSourceMode = Literal["course_auto", "selected_documents", "none"]

@dataclass(frozen=True)
class ResolvedSourceDocument:
    document_id: str
    name: str
    rag_index_key: str
    chunk_count: int

@dataclass(frozen=True)
class SourceDocumentRecord:
    course_id: str
    document_id: str
    name: str
    status: str
    rag_index_key: str
    chunk_count: int

@dataclass(frozen=True)
class ResolvedGenerationSource:
    course_id: str
    mode: GenerationSourceMode
    requested_document_ids: tuple[str, ...]
    documents: tuple[ResolvedSourceDocument, ...]
    context_text: str
    resolved_at: str

    def to_snapshot(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "requested_document_ids": list(self.requested_document_ids),
            "documents": [asdict(item) for item in self.documents],
            "resolved_at": self.resolved_at,
        }

class DocumentCatalog(Protocol):
    def list_for_course(self, course_id: str) -> list[SourceDocumentRecord]:
        raise NotImplementedError

    def get_by_public_id(self, document_id: str) -> SourceDocumentRecord | None:
        raise NotImplementedError

class DocumentContentReader(Protocol):
    def read_many(self, rag_index_keys: Sequence[str]) -> str:
        raise NotImplementedError
```

API error codes introduced by this plan:

| Code | HTTP/status | Meaning |
|---|---:|---|
| `SOURCE_DOCUMENT_NOT_FOUND` | 422 | A selected public document ID is absent from the course |
| `SOURCE_DOCUMENT_NOT_READY` | 409 | A selected document is still processing or failed |
| `SOURCE_DOCUMENT_WRONG_COURSE` | 403 | A selected document belongs to another course |
| `GENERATION_SOURCE_INVALID` | 422 | Mode and selected IDs contradict each other |
| `GENERATION_DEADLINE_EXCEEDED` | failed job | The job exceeded its configured execution deadline |
| `GENERATION_CANCELLED` | canceled job | Cancellation converged and no artifact was published |

## Target File Map

| File | Responsibility |
|---|---|
| `api/src/app/services/generation_source_resolver.py` | Resolve public course documents into immutable generation context |
| `api/src/app/services/generation_source_errors.py` | Stable source error types and codes |
| `api/src/app/chat/api/schemas_v2.py` | Common source-mode request schema |
| `api/src/app/services/generation_command.py` | Durable command carrying source intent and deadlines |
| `api/src/app/services/generation_task_handlers.py` | Resolve once, invoke generator, persist source snapshot |
| `api/src/app/chat/application/knowledge_base_document_content_provider.py` | Read content from resolved RAG keys |
| `api/src/app/chat/application/knowledge_base_summary_provider.py` | Summarize resolved course documents |
| `api/src/app/chat/api/routes_v2.py` | Preflight and direct-generation endpoints |
| `api/src/app/services/direct_lesson_plan_service.py` | Durable direct lesson-plan generation |
| `api/src/app/services/durable_task_executor.py` | One worker execution loop with cancellation/deadline checks |
| `api/src/app/services/durable_executor_pool.py` | Bounded worker pool lifecycle |
| `api/src/app/services/durable_job_runtime.py` | Build/start/stop the executor pool |
| `api/src/app/chat/tasks/task_store.py` | Durable deadline and cancellation state |
| `api/src/app/services/job_reconciliation_service.py` | Startup recovery and terminal-state convergence |
| `api/src/app/services/classroom_job_service.py` | Apply the same source contract to AI classroom generation |
| `api/src/scripts/migrate_course_document_ids.py` | Validate/backfill public IDs and RAG keys |

---

### Task 1: Implement the canonical generation source resolver

**Files:**
- Create: `api/src/app/services/generation_source_errors.py`
- Create: `api/src/app/services/generation_source_resolver.py`
- Create: `api/src/tests/test_generation_source_resolver.py`

**Interfaces:**
- Consumes: `KnowledgeDocumentService.list_documents(course_id)` and document content providers.
- Produces: `GenerationSourceResolver.resolve(course_id, mode, selected_document_ids)` returning `ResolvedGenerationSource`.

- [ ] **Step 1: Write failing source-resolution tests**

```python
def test_selected_documents_resolve_public_ids_to_rag_keys(resolver, catalog):
    catalog.add(course_id="c1", document_id="doc-1", status="ready", rag_index_key="rag/course/c1/doc-1")
    resolved = resolver.resolve("c1", "selected_documents", ["doc-1"])
    assert resolved.requested_document_ids == ("doc-1",)
    assert resolved.documents[0].rag_index_key == "rag/course/c1/doc-1"
    assert "Newton" in resolved.context_text


def test_none_does_not_query_catalog_or_content(resolver, catalog, content_reader):
    resolved = resolver.resolve("c1", "none", [])
    assert resolved.documents == ()
    assert resolved.context_text == ""
    assert catalog.calls == []
    assert content_reader.calls == []


def test_selected_processing_document_fails_with_stable_code(resolver, catalog):
    catalog.add(course_id="c1", document_id="doc-1", status="processing", rag_index_key="")
    with pytest.raises(GenerationSourceError) as caught:
        resolver.resolve("c1", "selected_documents", ["doc-1"])
    assert caught.value.code == "SOURCE_DOCUMENT_NOT_READY"
```

Define `FakeDocumentCatalog` and `FakeDocumentContentReader` in this test file. The `resolver` fixture injects both and a fixed UTC clock; the fakes expose `calls` lists so the `none` test proves there were no hidden reads.

- [ ] **Step 2: Run the focused test and verify the module is absent**

Run from `Edu_AI/api/src`:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_generation_source_resolver.py -q
```

Expected: collection fails because `generation_source_resolver` does not exist.

- [ ] **Step 3: Implement strict mode validation and deterministic ordering**

Implement:

```python
class GenerationSourceResolver:
    def __init__(self, document_catalog: DocumentCatalog, content_reader: DocumentContentReader, clock: Callable[[], datetime]):
        self._document_catalog = document_catalog
        self._content_reader = content_reader
        self._clock = clock

    def resolve(
        self,
        course_id: str,
        mode: GenerationSourceMode,
        selected_document_ids: Sequence[str],
    ) -> ResolvedGenerationSource:
        normalized = tuple(dict.fromkeys(item.strip() for item in selected_document_ids if item.strip()))
        if mode == "none":
            if normalized:
                raise GenerationSourceError("GENERATION_SOURCE_INVALID", "none mode cannot include documents")
            return ResolvedGenerationSource(course_id, mode, (), (), "", self._clock().isoformat())
        if mode == "selected_documents" and not normalized:
            raise GenerationSourceError("GENERATION_SOURCE_INVALID", "select at least one document")
        resolved_documents = self.validate(course_id, mode, normalized)
        context = self._content_reader.read_many([item.rag_index_key for item in resolved_documents])
        return ResolvedGenerationSource(course_id, mode, normalized, resolved_documents, context, self._clock().isoformat())

    def validate(
        self,
        course_id: str,
        mode: GenerationSourceMode,
        selected_document_ids: Sequence[str],
    ) -> tuple[ResolvedSourceDocument, ...]:
        normalized = tuple(dict.fromkeys(item.strip() for item in selected_document_ids if item.strip()))
        if mode == "none":
            if normalized:
                raise GenerationSourceError("GENERATION_SOURCE_INVALID", "none mode cannot include documents")
            return ()
        if mode == "selected_documents":
            if not normalized:
                raise GenerationSourceError("GENERATION_SOURCE_INVALID", "select at least one document")
            records = []
            for document_id in normalized:
                record = self._document_catalog.get_by_public_id(document_id)
                if record is None:
                    raise GenerationSourceError("SOURCE_DOCUMENT_NOT_FOUND", document_id)
                if record.course_id != course_id:
                    raise GenerationSourceError("SOURCE_DOCUMENT_WRONG_COURSE", document_id)
                records.append(record)
        else:
            records = self._document_catalog.list_for_course(course_id)
        ready = []
        for record in records:
            if record.status != "ready" or not record.rag_index_key:
                if mode == "selected_documents":
                    raise GenerationSourceError("SOURCE_DOCUMENT_NOT_READY", record.document_id)
                continue
            ready.append(self._to_resolved(record))
        return tuple(sorted(ready, key=lambda item: item.document_id))
```

For `course_auto`, call `ready_documents(course_id, None)` and include all ready documents in stable public-ID order. Limit concatenated context with the existing RAG budget rather than truncating individual files at arbitrary byte boundaries.

- [ ] **Step 4: Verify all source modes and error codes**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_generation_source_resolver.py tests/chat/test_rag_v2_document_resolver.py tests/chat/test_rag_v2_provider_document_resolution.py -q
```

Expected: public IDs resolve to RAG keys, `none` performs no reads, and invalid selections fail before generation.

- [ ] **Step 5: Commit the resolver boundary**

```powershell
git add Edu_AI/api/src/app/services/generation_source_errors.py Edu_AI/api/src/app/services/generation_source_resolver.py Edu_AI/api/src/tests/test_generation_source_resolver.py
git commit -m "feat: resolve course generation sources"
```

### Task 2: Put source mode into every direct-generation API and durable command

**Files:**
- Modify: `api/src/app/chat/api/schemas_v2.py`
- Modify: `api/src/app/chat/api/routes_v2.py`
- Modify: `api/src/app/services/generation_command.py`
- Modify: `api/src/tests/chat/test_generation_command.py`
- Create: `api/src/tests/chat/test_generation_source_contract.py`

**Interfaces:**
- Consumes: `GenerationSourceMode` from Task 1.
- Produces: one `GenerationSourceRequest` mixed into report, lesson plan, blog, quiz, PPT, flashcard, graph, and game requests.

- [ ] **Step 1: Add contract tests for valid and invalid request combinations**

```python
@pytest.mark.parametrize("path", DIRECT_GENERATION_PATHS)
def test_direct_generation_accepts_none_without_documents(client, path):
    response = client.post(path, json=minimum_payload(path) | {
        "course_id": "c1",
        "source_mode": "none",
        "selected_doc_ids": [],
    })
    assert response.status_code == 202


@pytest.mark.parametrize("path", DIRECT_GENERATION_PATHS)
def test_selected_mode_requires_documents(client, path):
    response = client.post(path, json=minimum_payload(path) | {
        "course_id": "c1",
        "source_mode": "selected_documents",
        "selected_doc_ids": [],
    })
    assert response.status_code == 422
```

For this task, `DIRECT_GENERATION_PATHS` enumerates the eight existing direct routes. Task 5 adds `/api/chat/v2/lesson-plan/direct` to the same constant and reruns this contract after the endpoint exists.

- [ ] **Step 2: Run the request contract and observe current minimum-length failures**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/chat/test_generation_source_contract.py tests/chat/test_generation_command.py -q
```

Expected: `none` fails for schemas that currently require at least one selected document.

- [ ] **Step 3: Add a shared request model and command fields**

```python
class GenerationSourceRequest(BaseModel):
    source_mode: GenerationSourceMode = "course_auto"
    selected_doc_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_selection(self) -> Self:
        if self.source_mode == "selected_documents" and not self.selected_doc_ids:
            raise ValueError("selected_documents requires at least one document")
        if self.source_mode != "selected_documents" and self.selected_doc_ids:
            raise ValueError("selected_doc_ids is only valid for selected_documents")
        return self
```

Extend `GenerationCommand` with `source_mode`, `selected_doc_ids`, and `deadline_seconds`. Default old persisted commands to `selected_documents` when they contain document IDs, otherwise `course_auto`. Do not rewrite existing SQLite task payloads in place.

- [ ] **Step 4: Run schema, command, and direct-route tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/chat/test_generation_source_contract.py tests/chat/test_generation_command.py tests/test_jobs_api_v2.py -q
```

Expected: every resource accepts the same three source modes and old command payloads still deserialize.

- [ ] **Step 5: Commit the shared source contract**

```powershell
git add Edu_AI/api/src/app/chat/api/schemas_v2.py Edu_AI/api/src/app/chat/api/routes_v2.py Edu_AI/api/src/app/services/generation_command.py Edu_AI/api/src/tests/chat/test_generation_command.py Edu_AI/api/src/tests/chat/test_generation_source_contract.py
git commit -m "feat: standardize generation source modes"
```

### Task 3: Resolve source context once and preserve provenance in artifacts

**Files:**
- Modify: `api/src/app/services/generation_task_handlers.py`
- Modify: `api/src/app/chat/application/knowledge_base_document_content_provider.py`
- Modify: `api/src/app/chat/application/knowledge_base_summary_provider.py`
- Modify: `api/src/core/course_storage.py`
- Create: `api/src/tests/test_generation_source_provenance.py`
- Modify: `api/src/tests/core/test_course_material_manifest.py`

**Interfaces:**
- Consumes: `GenerationSourceResolver` and `GenerationCommand` from Tasks 1–2.
- Produces: `GenerationExecutionContext` and artifact `source_snapshot`.

- [x] **Step 1: Write a test proving resolution happens once**

```python
def test_handler_resolves_once_and_publishes_same_snapshot(handler, resolver, generator, storage):
    command = command_for("report", source_mode="selected_documents", selected_doc_ids=["doc-1"])
    handler.handle(command)
    assert resolver.calls == [("course-1", "selected_documents", ("doc-1",))]
    assert generator.contexts[0].source.context_text == "resolved course evidence"
    material = storage.get_generated_material("course-1", "report", generator.material_id)
    assert material["source_snapshot"]["documents"][0]["document_id"] == "doc-1"
```

The test file defines `SpyGenerationSourceResolver`, `SpyResourceGenerator`, and an in-memory-compatible temporary `CourseStorageManager`. The `handler` fixture injects these exact objects so call counts and the persisted manifest are observed through public methods.

- [x] **Step 2: Run provenance tests and confirm duplicate provider lookup or missing snapshot**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_generation_source_provenance.py tests/core/test_course_material_manifest.py -q
```

Expected: the current handler lacks a resolved-source execution context and complete source snapshot.

- [x] **Step 3: Add an immutable execution context**

```python
@dataclass(frozen=True)
class GenerationExecutionContext:
    job_id: str
    course_id: str
    user_id: str
    source: ResolvedGenerationSource
    config: Mapping[str, object]
```

At the start of `GenerationTaskHandler.handle()`, resolve the source and pass the same context object to the resource-specific adapter. Update content and summary providers to accept resolved RAG keys directly; they must not reinterpret course document IDs. Persist `source_snapshot`, `config_snapshot`, `created_by`, and `source_job_id` with the final artifact.

- [x] **Step 4: Verify provider and manifest compatibility**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_generation_source_provenance.py tests/core/test_course_material_manifest.py tests/chat/test_rag_v2_provider_document_resolution.py tests/test_job_completion_service.py -q
```

Expected: one resolver call per job, immutable provenance, and successful legacy manifest reads.

- [x] **Step 5: Commit single-pass source resolution**

```powershell
git add Edu_AI/api/src/app/services/generation_task_handlers.py Edu_AI/api/src/app/chat/application/knowledge_base_document_content_provider.py Edu_AI/api/src/app/chat/application/knowledge_base_summary_provider.py Edu_AI/api/src/core/course_storage.py Edu_AI/api/src/tests/test_generation_source_provenance.py Edu_AI/api/src/tests/core/test_course_material_manifest.py
git commit -m "feat: preserve generation source provenance"
```

### Task 4: Normalize public course document IDs and repair legacy RAG links

**Files:**
- Modify: `api/src/app/services/knowledge_document_service.py`
- Modify: `api/src/modules/rag_v2/document_resolver.py`
- Create: `api/src/scripts/migrate_course_document_ids.py`
- Create: `api/src/tests/test_course_document_id_migration.py`
- Modify: `api/src/tests/test_rag_document_lifecycle.py`

**Interfaces:**
- Consumes: existing knowledge-base index records and RAG metadata.
- Produces: stable `document_id`, `rag_index_key`, `status`, `chunk_count`, and migration report.

- [x] **Step 1: Add lifecycle and migration tests**

```python
def test_ready_document_keeps_public_id_across_reindex(service):
    created = service.create_received("c1", "Mechanics.pdf")
    first = service.mark_ready("c1", created.document_id, rag_index_key="rag/key/1", chunk_count=12)
    second = service.mark_ready("c1", created.document_id, rag_index_key="rag/key/2", chunk_count=15)
    assert second.document_id == first.document_id
    assert second.rag_index_key == "rag/key/2"


def test_migration_dry_run_does_not_write(tmp_path):
    before = snapshot_tree(tmp_path)
    report = migrate_course_documents(tmp_path, apply=False)
    assert report.repairable_count == 1
    assert snapshot_tree(tmp_path) == before
```

- [x] **Step 2: Run lifecycle tests against legacy records**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_document_id_migration.py tests/test_rag_document_lifecycle.py -q
```

Expected: inconsistent legacy IDs or missing RAG keys are exposed by the new assertions.

- [x] **Step 3: Implement safe normalization and a two-mode migration command**

The migration reads every course knowledge index, reports missing/duplicate public IDs and broken RAG keys, and writes only with `--apply`:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m scripts.migrate_course_document_ids --dry-run
D:\anaconda\envs\edu-ai\python.exe -m scripts.migrate_course_document_ids --apply
```

Backfill IDs with a deterministic UUIDv5 derived from `(course_id, normalized legacy relative path)`. Never expose the relative path through new API responses. If no matching RAG record exists, retain the document and set `status="failed"` with `error_code="RAG_INDEX_MISSING"` so it cannot be selected as ready.

- [x] **Step 4: Verify dry-run, apply, rerun idempotency, and counts**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_document_id_migration.py tests/test_rag_document_lifecycle.py tests/chat/test_rag_v2_document_resolver.py -q
```

Expected: a second apply reports zero changes; list/detail/status endpoints agree on status and chunk count.

- [x] **Step 5: Commit document identity repair**

```powershell
git add Edu_AI/api/src/app/services/knowledge_document_service.py Edu_AI/api/src/modules/rag_v2/document_resolver.py Edu_AI/api/src/scripts/migrate_course_document_ids.py Edu_AI/api/src/tests/test_course_document_id_migration.py Edu_AI/api/src/tests/test_rag_document_lifecycle.py
git commit -m "fix: normalize course document identities"
```

### Task 5: Add durable direct lesson-plan generation

**Files:**
- Create: `api/src/app/services/direct_lesson_plan_service.py`
- Modify: `api/src/app/chat/api/schemas_v2.py`
- Modify: `api/src/app/chat/api/routes_v2.py`
- Modify: `api/src/app/services/generation_command.py`
- Modify: `api/src/app/services/generation_task_handlers.py`
- Create: `api/src/tests/chat/test_lesson_plan_direct.py`

**Interfaces:**
- Consumes: shared source contract and durable generation handler.
- Produces: `POST /api/chat/v2/lesson-plan/direct` returning the standard 202 job envelope.

- [x] **Step 1: Write request, job, and publication tests**

```python
def test_lesson_plan_direct_creates_durable_job(client, task_store):
    response = client.post("/api/chat/v2/lesson-plan/direct", json={
        "course_id": "c1",
        "topic": "Newton's laws",
        "duration_minutes": 45,
        "audience": "first-year undergraduate",
        "source_mode": "course_auto",
        "selected_doc_ids": [],
    })
    assert response.status_code == 202
    command = task_store.get_command(response.json()["job_id"])
    assert command["resource_type"] == "lesson_plan"
```

In this test file, expose `task_store.get_command(job_id)` as a small test-only adapter over the existing durable row so the assertion reads the deserialized command rather than depending on private SQLite columns.

- [x] **Step 2: Run and verify the endpoint is absent**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/chat/test_lesson_plan_direct.py -q
```

Expected: 404 for `/lesson-plan/direct`.

- [x] **Step 3: Implement the service and register it in the existing handler map**

The direct service accepts `GenerationExecutionContext`, builds a typed lesson-plan prompt from topic, audience, duration, objectives, and resolved source context, then returns the same artifact shape used by the current lesson-plan preview. The route only validates/enqueues; it must not call the model in the HTTP request thread.

- [x] **Step 4: Run lesson-plan, command, and publication tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/chat/test_lesson_plan_direct.py tests/chat/test_generation_command.py tests/test_job_completion_service.py -q
```

Expected: 202 response, durable execution, and a course-shared lesson-plan artifact.

- [x] **Step 5: Commit durable lesson-plan generation**

```powershell
git add Edu_AI/api/src/app/services/direct_lesson_plan_service.py Edu_AI/api/src/app/chat/api/schemas_v2.py Edu_AI/api/src/app/chat/api/routes_v2.py Edu_AI/api/src/app/services/generation_command.py Edu_AI/api/src/app/services/generation_task_handlers.py Edu_AI/api/src/tests/chat/test_lesson_plan_direct.py
git commit -m "feat: add durable lesson plan generation"
```

### Task 6: Apply the same source contract to AI classroom generation

**Files:**
- Modify: `api/src/app/schemas/course.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `api/src/app/services/classroom_job_service.py`
- Modify: `api/src/app/services/classroom_service.py`
- Create: `api/src/tests/test_classroom_generation_sources.py`

**Interfaces:**
- Consumes: `GenerationSourceResolver`.
- Produces: classroom generation request fields `source_mode` and `selected_doc_ids`, plus a persisted `source_snapshot`.

- [x] **Step 1: Write classroom source-mode tests**

```python
@pytest.mark.parametrize("mode,ids", [("course_auto", []), ("selected_documents", ["doc-1"]), ("none", [])])
def test_classroom_generation_uses_shared_source_contract(classroom_jobs, resolver, mode, ids):
    job = classroom_jobs.enqueue(course_id="c1", user_id="teacher-a", source_mode=mode, selected_doc_ids=ids, config=valid_classroom_config())
    classroom_jobs.run(job.id)
    assert resolver.calls[-1] == ("c1", mode, tuple(ids))
```

Build `classroom_jobs` with the real `ClassroomJobService`, a temporary course store, a synchronous fake executor, and the same spy resolver used by the general handler tests. `valid_classroom_config()` returns a fully typed minimum configuration including topic, audience, scene count, and explicit voice-enabled state.

- [x] **Step 2: Run and reproduce the classroom contract mismatch**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_classroom_generation_sources.py tests/test_classroom_job_service.py -q
```

Expected: current classroom requests do not expose all three modes or provenance.

- [x] **Step 3: Reuse the resolver instead of classroom-specific document parsing**

Validate the request with the same rules as `GenerationSourceRequest`. Store source intent in the job payload, resolve in the worker, and persist the snapshot with the classroom manifest. `none` must produce a valid classroom from topic and configuration only.

- [x] **Step 4: Run classroom and course authorization tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_classroom_generation_sources.py tests/test_classroom_job_service.py tests/test_course_route_authorization.py -q
```

Expected: editors can generate in every source mode; viewers receive 403; source snapshots are readable with classroom detail.

- [x] **Step 5: Commit the classroom source contract**

```powershell
git add Edu_AI/api/src/app/schemas/course.py Edu_AI/api/src/app/api/courses.py Edu_AI/api/src/app/services/classroom_job_service.py Edu_AI/api/src/app/services/classroom_service.py Edu_AI/api/src/tests/test_classroom_generation_sources.py
git commit -m "feat: standardize classroom generation sources"
```

### Task 7: Replace the single durable worker with a bounded executor pool

**Files:**
- Create: `api/src/app/services/durable_executor_pool.py`
- Modify: `api/src/app/services/durable_job_runtime.py`
- Modify: `api/src/app/services/durable_task_executor.py`
- Modify: `api/src/core/config.py`
- Create: `api/src/tests/test_durable_executor_pool.py`
- Modify: `api/src/tests/test_durable_job_runtime.py`
- Modify: `api/src/tests/test_job_worker_lifespan.py`

**Interfaces:**
- Consumes: existing `DurableTaskExecutor` and shared SQLite `TaskStore` leasing.
- Produces: `DurableExecutorPool.start()`, `.stop(timeout_seconds)`, `.worker_count`.

- [x] **Step 1: Write a fault-isolation test using synchronization events**

```python
def test_blocked_job_does_not_block_second_job(task_store, executor_pool):
    blocker_started = threading.Event()
    release_blocker = threading.Event()
    executor_pool.handlers["blocking"] = blocking_handler(blocker_started, release_blocker)
    first = enqueue_test_task(task_store, workflow_type="blocking", task_id="job-blocking")
    second = enqueue_test_task(task_store, workflow_type="fast", task_id="job-fast")
    executor_pool.start()
    assert blocker_started.wait(timeout=2)
    assert wait_for_status(task_store, second.id, "completed", timeout=2)
    assert task_store.get_durable(first.task_id).status == "running"
    release_blocker.set()
```

Define `enqueue_test_task()` in the same test file. It calls the existing keyword-only `TaskStore.enqueue()` with `handler_version=1`, `owner_user_id="teacher-a"`, `course_id="course-1"`, `scope_type="course"`, a JSON-safe command, and `max_attempts=1`; this keeps the test aligned with the production leasing API.

The `executor_pool` fixture uses two workers, a 10 ms poll interval, a temporary SQLite task store, and explicit `start()`/`stop()` teardown. `blocking_handler()` sets the start event before waiting and always observes the release event in a `finally`-safe test teardown.

- [x] **Step 2: Run the pool test and demonstrate head-of-line blocking**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_durable_executor_pool.py -q
```

Expected: the second task cannot complete while the only worker is blocked.

- [x] **Step 3: Implement a bounded pool over existing atomic leasing**

Add configuration:

```python
DURABLE_JOB_WORKERS = max(1, int(os.getenv("DURABLE_JOB_WORKERS", "3")))
```

`DurableExecutorPool` creates N executors with unique worker IDs, shares the task store/handlers, and owns lifecycle ordering. Startup is idempotent. Shutdown requests every worker to stop, joins each with the remaining shared timeout, then reports worker IDs that did not stop. Do not create nested model-call thread pools inside handlers.

- [x] **Step 4: Run pool, runtime, and lifespan tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_durable_executor_pool.py tests/test_durable_job_runtime.py tests/test_job_worker_lifespan.py -q
```

Expected: the fast task completes while the blocker runs, leasing prevents duplicate execution, and app shutdown terminates all test workers.

- [x] **Step 5: Commit bounded job concurrency**

```powershell
git add Edu_AI/api/src/app/services/durable_executor_pool.py Edu_AI/api/src/app/services/durable_job_runtime.py Edu_AI/api/src/app/services/durable_task_executor.py Edu_AI/api/src/core/config.py Edu_AI/api/src/tests/test_durable_executor_pool.py Edu_AI/api/src/tests/test_durable_job_runtime.py Edu_AI/api/src/tests/test_job_worker_lifespan.py
git commit -m "feat: run durable jobs in bounded pool"
```

### Task 8: Add deadlines and deterministic cancellation recovery

**Files:**
- Modify: `api/src/app/chat/tasks/task_store.py`
- Modify: `api/src/app/services/durable_task_executor.py`
- Modify: `api/src/app/services/job_reconciliation_service.py`
- Modify: `api/src/app/api/jobs.py`
- Create: `api/src/tests/test_job_deadlines_and_cancellation.py`

**Interfaces:**
- Consumes: command `deadline_seconds` and existing `cancel_requested` flag.
- Produces: persisted `deadline_at`, terminal `canceled` convergence, and stable timeout/cancel error codes.

- [ ] **Step 1: Write deadline and restart-recovery tests**

```python
def test_expired_queued_job_fails_without_handler_call(runtime, task_store, handler):
    job = enqueue_deadlined_task(task_store, task_id="job-expired", deadline_at="2026-08-06T00:00:00+00:00")
    runtime.run_once(now=datetime(2026, 8, 6, 0, 0, 1, tzinfo=timezone.utc))
    assert task_store.get_durable(job.task_id).status == "failed"
    assert task_store.get_durable(job.task_id).error_code == "GENERATION_DEADLINE_EXCEEDED"
    assert handler.calls == []


def test_reconciliation_finishes_cancel_requested_job(task_store, reconciliation):
    job = seed_cancel_requested_task(task_store, task_id="job-cancel", lease_expires_at="2026-08-05T00:00:00+00:00")
    reconciliation.run(now=datetime(2026, 8, 6, tzinfo=timezone.utc))
    assert task_store.get_durable(job.task_id).status == "canceled"
```

Define both helpers in this test file. `enqueue_deadlined_task()` uses the production enqueue method after the new deadline column is added. `seed_cancel_requested_task()` enqueues, claims, requests cancellation through the store API, and then updates only the lease timestamp through a test fixture connection so the scenario matches a process restart.

- [ ] **Step 2: Run and capture non-terminal cancellation behavior**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_job_deadlines_and_cancellation.py tests/test_job_reconciliation_service.py -q
```

Expected: expired work may execute and stale `cancel_requested` may remain non-terminal.

- [ ] **Step 3: Migrate the task schema and enforce transitions**

Add nullable `deadline_at` and `error_code` columns using `PRAGMA table_info` plus idempotent `ALTER TABLE`. Before invoking a handler and before publishing an artifact, the executor checks cancellation and deadline. Reconciliation applies:

```text
cancel_requested + no live lease -> canceled / GENERATION_CANCELLED
queued + deadline passed -> failed / GENERATION_DEADLINE_EXCEEDED
running + expired lease + deadline passed -> failed / GENERATION_DEADLINE_EXCEEDED
running + expired lease + deadline active -> queued for retry
```

A canceled/timed-out job must never publish an artifact after its terminal transition. Keep the jobs API owner-scoped.

- [ ] **Step 4: Run task-store, jobs API, runtime, and reconciliation tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_job_deadlines_and_cancellation.py tests/test_jobs_api_v2.py tests/test_job_reconciliation_service.py tests/test_durable_job_runtime.py -q
```

Expected: every cancellation converges, timeout codes persist, and retries remain available before the deadline.

- [ ] **Step 5: Commit reliable terminal-state handling**

```powershell
git add Edu_AI/api/src/app/chat/tasks/task_store.py Edu_AI/api/src/app/services/durable_task_executor.py Edu_AI/api/src/app/services/job_reconciliation_service.py Edu_AI/api/src/app/api/jobs.py Edu_AI/api/src/tests/test_job_deadlines_and_cancellation.py
git commit -m "fix: converge job deadlines and cancellation"
```

### Task 9: Add a generation preflight endpoint

**Files:**
- Modify: `api/src/app/chat/api/schemas_v2.py`
- Modify: `api/src/app/chat/api/routes_v2.py`
- Create: `api/src/tests/chat/test_generation_preflight.py`

**Interfaces:**
- Consumes: course authorization and `GenerationSourceResolver` validation.
- Produces: `POST /api/chat/v2/generation/preflight` with no model call and no durable job.

- [ ] **Step 1: Write preflight success and error tests**

```python
def test_preflight_returns_ready_document_summary(client):
    response = client.post("/api/chat/v2/generation/preflight", json={
        "course_id": "c1",
        "resource_type": "quiz",
        "source_mode": "selected_documents",
        "selected_doc_ids": ["doc-1"],
    })
    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "source_mode": "selected_documents",
        "ready_document_count": 1,
        "documents": [{"document_id": "doc-1", "name": "Mechanics.pdf", "chunk_count": 12}],
        "warnings": [],
    }
```

- [ ] **Step 2: Run and verify the endpoint is absent**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/chat/test_generation_preflight.py -q
```

Expected: 404.

- [ ] **Step 3: Implement validation-only preflight**

The endpoint requires course `generate` capability, uses catalog validation but does not read full document content, create a task, or call a model. Return warnings for `course_auto` with zero ready documents and stable errors for explicit invalid selections.

- [ ] **Step 4: Run preflight and authorization tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/chat/test_generation_preflight.py tests/test_course_route_authorization.py -q
```

Expected: editor success, viewer 403, invalid document errors, and zero task-store writes.

- [ ] **Step 5: Commit preflight validation**

```powershell
git add Edu_AI/api/src/app/chat/api/schemas_v2.py Edu_AI/api/src/app/chat/api/routes_v2.py Edu_AI/api/src/tests/chat/test_generation_preflight.py
git commit -m "feat: add generation source preflight"
```

### Task 10: Run the nine-resource reliability acceptance matrix

**Files:**
- Create: `api/src/tests/acceptance/test_generation_reliability_matrix.py`
- Create: `api/src/tests/acceptance/fake_generation_providers.py`
- Modify: `docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md` only after evidence exists.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: executable coverage for report, lesson plan, blog, quiz, PPT, flashcard, mind map, game, and AI classroom.

- [ ] **Step 1: Define the complete acceptance matrix**

```python
@dataclass(frozen=True)
class ResourceCase:
    resource_type: str
    path: str

RESOURCE_CASES = (
    ResourceCase("report", "/api/chat/v2/report/direct"),
    ResourceCase("lesson_plan", "/api/chat/v2/lesson-plan/direct"),
    ResourceCase("blog", "/api/chat/v2/blog/direct"),
    ResourceCase("quiz", "/api/chat/v2/quiz/direct"),
    ResourceCase("ppt", "/api/chat/v2/ppt/generate"),
    ResourceCase("flashcard", "/api/chat/v2/flashcard/direct"),
    ResourceCase("graph", "/api/chat/v2/graph/direct"),
    ResourceCase("game", "/api/chat/v2/game/direct"),
    ResourceCase("classroom", "/api/courses/c1/classrooms/generate"),
)
```

For each case verify `course_auto`, `selected_documents`, and `none`; correct source snapshot; successful artifact read-back; wrong-course rejection; and no live network.

- [ ] **Step 2: Add a concurrency/cancellation scenario to the matrix**

Block one fake blog provider, enqueue quiz and flashcard jobs, cancel the blog, and assert quiz/flashcard finish within two seconds while the blog converges to `canceled` without an artifact.

- [ ] **Step 3: Run the focused acceptance suite**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/acceptance/test_generation_reliability_matrix.py -q
```

Expected: 27 source-mode cases plus fault-isolation scenarios pass deterministically.

- [ ] **Step 4: Run the complete affected backend gate**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_generation_source_resolver.py tests/chat/test_generation_source_contract.py tests/test_generation_source_provenance.py tests/test_course_document_id_migration.py tests/chat/test_lesson_plan_direct.py tests/test_classroom_generation_sources.py tests/test_durable_executor_pool.py tests/test_job_deadlines_and_cancellation.py tests/chat/test_generation_preflight.py tests/acceptance/test_generation_reliability_matrix.py -q
```

Expected: all tests pass with deterministic fake providers.

- [ ] **Step 5: Run regression, record evidence, and commit**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_jobs_api_v2.py tests/test_job_completion_service.py tests/test_job_reconciliation_service.py tests/test_rag_document_lifecycle.py tests/chat/test_course_scope_routes.py -q
git add Edu_AI/api/src/tests/acceptance Edu_AI/docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md
git commit -m "test: verify generation reliability matrix"
```

Expected: regression tests pass. Check Spec stage items only when their test or recorded manual evidence exists.

---

## Plan 2 Completion Gate

Do not start the generation-factory UI work in Plan 3 until all of the following are evidenced:

- All nine resources accept `course_auto`, `selected_documents`, and `none` under one contract.
- Selected public document IDs resolve to ready RAG indexes and produce non-empty context when indexed content exists.
- Invalid, processing, failed, and wrong-course documents fail before a model call.
- Artifacts retain immutable source and configuration snapshots.
- Lesson plans run as durable jobs rather than blocking the HTTP request.
- A blocked generator cannot prevent unrelated jobs from completing.
- Expired and canceled jobs converge to terminal states and cannot publish late artifacts.
- The preflight endpoint validates configuration without model/network use.
- The deterministic nine-resource acceptance matrix passes.
