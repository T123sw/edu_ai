# AI Classroom Course Resource Learning Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为学生自主学习已发布 AI 课堂资源建立独立、版本化、服务端可信的学习记录，并允许教师任务复用同版本完成证据。

**Architecture:** 新建 `app/resource_learning` 领域和 PostgreSQL 仓储，以标准资源审核时冻结的场景清单为计量依据；播放器只上报会话、讲解时间线区间、习题提交和演示行为，服务端计算 80% 讲解覆盖与全部必答题作答。前端在学生资源卡片和 AI 课堂播放器展示独立进度，教师端提供资源分析；任务域只保存资源证据引用，不复用原有任务进度表。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy 2、Alembic、PostgreSQL/SQLite 测试引擎、React 18、TypeScript、OpenMAIC `LessonTimeline`、Node test runner、Playwright。

---

## 实施前提与文件结构

当前主工作区包含与本功能无关的未提交修改。执行本计划前，从规格提交 `0020063` 或其后已整合的干净提交创建独立 `codex/` 工作树；不得把当前工作区的其他修改带入本功能提交。

新增后端目录：

```text
backend/src/app/resource_learning/
  __init__.py          依赖装配
  models.py            领域记录与状态类型
  manifest.py          AI 课堂场景分类和冻结清单
  intervals.py         时间线区间校验、合并和覆盖计算
  repository.py        SQLAlchemy 持久化和事务操作
  service.py           会话、事件、题目和进度用例
  analytics.py         教师聚合投影
  task_evidence.py     任务资源证据适配器
```

新增前端文件：

```text
frontend/src/stitch/api/resourceLearning.ts
frontend/src/openmaic/resourceLearningTracker.ts
frontend/src/openmaic/resourceLearningTracker.test.ts
frontend/src/stitch/course/knowledge/ResourceLearningProgress.tsx
frontend/src/stitch/course/knowledge/ResourceLearningAnalytics.tsx
frontend/src/stitch/course/knowledge/resourceLearning.css
```

新领域只跟踪 `origin_type=standard`、`standard_kind=classroom` 且具有明确 `approved_version` 的课程资源。私人课堂预览和教师演示模式不创建学生学习会话。

## Task 1: 冻结 AI 课堂学习清单与区间算法

**Files:**
- Create: `backend/src/app/resource_learning/__init__.py`
- Create: `backend/src/app/resource_learning/models.py`
- Create: `backend/src/app/resource_learning/manifest.py`
- Create: `backend/src/app/resource_learning/intervals.py`
- Test: `backend/src/tests/resource_learning/test_manifest.py`
- Test: `backend/src/tests/resource_learning/test_intervals.py`

- [ ] **Step 1: 写场景分类和区间算法的失败测试**

```python
def test_build_manifest_classifies_slide_quiz_and_interactive():
    payload = {
        "course_id": "course-1",
        "material_id": "classroom-1",
        "version": 3,
        "scenes": [
            {"id": "s1", "type": "slide", "content": {"type": "slide"},
             "actions": [{"id": "a1", "type": "speech", "text": "普通讲解。"}]},
            {"id": "q1", "type": "quiz", "content": {"type": "quiz", "questions": [
                {"id": "question-1", "type": "single", "question": "1+1?", "answer": ["B"]}
             ]}},
            {"id": "d1", "type": "interactive", "content": {"type": "interactive"}},
        ],
    }
    manifest = build_classroom_learning_manifest(payload)
    assert [scene.kind for scene in manifest.scenes] == ["explanation", "exercise", "demo"]
    assert manifest.required_question_ids == ("question-1",)
    assert manifest.mode == "completable"


def test_merge_ranges_deduplicates_replays_and_clamps_to_scene():
    merged = merge_covered_ranges([(0, 20_000), (15_000, 35_000), (50_000, 65_000)], total_ms=60_000)
    assert merged == [(0, 35_000), (50_000, 60_000)]
    assert covered_duration_ms(merged) == 45_000
```

- [ ] **Step 2: 运行测试并确认红灯**

Run from `backend/src`:

```powershell
python -m pytest tests/resource_learning/test_manifest.py tests/resource_learning/test_intervals.py -q
```

Expected: FAIL，`app.resource_learning.manifest` 和 `intervals` 尚不存在。

- [ ] **Step 3: 实现不可变领域类型、确定性时长和区间算法**

`models.py` 定义以下稳定接口：

```python
SceneKind = Literal["explanation", "exercise", "demo"]
ManifestMode = Literal["completable", "behavior_only"]

@dataclass(frozen=True)
class ManifestScene:
    scene_id: str
    kind: SceneKind
    expected_duration_ms: int
    required_action_ids: tuple[str, ...]
    required_question_ids: tuple[str, ...]

@dataclass(frozen=True)
class ManifestQuestion:
    question_id: str
    scene_id: str
    question_type: str
    required: bool
    scoring_values: tuple[str, ...]
    knowledge_point_ids: tuple[str, ...]

@dataclass(frozen=True)
class ResourceLearningManifestRecord:
    manifest_id: str
    course_id: str
    resource_id: str
    resource_version: int
    content_hash: str
    mode: ManifestMode
    scenes: tuple[ManifestScene, ...]
    questions: tuple[ManifestQuestion, ...]
    created_at: str
```

`manifest.py` 使用现有课堂类型做唯一映射：`slide -> explanation`、`quiz -> exercise`、`interactive -> demo`。只把 `slide` 的 Action 编入标准时长；`discussion` 为实时行为，时长为零。quiz 场景内题目默认 `required=True`，只有资源显式写入 `required: false` 才排除；标准答案只进入私有 manifest 存储，不进入学生投影。时长策略必须与 `frontend/src/openmaic/timeline.ts` 一致：普通非 speech Action 为 1000ms，孤立 focus 不增加串行时长，speech 中文按 `max(2000, len(text) * 150) / speed`，英文按 `max(2000, word_count * 240) / speed`。将同一组固定 fixture 同时用于 Python 和 TypeScript 测试，防止算法漂移。

`intervals.py` 暴露：

```python
def normalize_range(start_ms: int, end_ms: int, *, total_ms: int) -> tuple[int, int] | None:
    start = max(0, min(int(start_ms), int(total_ms)))
    end = max(0, min(int(end_ms), int(total_ms)))
    return (start, end) if end > start else None

def merge_covered_ranges(ranges: Iterable[tuple[int, int]], *, total_ms: int) -> list[tuple[int, int]]:
    normalized = sorted(item for raw in ranges if (item := normalize_range(*raw, total_ms=total_ms)))
    merged: list[tuple[int, int]] = []
    for start, end in normalized:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged

def covered_duration_ms(ranges: Iterable[tuple[int, int]]) -> int:
    return sum(end - start for start, end in ranges)

def coverage_percent(covered_ms: int, total_ms: int) -> float:
    return 0.0 if total_ms <= 0 else min(100.0, max(0.0, covered_ms / total_ms * 100.0))
```

- [ ] **Step 4: 运行领域测试并确认通过**

```powershell
python -m pytest tests/resource_learning/test_manifest.py tests/resource_learning/test_intervals.py -q
```

Expected: PASS，包含 slide/quiz/interactive、无题课堂 `behavior_only`、重复区间、越界区间和精确 80% 边界。

- [ ] **Step 5: 提交领域算法**

```powershell
git add backend/src/app/resource_learning backend/src/tests/resource_learning
git commit -m "feat: add resource learning manifest and coverage rules"
```

## Task 2: 建立资源学习数据库模型与迁移

**Files:**
- Create: `backend/src/alembic/versions/20260831_0019_resource_learning.py`
- Modify: `backend/src/app/database/models.py`
- Modify: `backend/src/tests/database/test_alembic_revision_chain.py`
- Test: `backend/src/tests/resource_learning/test_database_schema.py`

- [ ] **Step 1: 写数据库约束失败测试**

```python
def test_resource_learning_schema_has_versioned_progress_and_idempotent_events(engine):
    Base.metadata.create_all(engine)
    names = set(inspect(engine).get_table_names())
    assert {
        "resource_learning_manifests",
        "resource_learning_sessions",
        "resource_learning_events",
        "resource_learning_coverage",
        "resource_question_attempts",
        "resource_learning_progress",
        "task_resource_evidence_refs",
    } <= names
    event_constraints = inspect(engine).get_unique_constraints("resource_learning_events")
    assert any(set(item["column_names"]) == {"session_id", "sequence_number"} for item in event_constraints)
```

- [ ] **Step 2: 运行数据库测试并确认红灯**

```powershell
python -m pytest tests/resource_learning/test_database_schema.py tests/database/test_alembic_revision_chain.py -q
```

Expected: FAIL，资源学习表和迁移 revision 尚不存在。

- [ ] **Step 3: 添加 SQLAlchemy 模型和线性迁移**

迁移以合并头 `20260831_0018` 为 `down_revision`。若执行时仓库迁移头已前进，先只读运行 `python -m alembic heads`，保持新 revision 单头线性后继，不重写已提交迁移。

在 `models.py` 添加七个模型，并落实这些数据库约束：

```python
class ResourceLearningManifestModel(Base):
    __tablename__ = "resource_learning_manifests"
    __table_args__ = (UniqueConstraint("course_id", "resource_id", "resource_version", name="uq_resource_learning_manifest_version"),)
    manifest_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResourceLearningProgressModel(Base):
    __tablename__ = "resource_learning_progress"
    student_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    resource_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation_covered_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explanation_total_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explanation_coverage_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    required_question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answered_question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_completion_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    correct_count_first: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count_latest: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    demo_view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    demo_interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

其余五个模型严格采用规格 §10 的字段。`resource_learning_events.event_id` 全局唯一，`session_id + sequence_number` 唯一；题目尝试使用 `student_id + course_id + resource_id + resource_version + question_id + attempt_number` 唯一；任务证据引用使用 `task_id + student_id + resource_id + resource_version` 唯一。

- [ ] **Step 4: 验证迁移升级、降级和模型测试**

```powershell
python -m pytest tests/resource_learning/test_database_schema.py tests/database/test_alembic_revision_chain.py -q
python -m alembic upgrade head
python -m alembic downgrade 20260831_0018
python -m alembic upgrade head
```

Expected: 全部 PASS；升级创建七张表，降级只移除本 revision 表，再升级恢复单头。

- [ ] **Step 5: 提交数据库结构**

```powershell
git add backend/src/alembic/versions/20260831_0019_resource_learning.py backend/src/app/database/models.py backend/src/tests/database/test_alembic_revision_chain.py backend/src/tests/resource_learning/test_database_schema.py
git commit -m "feat: persist versioned resource learning evidence"
```

## Task 3: 实现事务仓储、会话与进度投影

**Files:**
- Create: `backend/src/app/resource_learning/repository.py`
- Create: `backend/src/app/resource_learning/service.py`
- Modify: `backend/src/app/resource_learning/models.py`
- Modify: `backend/src/app/persistence/dependencies.py`
- Test: `backend/src/tests/resource_learning/test_repository.py`
- Test: `backend/src/tests/resource_learning/test_service.py`

- [ ] **Step 1: 写会话、心跳、答题和完成状态失败测试**

```python
def test_progress_requires_eighty_percent_and_every_required_question(service, manifest):
    service.freeze_manifest(manifest)
    session = service.start_session(course_id="course-1", resource_id="classroom-1", resource_version=3, student_id="student-1")
    service.record_events(session.session_id, "student-1", [heartbeat("e1", 1, "s1", 0, 80_000)])
    progress = service.get_my_progress("course-1", "classroom-1", 3, "student-1")
    assert progress.status == "in_progress"
    service.submit_questions(course_id="course-1", resource_id="classroom-1", resource_version=3,
                             student_id="student-1", answers={"q1": "wrong", "q2": "wrong"}, idempotency_key="submit-1")
    progress = service.get_my_progress("course-1", "classroom-1", 3, "student-1")
    assert progress.status == "completed"
    assert progress.correct_count_latest == 0
```

另写测试覆盖：重复 `event_id`、序号冲突、未知 scene、跨度超过 20 秒、会话归属不符、多设备新会话结束旧会话、`behavior_only` 永不 completed、完成状态不回退。

- [ ] **Step 2: 运行服务测试并确认红灯**

```powershell
python -m pytest tests/resource_learning/test_repository.py tests/resource_learning/test_service.py -q
```

Expected: FAIL，仓储和服务尚不存在。

- [ ] **Step 3: 实现仓储事务和服务公开接口**

`ResourceLearningService` 的公开方法固定为 `freeze_manifest(manifest)`、`start_session(course_id, resource_id, resource_version, student_id)`、`record_events(session_id, student_id, events)`、`submit_questions(course_id, resource_id, resource_version, student_id, answers, idempotency_key)`、`end_session(session_id, student_id)` 和 `get_my_progress(course_id, resource_id, resource_version, student_id)`。返回类型分别为 manifest、session 或 progress 领域记录；后续 API 和任务适配器不得绕过服务直接写进度投影。

仓储在同一事务内完成事件幂等插入、区间合并和进度重算。完成判定必须是：

```python
completed = (
    manifest.mode == "completable"
    and explanation_coverage_percent >= 80.0
    and answered_question_count == required_question_count
)
next_status = "completed" if completed or current.status == "completed" else "in_progress"
```

题目提交从 manifest 获取题目和标准答案，忽略客户端提供的正确性。第一份有效答案形成 `correct_count_first`，最新答案形成 `correct_count_latest`。同一 `idempotency_key` 重试返回原结果，不增加 attempt number。

在 `persistence/dependencies.py` 添加缓存构造：

```python
@lru_cache(maxsize=8)
def _build_resource_learning_repository(database_url: str):
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")
    return ResourceLearningRepository(create_engine(database_url, pool_pre_ping=True))

def get_resource_learning_repository():
    return _build_resource_learning_repository(str(os.getenv("DATABASE_URL", "")).strip())
```

- [ ] **Step 4: 运行仓储和服务测试**

```powershell
python -m pytest tests/resource_learning/test_repository.py tests/resource_learning/test_service.py -q
```

Expected: PASS，且全部答错用例仍得到 `completed`。

- [ ] **Step 5: 提交服务核心**

```powershell
git add backend/src/app/resource_learning backend/src/app/persistence/dependencies.py backend/src/tests/resource_learning
git commit -m "feat: calculate trusted resource learning progress"
```

## Task 4: 在标准 AI 课堂审核时冻结学习清单

**Files:**
- Create: `backend/src/app/standard_resources/review_service.py`
- Modify: `backend/src/app/api/standard_resources.py`
- Modify: `backend/src/app/standard_resources/repository.py`
- Test: `backend/src/tests/standard_resources/test_review_service.py`
- Modify: `backend/src/tests/standard_resources/test_repository.py`

- [ ] **Step 1: 写批准 AI 课堂必须同时冻结 manifest 的失败测试**

```python
def test_approving_classroom_freezes_manifest_before_student_visibility(review_service, materials, learning_repo):
    seed_pending_classroom(materials, version=2)
    result = review_service.review(course_id="course-1", material_id="classroom-1",
                                   reviewer_id="teacher-1", decision="approved", reason="")
    manifest = learning_repo.get_manifest("course-1", "classroom-1", 2)
    assert result["approved_version"] == 2
    assert manifest is not None
    assert manifest.mode == "completable"


def test_manifest_failure_leaves_classroom_pending(review_service, materials):
    seed_invalid_pending_classroom(materials)
    with pytest.raises(StandardResourceRuleError) as error:
        review_service.review(course_id="course-1", material_id="classroom-1",
                              reviewer_id="teacher-1", decision="approved", reason="")
    assert error.value.code == "LEARNING_MANIFEST_INVALID"
    assert materials.get("course-1", "classroom", "classroom-1")["current_review_status"] == "pending"
```

- [ ] **Step 2: 运行审核测试并确认红灯**

```powershell
python -m pytest tests/standard_resources/test_review_service.py tests/standard_resources/test_repository.py -q
```

Expected: FAIL，审核仍直接调用仓储，未冻结 manifest。

- [ ] **Step 3: 实现审核协调服务并保持单事务语义**

`StandardResourceReviewService.review()` 先读取当前 `MaterialVersion.payload` 并构建 manifest，再调用仓储的 `review_material_with_manifest()`。仓储使用同一个 SQLAlchemy session 同时写 `Material`、`MaterialVersion` 和 `ResourceLearningManifestModel`；任一步失败必须整体回滚。非 classroom 标准资源传入 `manifest=None`，行为保持不变。

批量批准逐项调用协调服务；某项 manifest 无效时该项保持 pending，批量结果返回明确失败，不把它静默标成 approved。

API 依赖改为：

```python
def get_standard_resource_review_service() -> StandardResourceReviewService:
    return StandardResourceReviewService(
        repository=get_standard_resource_repository(),
        material_repository=get_postgres_material_repository(),
    )
```

- [ ] **Step 4: 运行审核与标准资源回归**

```powershell
python -m pytest tests/standard_resources -q
```

Expected: PASS；学习指南和练习审核行为不变，AI 课堂批准后存在同版本 manifest。

- [ ] **Step 5: 提交发布接入**

```powershell
git add backend/src/app/standard_resources backend/src/app/api/standard_resources.py backend/src/tests/standard_resources
git commit -m "feat: freeze learning manifests on classroom approval"
```

## Task 5: 提供角色安全的资源学习 API

**Files:**
- Create: `backend/src/app/schemas/resource_learning.py`
- Create: `backend/src/app/api/resource_learning.py`
- Modify: `backend/src/app/resource_learning/__init__.py`
- Modify: `backend/src/app/bootstrap.py`
- Modify: `backend/src/app/api/courses.py`
- Test: `backend/src/tests/resource_learning/test_api.py`

- [ ] **Step 1: 写学生本人、教师聚合和越权失败测试**

```python
def test_student_can_write_only_own_session(api):
    started = api.student.post("/api/courses/course-1/resources/classroom-1/versions/3/learning/sessions")
    assert started.status_code == 201
    payload = started.json()
    assert "student_id" not in payload
    denied = api.student.get("/api/courses/course-1/resources/classroom-1/versions/3/learning/students/student-2")
    assert denied.status_code == 403


def test_client_cannot_post_progress_or_correctness(api):
    response = api.student.post(api.events_path, json={"events": [{
        "event_id": "e1", "sequence_number": 1, "event_type": "timeline_heartbeat",
        "scene_id": "s1", "timeline_from_ms": 0, "timeline_to_ms": 10_000,
        "progress_percent": 100, "is_correct": True,
    }]})
    assert response.status_code == 422
```

- [ ] **Step 2: 运行 API 测试并确认红灯**

```powershell
python -m pytest tests/resource_learning/test_api.py -q
```

Expected: FAIL，路由与 schema 尚不存在。

- [ ] **Step 3: 实现 Pydantic 合约和路由**

实现以下固定路由：

```text
GET  /api/courses/{course_id}/resource-learning/me
GET  /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/me
POST /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/sessions
POST /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/sessions/{session_id}/events:batch
POST /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/questions:submit
POST /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/sessions/{session_id}/end
GET  /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/analytics
GET  /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/students
GET  /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/students/{student_id}
```

事件 schema 使用 `extra="forbid"`，禁止客户端夹带百分比、正确率和完成状态：

```python
class ResourceLearningEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=200)
    sequence_number: int = Field(ge=1)
    event_type: Literal["scene_entered", "timeline_heartbeat", "playback_paused",
                        "scene_completed", "demo_entered", "demo_interacted", "demo_completed"]
    scene_id: str = Field(min_length=1, max_length=240)
    timeline_from_ms: int | None = Field(default=None, ge=0)
    timeline_to_ms: int | None = Field(default=None, ge=0)
    action_id: str | None = Field(default=None, max_length=240)
    occurred_at: datetime

class ResourceQuestionSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)
    answers: dict[str, str | list[str]]
```

本人进度响应包含学生安全的 manifest 投影：只返回 `scene_id`、`kind`、`expected_duration_ms`、`required_action_ids` 和必答题 ID，不返回 `scoring_values`、标准答案或解析。播放器以该投影驱动 tracker，服务端仍以私有 manifest 判定和评分。

学生进度接口从 `principal.user_id` 取身份。教师 analytics/students 接口使用 `require_course_edit`。在 `bootstrap.py` 注册新 router。

同时实现课程级批量读取 `GET /api/courses/{course_id}/resource-learning/me`，一次返回当前学生对本课程所有 approved classroom 精确版本的进度，供资源目录渲染；资源卡片不得逐项发起 N+1 请求。

扩展 `GET /api/courses/{course_id}/classrooms/{classroom_id}` 支持可选 `resource_version`：viewer 只能读取当前 `approved_version`，owner/editor 可预览指定存在版本。响应显式包含 `version` 和 `content_hash`，防止播放器记录到错误版本。

- [ ] **Step 4: 运行 API、课程权限和课堂读取回归**

```powershell
python -m pytest tests/resource_learning/test_api.py tests/test_student_classroom_permissions.py tests/test_classroom_persistence.py -q
```

Expected: PASS；学生不能覆盖身份或计算字段，教师只能读取本课程聚合。

- [ ] **Step 5: 提交 API**

```powershell
git add backend/src/app/schemas/resource_learning.py backend/src/app/api/resource_learning.py backend/src/app/resource_learning/__init__.py backend/src/app/bootstrap.py backend/src/app/api/courses.py backend/src/tests/resource_learning/test_api.py
git commit -m "feat: expose secure resource learning APIs"
```

## Task 6: 建立前端 API 类型和学习事件缓冲器

**Files:**
- Create: `frontend/src/stitch/api/resourceLearning.ts`
- Modify: `frontend/src/stitch/api/types.ts`
- Create: `frontend/src/openmaic/resourceLearningTracker.ts`
- Create: `frontend/src/openmaic/resourceLearningTracker.test.ts`
- Modify: `frontend/src/stitch/api/classroom.ts`

- [ ] **Step 1: 写前端 tracker 失败测试**

```typescript
test('flushes only contiguous explanation playback and pauses during QA', async () => {
  const sent: ResourceLearningEventPayload[][] = [];
  const tracker = new ResourceLearningTracker({
    heartbeatMs: 10_000,
    send: async (events) => { sent.push(events); },
    now: fakeClock.now,
  });
  tracker.enterExplanation('scene-1', 60_000);
  tracker.play();
  fakeClock.advance(12_000);
  await tracker.flush();
  tracker.interrupt();
  fakeClock.advance(30_000);
  await tracker.flush();
  assert.deepEqual(sent.flat().filter((event) => event.event_type === 'timeline_heartbeat')
    .map(({ timeline_from_ms, timeline_to_ms }) => [timeline_from_ms, timeline_to_ms]), [[0, 12_000]]);
});
```

另写测试覆盖：场景切换自动 flush、演示只发 demo 事件、重复 flush 不重复区间、失败事件进入 localStorage outbox、成功后清除、序号连续。

- [ ] **Step 2: 运行 tracker 测试并确认红灯**

```powershell
pnpm test -- src/openmaic/resourceLearningTracker.test.ts
```

Expected: FAIL，tracker 与 API 类型不存在。

- [ ] **Step 3: 实现前端类型、API 客户端和缓冲器**

`types.ts` 添加 `ResourceLearningProgress`、`ResourceLearningSession`、`ResourceLearningAnalytics` 和事件 payload。`resourceLearning.ts` 提供：

```typescript
const base = (courseId: string, resourceId: string, version: number) =>
  `/api/courses/${encodeURIComponent(courseId)}/resources/${encodeURIComponent(resourceId)}/versions/${version}/learning`;

export const getMyResourceLearningProgress = (courseId: string, resourceId: string, version: number) =>
  apiRequest<ResourceLearningProgress>(`${base(courseId, resourceId, version)}/me`);
export const listMyCourseResourceLearningProgress = (courseId: string) =>
  apiRequest<ResourceLearningProgress[]>(`/api/courses/${encodeURIComponent(courseId)}/resource-learning/me`);
export const startResourceLearningSession = (courseId: string, resourceId: string, version: number) =>
  apiRequest<ResourceLearningSession>(`${base(courseId, resourceId, version)}/sessions`, { method: 'POST' });
export const sendResourceLearningEvents = (courseId: string, resourceId: string, version: number, sessionId: string, events: ResourceLearningEventPayload[]) =>
  apiRequest<ResourceLearningProgress>(`${base(courseId, resourceId, version)}/sessions/${encodeURIComponent(sessionId)}/events:batch`, { method: 'POST', body: JSON.stringify({ events }) });
export const submitResourceQuestions = (courseId: string, resourceId: string, version: number, idempotencyKey: string, answers: QuizAnswers) =>
  apiRequest<ResourceLearningProgress>(`${base(courseId, resourceId, version)}/questions:submit`, { method: 'POST', body: JSON.stringify({ idempotency_key: idempotencyKey, answers }) });
export const endResourceLearningSession = (courseId: string, resourceId: string, version: number, sessionId: string) =>
  apiRequest<ResourceLearningProgress>(`${base(courseId, resourceId, version)}/sessions/${encodeURIComponent(sessionId)}/end`, { method: 'POST' });
export const getResourceLearningAnalytics = (courseId: string, resourceId: string, version: number) =>
  apiRequest<ResourceLearningAnalytics>(`${base(courseId, resourceId, version)}/analytics`);
```

`ResourceLearningTracker` 只接受当前场景类型和标准时长，不计算最终百分比。每 10 秒或在暂停、中断、切页、卸载前 flush；每次区间最大 15 秒。使用 `navigator.sendBeacon` 不适合带现有 Bearer token，卸载时改为 `fetch(..., {keepalive: true})`，失败则写入带资源版本的 localStorage outbox，下次进入同一版本按序补传。

`getClassroom(courseId, classroomId, resourceVersion?)` 把版本作为查询参数，并保留现有音频 URL 解析。

- [ ] **Step 4: 运行 tracker、API client 和类型检查**

```powershell
pnpm test -- src/openmaic/resourceLearningTracker.test.ts src/stitch/api/classroom.test.ts
pnpm exec tsc --noEmit
```

Expected: PASS；TypeScript 无新增错误。

- [ ] **Step 5: 提交前端基础设施**

```powershell
git add frontend/src/stitch/api/resourceLearning.ts frontend/src/stitch/api/types.ts frontend/src/openmaic/resourceLearningTracker.ts frontend/src/openmaic/resourceLearningTracker.test.ts frontend/src/stitch/api/classroom.ts
git commit -m "feat: add classroom learning event tracker"
```

## Task 7: 将播放器和课堂习题接入资源学习会话

**Files:**
- Modify: `frontend/src/stitch/pages/ClassroomPlayer.tsx`
- Modify: `frontend/src/openmaic/ClassroomSceneRenderer.tsx`
- Modify: `frontend/src/openmaic/QuizScenePlayer.tsx`
- Modify: `frontend/src/openmaic/quizScene.ts`
- Create: `frontend/src/openmaic/QuizScenePlayer.test.ts`
- Create: `frontend/src/stitch/pages/classroomResourceLearning.test.ts`

- [ ] **Step 1: 写“仅学生标准资源模式记录”的失败测试**

```typescript
test('resource learning activates only for a student with an exact approved version', () => {
  assert.equal(shouldTrackResourceLearning({ role: 'student', courseRole: 'viewer', resourceVersion: 3 }), true);
  assert.equal(shouldTrackResourceLearning({ role: 'teacher', courseRole: 'owner', resourceVersion: 3 }), false);
  assert.equal(shouldTrackResourceLearning({ role: 'student', courseRole: 'viewer', resourceVersion: null }), false);
});

test('quiz submission persists all non-empty answers even when every answer is wrong', async () => {
  const payload = buildResourceQuestionSubmission(questions, { q1: 'wrong', q2: 'wrong' });
  assert.deepEqual(Object.keys(payload.answers), ['q1', 'q2']);
});
```

- [ ] **Step 2: 运行组件辅助测试并确认红灯**

```powershell
pnpm test -- src/openmaic/QuizScenePlayer.test.ts src/stitch/pages/classroomResourceLearning.test.ts
```

Expected: FAIL，激活判定和提交回调不存在。

- [ ] **Step 3: 接入播放器生命周期和习题提交**

`ClassroomPlayer` 读取 `resource_version` 查询参数；仅 `user.role === "student" && courseRole === "viewer" && resource_version` 时启动 session。使用现有 `playback.status` 驱动 tracker：

```typescript
useEffect(() => {
  if (!tracker || !currentScene) return;
  tracker.enterScene(currentScene.id, resolveLearningSceneKind(currentScene), manifestDuration(currentScene.id));
}, [currentScene?.id, playback.revision, tracker]);

useEffect(() => {
  if (!tracker) return;
  if (playback.status === 'playing') tracker.play();
  else if (playback.status === 'interrupted') tracker.interrupt();
  else tracker.pause();
}, [playback.status, tracker]);
```

tracker 在每个 playback revision 内从时间线 0 开始累计连续的 `playing` 内容时间，暂停、QA 中断和切页时冻结游标，并按 manifest 的 `expected_duration_ms` 截断。场景正常触发 `onComplete` 时 flush 到该 explanation 场景标准结尾；只切页而没有完成回调时，仅提交已经连续播放的区间。

`QuizScenePlayerProps` 新增：

```typescript
onSubmitAnswers?: (answers: QuizAnswers) => Promise<void>;
submissionState?: 'idle' | 'saving' | 'saved' | 'failed';
```

点击提交时先验证每道必答题有非空答案，再调用服务端；成功后才 `setSubmitted(true)` 并显示解析。错误答案仍是成功提交。重新作答保留服务端历史，只清除本地当前草稿。

演示场景进入时发 `demo_entered`，受支持 widget 交互发 `demo_interacted`；没有 widget 回调的演示至少记录进入和场景完成。

- [ ] **Step 4: 运行播放器、Quiz、QA 中断和构建回归**

```powershell
pnpm test -- src/openmaic/QuizScenePlayer.test.ts src/stitch/pages/classroomResourceLearning.test.ts src/stitch/classroomQa/useClassroomInterruption.test.ts src/openmaic/pagePlaybackController.test.ts
pnpm build
```

Expected: PASS；QA 中断期间不产生 heartbeat，教师预览不创建 session。

- [ ] **Step 5: 提交播放器接入**

```powershell
git add frontend/src/stitch/pages/ClassroomPlayer.tsx frontend/src/openmaic/ClassroomSceneRenderer.tsx frontend/src/openmaic/QuizScenePlayer.tsx frontend/src/openmaic/quizScene.ts frontend/src/openmaic/QuizScenePlayer.test.ts frontend/src/stitch/pages/classroomResourceLearning.test.ts
git commit -m "feat: record classroom playback and quiz participation"
```

## Task 8: 在学生资源卡片和播放器展示独立进度

**Files:**
- Create: `frontend/src/stitch/course/knowledge/ResourceLearningProgress.tsx`
- Create: `frontend/src/stitch/course/knowledge/resourceLearning.css`
- Modify: `frontend/src/stitch/course/knowledge/StandardLearningResources.tsx`
- Modify: `frontend/src/stitch/course/knowledge/standardLearningResourcesPresentation.ts`
- Modify: `frontend/src/stitch/shared/routes/roleCourseRouteResolver.ts`
- Modify: `frontend/src/stitch/pages/ClassroomPlayer.tsx`
- Create: `frontend/src/stitch/course/knowledge/resourceLearningPresentation.test.ts`

- [ ] **Step 1: 写资源学习展示与精确版本链接失败测试**

```typescript
test('student classroom link carries the approved resource version', () => {
  assert.equal(buildStudentClassroomLearningHref('course-1', 'classroom-1', 3),
    '#classroom-player?course_id=course-1&classroom_id=classroom-1&resource_version=3');
});

test('progress copy keeps coverage and questions separate', () => {
  assert.deepEqual(resourceLearningLabels(progress({ coverage: 83, answered: 3, required: 3 })), {
    coverage: '讲解完整度 83%', questions: '习题进度 3/3', status: '已完成'
  });
});
```

- [ ] **Step 2: 运行展示测试并确认红灯**

```powershell
pnpm test -- src/stitch/course/knowledge/resourceLearningPresentation.test.ts
```

Expected: FAIL，链接和展示 helper 尚不存在。

- [ ] **Step 3: 实现学生双指标 UI**

学生可见的 approved classroom 卡片增加“开始学习/继续学习”按钮和：

```text
讲解完整度 68%
习题进度 2/3
学习中
```

完成后显示首次 `completed_at`。不得显示综合进度条或“测评通过”。`behavior_only` 显示“已记录学习行为”，不显示“已完成”。

播放器非演示模式增加紧凑状态条：讲解完整度、习题数、同步状态和完成状态。播放器返回链接使用 `buildRoleCourseHash`，学生返回学生课程知识/资源页，教师仍返回课堂工作台。

- [ ] **Step 4: 运行资源展示、路由和构建测试**

```powershell
pnpm test -- src/stitch/course/knowledge/resourceLearningPresentation.test.ts src/stitch/shared/routes/roleCourseRouteResolver.test.ts src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts
pnpm build
```

Expected: PASS；学生与教师路由保持角色正确。

- [ ] **Step 5: 提交学生体验**

```powershell
git add frontend/src/stitch/course/knowledge frontend/src/stitch/shared/routes/roleCourseRouteResolver.ts frontend/src/stitch/pages/ClassroomPlayer.tsx
git commit -m "feat: show student classroom learning progress"
```

## Task 9: 提供教师资源学习分析

**Files:**
- Create: `backend/src/app/resource_learning/analytics.py`
- Modify: `backend/src/app/resource_learning/service.py`
- Modify: `backend/src/app/api/resource_learning.py`
- Create: `frontend/src/stitch/course/knowledge/ResourceLearningAnalytics.tsx`
- Modify: `frontend/src/stitch/course/knowledge/StandardLearningResources.tsx`
- Test: `backend/src/tests/resource_learning/test_analytics.py`
- Create: `frontend/src/stitch/course/knowledge/resourceLearningAnalytics.test.ts`

- [ ] **Step 1: 写聚合分母和队列失败测试**

```python
def test_analytics_separates_coverage_question_and_demo_metrics(service):
    result = service.get_analytics(course_id="course-1", resource_id="classroom-1", resource_version=3, teacher_id="teacher-1")
    assert result.enrolled_students == 4
    assert result.completed_students == 1
    assert result.completion_rate == 0.25
    assert result.average_explanation_coverage_percent == 55.0
    assert result.all_questions_answered_students == 2
    assert result.demo_view_students == 3
    assert result.queues["coverage_ready_questions_pending"] == 1
```

题目分析测试必须分别断言作答率、首次正确率、最终正确率、选项分布和知识点错误数；每个比例保留 numerator 与 denominator。

- [ ] **Step 2: 运行分析测试并确认红灯**

```powershell
python -m pytest tests/resource_learning/test_analytics.py -q
pnpm test -- src/stitch/course/knowledge/resourceLearningAnalytics.test.ts
```

Expected: FAIL，聚合器和面板不存在。

- [ ] **Step 3: 实现教师聚合和五类学生队列**

后端只返回当前课程聚合和经教师显式打开的学生列表。队列键固定为：

```python
QUEUE_KEYS = (
    "not_started",
    "coverage_pending",
    "coverage_ready_questions_pending",
    "questions_ready_coverage_pending",
    "completed",
)
```

前端资源卡片为 owner/editor 提供“学习分析”入口，展示课程学生、已开始、已完成、平均讲解完整度、全部作答人数、逐题分析、知识点错误和演示访问。资源分析不得混入教师任务完成率。

- [ ] **Step 4: 运行分析、权限和前端测试**

```powershell
python -m pytest tests/resource_learning/test_analytics.py tests/resource_learning/test_api.py -q
pnpm test -- src/stitch/course/knowledge/resourceLearningAnalytics.test.ts
pnpm build
```

Expected: PASS；比例都带分母，学生 API 无法读取班级聚合。

- [ ] **Step 5: 提交教师分析**

```powershell
git add backend/src/app/resource_learning backend/src/app/api/resource_learning.py backend/src/tests/resource_learning frontend/src/stitch/course/knowledge
git commit -m "feat: add classroom resource learning analytics"
```

## Task 10: 让教师任务复用同版本资源证据

**Files:**
- Create: `backend/src/app/resource_learning/task_evidence.py`
- Modify: `backend/src/app/resource_learning/service.py`
- Modify: `backend/src/app/learning/service.py`
- Modify: `backend/src/app/learning/models.py`
- Modify: `backend/src/app/schemas/learning.py`
- Modify: `frontend/src/stitch/api/types.ts`
- Modify: `frontend/src/stitch/pages/CourseLearning.tsx`
- Test: `backend/src/tests/resource_learning/test_task_evidence.py`
- Test: `frontend/src/stitch/pages/courseLearningPresentation.test.ts`

- [ ] **Step 1: 写同版本复用和跨版本拒绝失败测试**

```python
def test_published_task_reuses_prior_same_version_completion(adapter, completed_progress, task_v3):
    refs = adapter.initialize_task(task_v3, student_ids=["student-1"])
    assert refs[0].condition_status == "satisfied"
    assert refs[0].resource_completed_at == completed_progress.completed_at


def test_task_does_not_reuse_different_resource_version(adapter, completed_progress_v2, task_v3):
    refs = adapter.initialize_task(task_v3, student_ids=["student-1"])
    assert refs[0].condition_status == "pending"
```

另写测试：资源稍后完成更新 pending 引用；重复同步幂等；任务关闭/删除不改资源进度；任务引用非 classroom 资源不创建证据引用；任务发布后新加入课程的学生首次读取任务时会补建 pending/satisfied 引用。

- [ ] **Step 2: 运行任务证据测试并确认红灯**

```powershell
python -m pytest tests/resource_learning/test_task_evidence.py -q
```

Expected: FAIL，适配器和任务投影不存在。

- [ ] **Step 3: 实现只读证据适配器和任务展示投影**

`TaskResourceEvidenceAdapter` 从 `LearningTaskResourceSnapshot` 读取 `source_material_type == "classroom"`、`origin_type == "standard"`、`source_version`，建立精确版本引用。`ResourceLearningService` 首次形成 completed 时调用幂等 `satisfy_for_progress(progress)` 更新所有匹配 pending 引用。

在 `LearningService.publish_task()` 成功后调用 `initialize_task()`；失败不回滚已发布任务，但记录可重试同步错误并允许再次调用初始化。`list_tasks()` 为当前学生幂等调用 `ensure_for_student()`，保证任务发布后才入课的学生也能得到资源条件。任务响应增加：

```python
class TaskResourceEvidenceResponse(BaseModel):
    resource_id: str
    resource_version: int
    condition_status: Literal["pending", "satisfied"]
    evidence_source: Literal["course_resource_learning"]
    resource_completed_at: str | None
```

学生和教师任务页只展示“资源条件已满足/待完成”及证据版本、完成时间，不把它映射成现有 `completion_basis`，也不自动将任务 `status` 改为 completed。

- [ ] **Step 4: 运行任务、正式测评和前端回归**

```powershell
python -m pytest tests/resource_learning/test_task_evidence.py tests/learning tests/assessment -q
pnpm test -- src/stitch/pages/courseLearningPresentation.test.ts src/stitch/course/learning/learningEvidencePresentation.test.ts
pnpm build
```

Expected: PASS；资源证据与正式测评完成口径保持分离。

- [ ] **Step 5: 提交任务证据复用**

```powershell
git add backend/src/app/resource_learning backend/src/app/learning backend/src/app/schemas/learning.py backend/src/tests/resource_learning frontend/src/stitch/api/types.ts frontend/src/stitch/pages/CourseLearning.tsx frontend/src/stitch/pages/courseLearningPresentation.test.ts
git commit -m "feat: reuse classroom learning evidence in tasks"
```

## Task 11: 加固恢复、可观察性和事件保留

**Files:**
- Create: `backend/src/app/resource_learning/metrics.py`
- Modify: `backend/src/app/resource_learning/repository.py`
- Modify: `backend/src/app/resource_learning/service.py`
- Modify: `frontend/src/openmaic/resourceLearningTracker.ts`
- Test: `backend/src/tests/resource_learning/test_recovery.py`
- Modify: `frontend/src/openmaic/resourceLearningTracker.test.ts`

- [ ] **Step 1: 写重启恢复、补传和投影重算失败测试**

```python
def test_projection_can_rebuild_from_coverage_and_attempts(repository, service):
    seed_coverage_and_attempts_without_progress(repository)
    rebuilt = service.rebuild_progress(course_id="course-1", resource_id="classroom-1",
                                       resource_version=3, student_id="student-1")
    assert rebuilt.explanation_coverage_percent == 80.0
    assert rebuilt.answered_question_count == rebuilt.required_question_count
    assert rebuilt.status == "completed"
```

前端测试模拟第一次批量发送失败、刷新后重建 tracker、第二次成功，并断言 event ID 与序号保持不变而非重新生成。

- [ ] **Step 2: 运行恢复测试并确认红灯**

```powershell
python -m pytest tests/resource_learning/test_recovery.py -q
pnpm test -- src/openmaic/resourceLearningTracker.test.ts
```

Expected: FAIL，重建接口和持久 outbox 恢复尚不完整。

- [ ] **Step 3: 实现幂等恢复、指标和保留边界**

实现服务端 `rebuild_progress()`，只从 manifest、validated coverage 和 question attempts 重算。增加规格 §18 指标；指标标签不得包含 student ID。

原始 heartbeat 默认保留 90 天，合并区间、题目尝试、完成时间和任务证据按课程数据策略长期保留。删除作业不级联删除资源学习表；删除课程时沿用课程数据删除流程显式清理。

前端 outbox 每个资源版本最多保留 500 个事件或 2MB，超过限制时优先合并相邻 heartbeat，不删除题目提交。UI 区分“同步中”“待同步”“同步失败”，未同步完成前不乐观显示 completed。

- [ ] **Step 4: 运行恢复和核心回归**

```powershell
python -m pytest tests/resource_learning -q
pnpm test -- src/openmaic/resourceLearningTracker.test.ts
```

Expected: PASS；服务重启和客户端刷新均能恢复一致投影。

- [ ] **Step 5: 提交可靠性加固**

```powershell
git add backend/src/app/resource_learning backend/src/tests/resource_learning frontend/src/openmaic/resourceLearningTracker.ts frontend/src/openmaic/resourceLearningTracker.test.ts
git commit -m "feat: harden resource learning recovery"
```

## Task 12: 完成真实端到端验收与文档

**Files:**
- Create: `frontend/tests/e2e/resource-learning.spec.ts`
- Modify: `frontend/tests/e2e/fixtures/learningLoop.ts`
- Create: `backend/src/scripts/seed_resource_learning_e2e.py`
- Create: `docs/superpowers/acceptance/2026-08-31-course-resource-learning-tracking-acceptance-cn.md`
- Modify: `项目总览地图.md`

- [ ] **Step 1: 写完整浏览器验收场景**

使用 deterministic fixture 直接准备一个 approved classroom v3：三个普通讲解场景合计约 10 秒、一个 quiz 场景含三道必答题、一个 interactive 演示场景。测试必须验证：

`seed_resource_learning_e2e.py` 使用与生产相同的 `PostgresMaterialRepository`、`StandardResourceReviewService` 和 `ResourceLearningRepository` 写入 fixture，不增加生产 seed HTTP 入口。`learningLoop.ts` 在启动后端前为 worker 创建独立 `app.db`，设置形如 `DATABASE_URL=sqlite+pysqlite:///D:/test-results/worker/app.db` 的绝对 URL，运行 `python -m alembic upgrade head` 和该 seed 脚本，再把相同 `DATABASE_URL` 传给 Uvicorn。

在 `fixtures/learningLoop.ts` 新增并导出 `playExplanationToCoverage(page, percent)`；它按 manifest 标准时长依次播放 explanation 场景到目标覆盖率，并把播放器错误抛给测试。约 10 秒的 fixture 使 80% 主链路无需修改生产时钟，也不引入测试专用播放器分支。

```typescript
test('student completes a classroom with 80 percent explanation and all questions', async ({ studentPage, request }) => {
  await studentPage.goto(`/#student-course-knowledge?course_id=${learningCourseId}`);
  await studentPage.getByRole('link', { name: /开始学习.*进程调度/ }).click();
  await playExplanationToCoverage(studentPage, 80);
  await answerEveryRequiredQuestion(studentPage, 'wrong');
  await expect(studentPage.getByText('讲解完整度 80%')).toBeVisible();
  await expect(studentPage.getByText('习题进度 3/3')).toBeVisible();
  await expect(studentPage.getByText('当前状态：已完成')).toBeVisible();
});
```

同一 spec 继续验证：100% 播放少一题仍学习中、全部答错仍完成、快速翻页不增加、重复区间去重、演示不增加、QA 中断不增加、同版本任务复用、不同版本不复用、重登恢复、伪造百分比返回 422。

- [ ] **Step 2: 运行 E2E 并确认首轮失败点均来自未接通链路**

```powershell
pnpm exec playwright test tests/e2e/resource-learning.spec.ts --project=chromium
```

Expected: 若前序任务均完成则 PASS；若有失败，只修复本规格链路，不通过降低断言或改阈值绕过。

- [ ] **Step 3: 运行全量相关验证**

Backend from `backend/src`:

```powershell
python -m pytest tests/resource_learning tests/standard_resources tests/learning tests/assessment tests/test_classroom_service.py tests/test_classroom_qa_service.py -q
```

Frontend from `Edu_AI`:

```powershell
pnpm test
pnpm lint
pnpm build
pnpm exec playwright test tests/e2e/resource-learning.spec.ts tests/e2e/learning-task-assessment-loop.spec.ts tests/e2e/resources-and-classroom.spec.ts --project=chromium
```

Expected: 全部 PASS；不存在 AI 课堂、标准资源、正式测评或教师任务 P0/P1 回归。

- [ ] **Step 4: 写验收证据并更新项目地图**

验收文档逐项记录 CRLT-FR-001 至 CRLT-FR-012、CRLT-NFR-001 至 CRLT-NFR-006 对应测试命令、结果和截图路径。项目地图将“课程资源学习记录”标记为完成前，必须同时具备后端、前端和真实浏览器证据。

- [ ] **Step 5: 提交验收收尾**

```powershell
git add frontend/tests/e2e/resource-learning.spec.ts frontend/tests/e2e/fixtures/learningLoop.ts backend/src/scripts/seed_resource_learning_e2e.py docs/superpowers/acceptance/2026-08-31-course-resource-learning-tracking-acceptance-cn.md 项目总览地图.md
git commit -m "test: verify classroom resource learning loop"
```

## 规格覆盖映射

| 规格要求 | 实施任务 |
| --- | --- |
| CRLT-FR-001 资源学习与任务独立 | Task 2、Task 10 |
| CRLT-FR-002 按学生/课程/资源/版本聚合 | Task 2、Task 3 |
| CRLT-FR-003 有效时间线区间 | Task 1、Task 3、Task 6、Task 7 |
| CRLT-FR-004 80% 讲解阈值 | Task 3、Task 12 |
| CRLT-FR-005 所有必答题提交 | Task 1、Task 3、Task 7 |
| CRLT-FR-006 正确率不设通过线 | Task 3、Task 7、Task 12 |
| CRLT-FR-007 演示不进入完整度 | Task 1、Task 7、Task 12 |
| CRLT-FR-008 双条件完成 | Task 3、Task 12 |
| CRLT-FR-009 教师四级分析 | Task 9 |
| CRLT-FR-010 同版本证据复用 | Task 10、Task 12 |
| CRLT-FR-011 跨版本隔离 | Task 2、Task 10、Task 12 |
| CRLT-FR-012 学生分项展示 | Task 8 |
| CRLT-NFR-001 客户端不能写计算状态 | Task 5 |
| CRLT-NFR-002 幂等 | Task 3、Task 6、Task 10 |
| CRLT-NFR-003 manifest 不可变 | Task 2、Task 4 |
| CRLT-NFR-004 重启与重登一致 | Task 11、Task 12 |
| CRLT-NFR-005 分析故障不阻断学习 | Task 9、Task 11 |
| CRLT-NFR-006 认证与课程角色权限 | Task 5、Task 9 |

## 最终完成检查

执行者在宣称完成前必须确认：

- [ ] 课程资源学习表和现有任务学习表没有共享主键或隐式状态映射。
- [ ] 资源习题没有正确率通过线，全部答错但全部提交可以完成。
- [ ] 演示和 QA 行为没有进入讲解完整度。
- [ ] 播放完整度只能由服务端基于已验证区间计算。
- [ ] 同版本任务证据可复用，不同版本严格隔离。
- [ ] 学生、教师和任务页面对同一证据版本及时间显示一致。
- [ ] 原工作区的无关修改没有进入任何功能提交。
- [ ] 所有计划内测试命令保留最新成功输出作为验收证据。
