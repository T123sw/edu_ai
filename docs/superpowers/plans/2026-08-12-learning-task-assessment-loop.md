# Learning Task Assessment Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为每个新发布的学习任务建立强制正式测评，贯通已有习题导入、无习题生成、学生多次作答、服务端评分、教师复核、补学反馈和双端 Agent 事实读取。

**Architecture:** 在现有 `LearningStore → LearningService → HTTP/Agent projection` 旁增加独立测评域，以不可变 `AssessmentVersion`、学生 `AssessmentAssignment` 和追加式 `AssessmentAttempt/Review` 为事实源。测评域通过内部幂等结果端口提升学习任务的 `assessment_verified` 证据，学生不能通过公共学习事件 API 写入成绩。实施按“创作发布、学生作答、复核分析、Agent 与上线加固”四个可独立验收和推送的阶段推进。

**Tech Stack:** Python 3.12、FastAPI、Pydantic v2、SQLite/WAL、SQLAlchemy 2、PostgreSQL/Alembic、React 18、TypeScript 5.6、Vite、Node test runner、Playwright。

## Global Constraints

- 本能力上线后，每个新发布学习任务必须绑定教师确认的正式测评版本；`legacy_unassessed` 仅用于迁移前遗留任务。
- 已发布测评版本不可变；历史作答永远绑定开始作答时的版本。
- 默认及格线 60、掌握良好线 80、最多 3 次提交、最高最终成绩计入；教师可在规定范围内调整前三项。
- 客观题只能由服务端确定性评分；主观题、成果题和本期编程实现题必须由教师确认最终分。
- 本期不执行学生代码，不引入 Judge0/Piston/Docker 判题或其他不可信代码运行路径。
- 学习参与、测评提交和测评通过使用独立事实；只有最终通过才能写入 `assessment_verified`。
- 学生投影在揭示前不得返回答案、解析、评分键、私有量规或教师私有评语。
- 所有作答提交、评分、复核、发布和学习结果同步必须幂等并保留审计记录。
- SQLite 与 PostgreSQL 的模型、约束、迁移和行为必须一致。
- 每个阶段完成后运行该阶段测试、提交，并先执行普通 `git push origin main`；只有 GitHub 443 超时、连接重置或无法连接时才使用 AGENTS.md 中的单次 `curloptResolve` 命令。
- 新决策追加到 `docs/superpowers/decisions/2026-08-12-learning-task-assessment-loop.md`，记录日期、问题、采用方案、备选方案和影响。

---

## File Structure

### Backend files to create

- `Edu_AI/api/src/app/assessment/models.py`：测评、版本、题目、分配、作答、答案、复核和分析领域记录。
- `Edu_AI/api/src/app/assessment/policies.py`：阈值、题目校验、客观评分、最佳成绩和答案揭示纯规则。
- `Edu_AI/api/src/app/assessment/extractors.py`：从 `quiz` 材料与 AI 课堂 Quiz scene 提取统一题目。
- `Edu_AI/api/src/app/assessment/quality.py`：结构、答案、覆盖、重复、来源和学生投影泄露门禁。
- `Edu_AI/api/src/app/assessment/generator.py`：使用现有 QuizGenerator/LLM 基于选中材料补齐测评草稿。
- `Edu_AI/api/src/app/assessment/store.py`：SQLite 测评事务仓储与自动兼容建表。
- `Edu_AI/api/src/app/assessment/service.py`：创作、发布、作答、评分、揭示、复核和分析用例。
- `Edu_AI/api/src/app/assessment/__init__.py`：生产依赖组装与 FastAPI dependency。
- `Edu_AI/api/src/app/schemas/assessment.py`：角色安全的请求和响应模型。
- `Edu_AI/api/src/app/api/assessment.py`：教师创作、学生作答和教师分析路由。
- `Edu_AI/api/src/app/persistence/postgres_assessment_repository.py`：PostgreSQL 测评仓储。
- `Edu_AI/api/src/alembic/versions/20260812_0013_assessments.py`：测评表、约束、索引与学习任务绑定迁移。
- `Edu_AI/api/src/tests/assessment/`：领域、仓储、服务、API、安全和分析测试。
- `Edu_AI/api/src/tests/persistence/test_postgres_assessment_repository.py`：双数据库行为测试。

### Backend files to modify

- `Edu_AI/api/src/app/database/models.py`、`Edu_AI/api/src/app/database/__init__.py`：SQLAlchemy 测评模型导出。
- `Edu_AI/api/src/app/bootstrap.py`：注册 assessment router。
- `Edu_AI/api/src/app/learning/models.py`、`service.py`、`store.py`：测评状态投影和内部可信结果同步。
- `Edu_AI/api/src/app/schemas/learning.py`、`app/api/learning.py`：移除学生可写 `assessment_scored`，返回任务测评摘要。
- `Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/learning.py`、`nodes/executor.py`、`learning_context_prompt.py`：双角色测评事实与回答约束。

### Frontend files to create

- `Edu_AI/src/stitch/assessment/assessmentAuthoring.ts`：创作步骤、草稿验证和发布门禁纯函数。
- `Edu_AI/src/stitch/assessment/AssessmentEditor.tsx`：题目导入/生成、编辑、覆盖和学生预览。
- `Edu_AI/src/stitch/assessment/AssessmentRunner.tsx`：学生作答、自动保存、提交、揭示和重做。
- `Edu_AI/src/stitch/assessment/AssessmentReview.tsx`：教师待复核队列和评分量规。
- `Edu_AI/src/stitch/assessment/AssessmentAnalytics.tsx`：任务、题目、知识点和学生反馈。
- `Edu_AI/src/stitch/assessment/*.test.ts`：纯逻辑和源码契约测试。
- `Edu_AI/tests/e2e/learning-task-assessment-loop.spec.ts`：确定性浏览器闭环。

### Frontend files to modify

- `Edu_AI/src/stitch/api/types.ts`、`learning.ts`：测评契约和 API 客户端。
- `Edu_AI/src/stitch/pages/CourseLearning.tsx`、`CourseLearning.css`：教师四步创建、学生测评入口和教师反馈入口。
- `Edu_AI/src/stitch/pages/courseLearningPresentation.ts`、测试：分离学习、提交、待复核、未通过和已验证文案。
- `Edu_AI/src/stitch/pages/CourseMaterialArtifactPreview.tsx`：学生角色不再显示正式测评答案，教师与练习资源保持可配置预览。

### Documentation files to create or update

- `docs/superpowers/decisions/2026-08-12-learning-task-assessment-loop.md`：实施决策日志。
- `Edu_AI/docs/acceptance/2026-08-12-learning-task-assessment-loop-acceptance.md`：独立验收标准和证据记录。
- `docs/superpowers/plans/2026-08-12-learning-task-assessment-loop.md`：本计划，实施时逐项勾选。

---

## Phase 1 — 测评创作与强制发布门禁

### Task 1: 建立测评领域记录与纯策略

**Files:**
- Create: `Edu_AI/api/src/app/assessment/__init__.py`
- Create: `Edu_AI/api/src/app/assessment/models.py`
- Create: `Edu_AI/api/src/app/assessment/policies.py`
- Test: `Edu_AI/api/src/tests/assessment/test_assessment_policies.py`

**Interfaces:**
- Produces: `AssessmentVersionRecord`、`AssessmentItemRecord`、`AssessmentAssignmentRecord`、`AssessmentAttemptRecord`、`AssessmentAnswerRecord`、`AssessmentReviewRecord`。
- Produces: `validate_settings(pass_threshold, mastery_threshold, max_attempts)`、`grade_objective_item(item, answer)`、`select_best_attempt(attempts)`、`can_reveal_answers(assignment)`。
- Consumes: 标准化题型 `single_choice | multiple_choice | judge | structured_blank | code_output | code_trace | debug_fix | short_answer | artifact | code_implementation`。

- [x] **Step 1: 写失败测试**

```python
def test_default_policy_and_best_score_are_deterministic():
    policy = validate_settings(60, 80, 3)
    assert policy.max_attempts == 3
    attempts = [
        attempt(final_score=50, status="graded"),
        attempt(final_score=75, status="graded"),
        attempt(final_score=65, status="graded"),
    ]
    assert select_best_attempt(attempts).final_score == 75


def test_subjective_item_never_receives_final_ai_score():
    item = item_record(item_type="short_answer", grading_provider="rubric_ai_teacher")
    result = grade_objective_item(item, {"text": "answer"})
    assert result.status == "pending_review"
    assert result.final_score is None
```

- [x] **Step 2: 运行红灯测试**

Run: `cd Edu_AI/api/src; python -m pytest tests/assessment/test_assessment_policies.py -q`

Expected: FAIL，`app.assessment` 尚不存在。

- [x] **Step 3: 实现不可变 dataclass 与纯策略**

`validate_settings` 必须拒绝阈值越界、`mastery_threshold < pass_threshold` 和次数不在 1–10；多选答案按稳定 option ID 集合比较，结构化填空先 trim/casefold 后比较，主观类题型只返回 `pending_review`。

- [x] **Step 4: 运行测试并提交**

Run: `cd Edu_AI/api/src; python -m pytest tests/assessment/test_assessment_policies.py -q`

Expected: PASS。

Commit: `git commit -m "feat: add assessment domain policies"`

### Task 2: 建立 SQLite/PostgreSQL 持久化与版本约束

**Files:**
- Create: `Edu_AI/api/src/app/assessment/store.py`
- Create: `Edu_AI/api/src/app/persistence/postgres_assessment_repository.py`
- Create: `Edu_AI/api/src/alembic/versions/20260812_0013_assessments.py`
- Modify: `Edu_AI/api/src/app/database/models.py`
- Modify: `Edu_AI/api/src/app/database/__init__.py`
- Test: `Edu_AI/api/src/tests/assessment/test_assessment_store.py`
- Test: `Edu_AI/api/src/tests/persistence/test_postgres_assessment_repository.py`

**Interfaces:**
- Produces: `AssessmentStore.create_draft`、`replace_draft_items`、`publish_version`、`get_task_assessment`、`create_assignment`、`create_attempt`、`save_answers`、`submit_attempt`、`append_review`、`list_task_attempts`。
- Enforces: 已发布版本不可修改，`task_id` 唯一 assessment，`assignment_id + attempt_number` 唯一，同一 assignment 仅一个进行中 attempt。

- [x] **Step 1: 写事务与不可变失败测试**

```python
def test_publish_freezes_content_and_is_idempotent(store):
    draft = store.create_draft(draft_record())
    store.replace_draft_items(draft.version_id, [objective_item()])
    first = store.publish_version(draft.version_id, published_by="teacher-1")
    second = store.publish_version(draft.version_id, published_by="teacher-1")
    assert first.content_hash == second.content_hash
    with pytest.raises(AssessmentStoreError, match="VERSION_IMMUTABLE"):
        store.replace_draft_items(first.version_id, [different_item()])
```

- [x] **Step 2: 运行红灯测试**

Run: `cd Edu_AI/api/src; python -m pytest tests/assessment/test_assessment_store.py tests/persistence/test_postgres_assessment_repository.py -q`

Expected: FAIL，仓储和 ORM 模型缺失。

- [x] **Step 3: 实现七张测评表和迁移**

迁移创建 `assessments`、`assessment_versions`、`assessment_items`、`assessment_assignments`、`assessment_attempts`、`assessment_answers`、`assessment_reviews`；索引覆盖 `task_id`、`course_id`、`student_id`、`status`、`assessment_version_id`。SQLite `_initialize()` 使用同名字段和唯一约束；PostgreSQL repository 不允许回退到 SQLite。

- [x] **Step 4: 验证迁移与仓储**

Run:

```powershell
cd Edu_AI/api/src
python -m pytest tests/assessment/test_assessment_store.py tests/persistence/test_postgres_assessment_repository.py tests/database/test_alembic_revision_chain.py -q
python -m alembic heads
```

Expected: PASS，Alembic 只有一个 head `20260812_0013`。

Commit: `git commit -m "feat: persist versioned learning assessments"`

### Task 3: 实现已有习题抽取、材料生成与质量门禁

**Files:**
- Create: `Edu_AI/api/src/app/assessment/extractors.py`
- Create: `Edu_AI/api/src/app/assessment/quality.py`
- Create: `Edu_AI/api/src/app/assessment/generator.py`
- Test: `Edu_AI/api/src/tests/assessment/test_assessment_authoring.py`

**Interfaces:**
- Produces: `extract_assessment_items(materials) -> ExtractionResult`，支持 `quiz.questions` 和 `classroom.scenes[].content.questions`。
- Produces: `AssessmentDraftGenerator.generate(materials, task, coverage_gaps, settings) -> list[AssessmentItemRecord]`，复用 `get_fallback_llm()` 与 `QuizGenerator.build_artifact_from_raw()`。
- Produces: `AssessmentQualityService.validate(draft) -> QualityReport`，严重问题使 `publishable=False`。

- [x] **Step 1: 写已有习题优先和无习题补齐测试**

```python
def test_existing_quiz_is_imported_without_duplicate_generation(generator_spy):
    result = authoring.build_draft(task(), [quiz_material(two_questions())])
    assert len(result.items) == 2
    assert {item.created_origin for item in result.items} == {"imported"}
    generator_spy.assert_not_called()


def test_missing_coverage_generates_only_gaps(generator_spy):
    result = authoring.build_draft(task(points=["loops", "recursion"]), [report_material()])
    assert generator_spy.call_args.kwargs["coverage_gaps"] == ["loops", "recursion"]
    assert all(item.source_refs for item in result.items)
```

- [x] **Step 2: 运行红灯测试**

Run: `cd Edu_AI/api/src; python -m pytest tests/assessment/test_assessment_authoring.py -q`

Expected: FAIL，抽取器、生成器和质量服务缺失。

- [x] **Step 3: 实现标准化和门禁**

已有 `choice/blank/short/judge` 映射到统一题型；题干、选项、答案和材料来源使用稳定 ID。质量门禁至少返回 `MISSING_SCORING_KEY`、`MISSING_RUBRIC`、`KNOWLEDGE_POINT_UNCOVERED`、`DUPLICATE_ITEM`、`SOURCE_MISSING`、`STUDENT_PROJECTION_LEAK`。自动生成没有可解析材料时返回 `ASSESSMENT_SOURCE_REQUIRED`。

- [x] **Step 4: 运行测试并提交**

Run: `cd Edu_AI/api/src; python -m pytest tests/assessment/test_assessment_authoring.py tests/chat/test_quiz_generator.py -q`

Expected: PASS。

Commit: `git commit -m "feat: author grounded task assessments"`

### Task 4: 建立教师创作 API、原子发布门禁和四步前端

**Files:**
- Create: `Edu_AI/api/src/app/schemas/assessment.py`
- Create: `Edu_AI/api/src/app/api/assessment.py`
- Create/Modify: `Edu_AI/api/src/app/assessment/service.py`、`__init__.py`
- Modify: `Edu_AI/api/src/app/bootstrap.py`
- Modify: `Edu_AI/api/src/app/api/learning.py`
- Create: `Edu_AI/src/stitch/assessment/assessmentAuthoring.ts`
- Create: `Edu_AI/src/stitch/assessment/AssessmentEditor.tsx`
- Modify: `Edu_AI/src/stitch/api/types.ts`、`learning.ts`
- Modify: `Edu_AI/src/stitch/pages/CourseLearning.tsx`、`CourseLearning.css`
- Test: `Edu_AI/api/src/tests/assessment/test_assessment_authoring_api.py`
- Test: `Edu_AI/src/stitch/assessment/assessmentAuthoring.test.ts`

**Interfaces:**
- Produces: detect/draft/generate/validate endpoints and replacement `POST .../tasks/{task_id}/publish` atomic use case.
- Produces: `getAssessmentPublishBlockers(draft) -> string[]` and four-step teacher wizard.

- [x] **Step 1: 写无测评禁止发布 API 测试**

```python
def test_new_task_cannot_publish_without_confirmed_assessment(teacher_client, task_id):
    response = teacher_client.post(f"/api/courses/course-1/learning/tasks/{task_id}/publish")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ASSESSMENT_REQUIRED"
```

- [x] **Step 2: 写前端发布门禁测试并运行红灯**

Run:

```powershell
cd Edu_AI/api/src; python -m pytest tests/assessment/test_assessment_authoring_api.py -q
cd ..; npm test -- src/stitch/assessment/assessmentAuthoring.test.ts
```

Expected: 两组均 FAIL。

- [x] **Step 3: 实现 API 与四步创作界面**

教师流程固定为任务目标、学习材料、正式测评、发布设置。发布请求必须带当前 `draft_revision`；服务端重新执行质量校验并在一个写事务中冻结版本和发布任务。前端不得在后端不可用时退回旧 publish 调用。

- [x] **Step 4: 阶段回归、决策记录、提交和推送**

Run:

```powershell
cd Edu_AI/api/src
python -m pytest tests/assessment/test_assessment_policies.py tests/assessment/test_assessment_store.py tests/assessment/test_assessment_authoring.py tests/assessment/test_assessment_authoring_api.py tests/learning -q
cd ../..
npm test -- src/stitch/assessment/assessmentAuthoring.test.ts src/stitch/pages/courseLearningPresentation.test.ts
npm run build
```

Expected: 全部 PASS，build 退出码 0。

Commit: `git commit -m "feat: require assessments before task publication"`

Push: `git push origin main`

---

## Phase 2 — 学生作答、服务端评分与补学重做

### Task 5: 实现测评分配、草稿、提交和客观评分

**Files:**
- Modify: `Edu_AI/api/src/app/assessment/service.py`、`store.py`、`policies.py`
- Create: `Edu_AI/api/src/alembic/versions/20260812_0014_attempt_idempotency.py`
- Test: `Edu_AI/api/src/tests/assessment/test_assessment_attempt_service.py`

**Interfaces:**
- Produces: `start_attempt`、`save_answers(expected_revision)`、`submit_attempt(idempotency_key)`、`reveal_answers`、`get_student_feedback`。
- Enforces: 草稿不占次数；提交占一次；最多 3 次默认；最高最终分；通过后可继续挑战但揭示后只能不计分练习。

- [x] **Step 1: 写三次作答和冲突失败测试**

```python
def test_three_attempts_keep_best_score_and_all_history(service):
    scores = [50, 75, 65]
    for score in scores:
        attempt = service.start_attempt(context())
        service.save_answers(attempt.attempt_id, answers_for_score(score), expected_revision=0)
        service.submit_attempt(attempt.attempt_id, idempotency_key=f"submit-{score}")
    assignment = service.get_assignment(context())
    assert assignment.attempts_used == 3
    assert assignment.best_final_score == 75
    assert [item.final_score for item in service.list_attempts(context())] == scores
```

- [x] **Step 2: 运行红灯、实现事务，再运行绿灯**

Run: `cd Edu_AI/api/src; python -m pytest tests/assessment/test_assessment_attempt_service.py -q`

Expected before/after: 首次 FAIL；实现后 PASS。并覆盖重复提交不重复扣次数、修订冲突 409、答案揭示后拒绝计分作答。

Commit: `git commit -m "feat: grade durable assessment attempts"`

### Task 6: 建立学生安全投影 API 并关闭伪造成绩入口

**Files:**
- Modify: `Edu_AI/api/src/app/api/assessment.py`
- Modify: `Edu_AI/api/src/app/schemas/assessment.py`
- Modify: `Edu_AI/api/src/app/schemas/learning.py`
- Modify: `Edu_AI/api/src/app/api/learning.py`
- Modify: `Edu_AI/api/src/app/learning/service.py`、`store.py`
- Test: `Edu_AI/api/src/tests/assessment/test_assessment_student_api.py`
- Test: `Edu_AI/api/src/tests/learning/test_learning_api.py`

**Interfaces:**
- Produces: student assessment, current attempt, answer save, submit, history, feedback and reveal endpoints.
- Produces: internal `record_verified_assessment_outcome(outcome_id, task_id, student_id, score, passed_at)`；公共事件 schema 不再包含 `assessment_scored`。

- [x] **Step 1: 写答案泄露和伪造拒绝测试**

```python
def test_student_projection_never_contains_scoring_keys(student_client, task_id):
    body = student_client.get(f"/api/courses/course-1/learning/tasks/{task_id}/assessment").json()
    serialized = json.dumps(body, ensure_ascii=False)
    assert "correct_answer" not in serialized
    assert "scoring_key" not in serialized


def test_student_cannot_submit_assessment_scored_event(student_client, task_id):
    response = student_client.post(
        f"/api/courses/course-1/learning/tasks/{task_id}/events",
        json={"event_id": "forged", "event_type": "assessment_scored", "progress_percent": 100},
    )
    assert response.status_code == 422
```

- [x] **Step 2: 实现角色投影与内部 outcome 同步**

学生题目 DTO 仅含稳定题目 ID、题型、题干、选项、分值和学生可见素材。最终通过在同一事务或 outbox 幂等同步为 `assessment_verified`；同步失败保留重试事件，客户端无补写接口。

- [x] **Step 3: 运行测试并提交**

Run: `cd Edu_AI/api/src; python -m pytest tests/assessment/test_assessment_student_api.py tests/learning/test_learning_api.py tests/learning/test_learning_service.py -q`

Expected: PASS。

Commit: `git commit -m "security: isolate trusted assessment outcomes"`

### Task 7: 实现学生作答、恢复、补学和揭示界面

**Files:**
- Create: `Edu_AI/src/stitch/assessment/assessmentRunnerState.ts`
- Create: `Edu_AI/src/stitch/assessment/AssessmentRunner.tsx`
- Create: `Edu_AI/src/stitch/assessment/assessmentRunner.test.ts`
- Modify: `Edu_AI/src/stitch/api/types.ts`、`learning.ts`
- Modify: `Edu_AI/src/stitch/pages/CourseLearning.tsx`、`CourseLearning.css`
- Modify: `Edu_AI/src/stitch/pages/courseLearningPresentation.ts`、测试

**Interfaces:**
- Produces: `deriveAssessmentAction(summary)`、`mergeServerDraft(local, remote)`、学生安全题目控件和状态文案。
- Consumes: Task 6 student API。

- [x] **Step 1: 写状态机失败测试**

测试必须断言 `not_attempted → in_progress → pending_review|graded → needs_retry|verified_completed`，以及 50→75→65 仍显示最佳 75；`answers_revealed_at` 后不显示“再次计分作答”。

- [x] **Step 2: 运行红灯并实现界面**

Run: `cd Edu_AI; npm test -- src/stitch/assessment/assessmentRunner.test.ts src/stitch/pages/courseLearningPresentation.test.ts`

Expected before/after: 首次 FAIL；实现后 PASS。

- [x] **Step 3: 阶段回归、提交和推送**

Run:

```powershell
cd Edu_AI/api/src
python -m pytest tests/assessment tests/learning -q
cd ../..
npm test -- src/stitch/assessment/assessmentRunner.test.ts src/stitch/assessment/assessmentAuthoring.test.ts src/stitch/pages/courseLearningPresentation.test.ts
npm run lint
npm run build
```

Expected: pytest/test/build PASS；lint 允许记录既有 warning，但新增文件不得有 error。

Commit: `git commit -m "feat: add student assessment experience"`

Push: `git push origin main`

---

## Phase 3 — 主观复核与教师可行动反馈

### Task 8: 实现 AI 建议、教师复核和追加式审计

**Files:**
- Modify: `Edu_AI/api/src/app/assessment/service.py`、`store.py`
- Create: `Edu_AI/api/src/app/assessment/rubric.py`
- Modify: `Edu_AI/api/src/app/api/assessment.py`、`schemas/assessment.py`
- Test: `Edu_AI/api/src/tests/assessment/test_assessment_review.py`

**Interfaces:**
- Produces: `RubricSuggestion`，字段为建议分、分维度得分、理由、置信度、量规版本、模型版本和时间。
- Produces: `finalize_review(attempt_id, item_scores, reason_code, student_comment, teacher_id)`。
- Enforces: AI 建议不能成为最终分；教师决定只追加；历史调整重算最佳成绩。

- [x] **Step 1: 写待复核和重算失败测试**

```python
def test_subjective_attempt_waits_for_teacher_and_review_recomputes_best(service):
    attempt = submit_subjective_attempt(service)
    assert attempt.status == "pending_review"
    assert attempt.final_score is None
    reviewed = service.finalize_review(
        attempt_id=attempt.attempt_id,
        item_scores={"asi-short": 18},
        reason_code="RUBRIC_CONFIRMED",
        student_comment="说明完整。",
        teacher_id="teacher-1",
    )
    assert reviewed.status == "graded"
    assert service.list_reviews(attempt.attempt_id)[0].previous_score is None
```

- [x] **Step 2: 实现服务/API 并运行测试**

Run: `cd Edu_AI/api/src; python -m pytest tests/assessment/test_assessment_review.py -q`

Expected before/after: 首次 FAIL；实现后 PASS。

Commit: `git commit -m "feat: add audited assessment reviews"`

### Task 9: 实现四级分析、教师复核与反馈界面

**Files:**
- Create: `Edu_AI/api/src/app/assessment/analytics.py`
- Modify: `Edu_AI/api/src/app/assessment/service.py`、`api/assessment.py`、`schemas/assessment.py`
- Create: `Edu_AI/src/stitch/assessment/AssessmentReview.tsx`
- Create: `Edu_AI/src/stitch/assessment/AssessmentAnalytics.tsx`
- Create: `Edu_AI/src/stitch/assessment/assessmentAnalytics.test.ts`
- Modify: `Edu_AI/src/stitch/pages/CourseLearning.tsx`、`CourseLearning.css`
- Test: `Edu_AI/api/src/tests/assessment/test_assessment_analytics.py`

**Interfaces:**
- Produces: task summary、student queues、item analysis、knowledge-point analysis。
- Required task metrics: enrolled、participated、submitted、passed、mastery、pending_review、mean、median、score_distribution、average_attempts，所有比例携带 numerator/denominator。

- [x] **Step 1: 写统计口径失败测试**

以 4 名学生构造未开始、学习未提交、50 分未通过、85 分掌握良好四种状态，断言提交率 `2/4`、通过率 `1/4`、待复核不进入平均最终分，并断言学生 API 不能访问班级分析。

- [x] **Step 2: 实现聚合和界面**

教师页面提供未开始、已学习未提交、待复核、可重做未通过、次数用尽未通过、已通过、掌握良好筛选；学生行展示历次成绩和最近活动。题目与知识点卡片必须展示样本数，零样本不显示掌握百分比。

- [x] **Step 3: 阶段回归、提交和推送**

Run:

```powershell
cd Edu_AI/api/src
python -m pytest tests/assessment tests/learning -q
cd ../..
npm test -- src/stitch/assessment/assessmentAnalytics.test.ts src/stitch/assessment/assessmentRunner.test.ts src/stitch/assessment/assessmentAuthoring.test.ts
npm run build
```

Expected: 全部 PASS。

Commit: `git commit -m "feat: add assessment review analytics"`

Push: `git push origin main`

---

## Phase 4 — Agent、迁移、安全与真实验收

### Task 10: 将测评事实接入双端 Agent

**Files:**
- Modify: `Edu_AI/api/src/app/learning/context_reader.py`、`service.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/learning.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/nodes/executor.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/learning_context_prompt.py`
- Test: `Edu_AI/api/src/tests/chat/runtime/test_learning_agent_tools.py`
- Test: `Edu_AI/api/src/tests/chat/runtime/test_learning_task_domain.py`
- Test: `Edu_AI/api/src/tests/chat/test_learning_context_injection.py`

**Interfaces:**
- Student projection: 本人任务结果、剩余次数、最佳最终成绩、可见反馈和薄弱知识点。
- Teacher projection: 聚合参与/提交/通过/掌握/待复核、分数分布、高频错题、统计时间。

- [x] **Step 1: 写回答边界失败测试**

断言待复核不能回答“已通过”，开卷测评回答携带 `assessment_mode=open_book`，未揭示答案不进入学生工具结果，教师聚合不包含逐人答案。

- [x] **Step 2: 实现投影和回答模板并运行测试**

Run: `cd Edu_AI/api/src; python -m pytest tests/chat/runtime/test_learning_agent_tools.py tests/chat/runtime/test_learning_task_domain.py tests/chat/test_learning_context_injection.py -q`

Expected: PASS。

Commit: `git commit -m "feat: ground agents in assessment outcomes"`

### Task 11: 完成遗留迁移、安全门禁和确定性 E2E

**Files:**
- Modify: `Edu_AI/api/src/app/learning/store.py`、`service.py`
- Modify: `Edu_AI/src/stitch/pages/CourseMaterialArtifactPreview.tsx`
- Create: `Edu_AI/tests/e2e/learning-task-assessment-loop.spec.ts`
- Test: `Edu_AI/api/src/tests/assessment/test_assessment_student_api.py`
- Test: `Edu_AI/api/src/tests/learning/test_learning_api.py`
- Test: `Edu_AI/api/src/tests/database/test_alembic_revision_chain.py`

**Interfaces:**
- Produces: legacy tasks show `legacy_unassessed` and cannot generate verified evidence until supplemented。
- Produces: role-aware course quiz preview; student cannot use course resources to retrieve formal assessment keys before reveal。

- [x] **Step 1: 写迁移和攻击用例**

覆盖跨课程 task ID、伪造 student ID、伪造成绩、重复提交、猜测 answer endpoint、乱序 option ID、并发 autosave、修改源材料、后端重启和旧 completed 数据。

- [x] **Step 2: 实现最小修复并运行安全测试**

安全、迁移和权限用例按职责分布在 assessment、learning、PostgreSQL repository 和 Alembic revision-chain 测试中，并已纳入后端全量门禁。

Expected: PASS。

- [x] **Step 3: 实现 Playwright 闭环**

确定性 E2E 启动真实 FastAPI 与 Vite，使用真实教师/学生账号验证发布门禁、答案防泄露、50→75→65、最佳分、答案揭示、学生越权拒绝、教师四级反馈，以及代码实现题提交、待复核、教师确认、学生可见评语和私有备注隔离。已有习题导入、无习题生成、版本和 Agent 角色投影由同一全量门禁中的领域/API 测试覆盖。

Run: `cd Edu_AI; pnpm exec playwright test tests/e2e/learning-task-assessment-loop.spec.ts --project=desktop1366`

Expected: PASS。

Commit: `git commit -m "test: harden the assessment learning loop"`

### Task 12: 全量验证、验收取证、文档收口和最终推送

**Files:**
- Modify: `Edu_AI/docs/acceptance/2026-08-12-learning-task-assessment-loop-acceptance.md`
- Modify: `docs/superpowers/decisions/2026-08-12-learning-task-assessment-loop.md`
- Modify: `docs/superpowers/plans/2026-08-12-learning-task-assessment-loop.md`

- [x] **Step 1: 运行全量后端、前端和迁移门禁**

```powershell
cd Edu_AI/api/src
python -m pytest tests -q
python -m alembic heads
cd ../..
npm test
npm run lint
npm run build
```

Expected: pytest/test/build 退出码 0，Alembic 仅一个 head。若 lint 只有基线 warning，记录数量和基线；任何新增 error 必须修复。

- [x] **Step 2: 执行真实双账号验收**

使用一个真实教师账号和一个真实学生账号贯通 UI 主链路；班级多学生分母、无习题生成、版本切换和 Agent 边界使用确定性领域/API 测试补足，避免验收依赖外部 LLM。证据记录提交、课程、任务、测评版本、三次客观作答、一次代码作答、教师复核、截图和服务日志。

- [x] **Step 3: 更新计划勾选、决策日志和验收结论**

所有证据必须指向同一提交；失败项写明命令、错误、修复提交和重跑结果，不使用“基本通过”。

- [x] **Step 4: 提交并推送**

Commit: `git commit -m "docs: record assessment loop acceptance"`

Push: `git push origin main`

Push 后检查：

```powershell
git status --short
git rev-parse HEAD
git rev-parse origin/main
git log -1 --oneline --decorate
```

Expected: 工作区无本任务未提交文件，`HEAD` 与 `origin/main` 相同。

---

## Spec Coverage Matrix

| Spec requirement | Plan tasks |
| --- | --- |
| ASMT-FR-001 | Tasks 2、4 |
| ASMT-FR-002 | Tasks 3–4 |
| ASMT-FR-003 | Tasks 3–4 |
| ASMT-FR-004 | Tasks 3–4 |
| ASMT-FR-005 | Tasks 1、3、8 |
| ASMT-FR-006 | Tasks 5–7 |
| ASMT-FR-007 | Tasks 5、7 |
| ASMT-FR-008 | Tasks 1、4–7 |
| ASMT-FR-009 | Task 8 |
| ASMT-FR-010 | Tasks 5、7、9 |
| ASMT-FR-011 | Task 9 |
| ASMT-FR-012 | Tasks 6、7、9 |
| ASMT-FR-013 | Task 10 |
| ASMT-FR-014 | Tasks 5–7 |
| ASMT-FR-015 | Tasks 8–9 |
| ASMT-NFR-001 | Tasks 1–2、11 |
| ASMT-NFR-002 | Tasks 3、6、11 |
| ASMT-NFR-003 | Tasks 2、5–6、8、11 |
| ASMT-NFR-004 | Tasks 6、11 |
| ASMT-NFR-005 | Tasks 4、6、8–11 |
| ASMT-NFR-006 | Tasks 2、5、11–12 |
| ASMT-NFR-007 | Tasks 9、11–12 |
