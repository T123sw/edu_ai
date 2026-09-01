# 标准学习资源与学习闭环（二期）实施计划

> 执行方式：在 `codex/standard-learning-resources` 隔离分支内，按测试先行顺序逐项实施。每个任务都先写失败测试，再写最小实现，再运行局部测试；最后执行完整回归与当前测试课程验收。

**目标：** 为课程知识结构的叶子知识点预生成并审核三类标准学习资源（AI 课堂、学习指南、练习），教师可将已审核资源或个人资源制作成带不可变快照的学习任务，学生的真实学习行为形成可核验进度。

**范围边界：** 保留知识图谱后端；前端不恢复独立知识图谱页面。RAG 升级、历史课程共享资源清理、真实数据库的数据迁移均不在本期实现范围。

**技术策略：** 在现有 `materials` / `material_versions` 上增加来源、标准资源类型和审核字段；增加批次表与任务资源快照表；复用现有持久化任务队列和报告、测验、课堂生成器；React 页面按知识点展示固定三槽位；学习任务发布后以快照为准。

---

## 任务 1：数据库契约与迁移

**涉及文件**

- 修改：`backend/src/app/database/models.py`
- 修改：`backend/src/app/database/__init__.py`
- 新增：`backend/alembic/versions/20260824_0016_standard_learning_resources.py`
- 新增：`backend/src/tests/database/test_standard_learning_resource_models.py`
- 修改：`backend/src/tests/database/test_alembic_chain.py`

**失败测试**

1. 断言 `Material` 与 `MaterialVersion` 暴露来源、标准类型、批次与审核字段。
2. 断言新模型 `StandardResourceBatch`、`StandardResourceBatchItem`、`LearningTaskResourceSnapshot` 可建立元数据表。
3. 断言 Alembic 新版本的 `down_revision == "20260812_0015"`，升级 SQL 包含索引、约束和旧学习任务 `task_type='assessed'` 的回填。

**最小实现**

- `materials.origin_type`: `personal | standard | legacy_shared`，旧数据按 `visibility` 回填为个人或历史共享。
- `materials.standard_kind`: `classroom | study_guide | practice | NULL`。
- `materials.current_review_status`: `not_required | pending | approved | rejected`。
- `materials.approved_version` 指向已经审核的版本号；新版本生成完成时仅进入 `pending`，不得覆盖学生可见版本。
- 批次保存课程、发起人、状态、汇总计数和时间；批次项唯一键为 `(batch_id, leaf_id, standard_kind)`。
- 学习任务新增 `task_type`，旧任务回填 `assessed`。
- 快照保存任务、来源材料版本、类型、标题、清洗后的内容载荷、文件引用和创建时间；发布后不可更新。

**验证命令**

```powershell
python -m pytest backend/src/tests/database/test_standard_learning_resource_models.py backend/src/tests/database/test_alembic_chain.py -q
```

---

## 任务 2：标准资源领域规则与查询

**涉及文件**

- 新增：`backend/src/app/standard_resources/__init__.py`
- 新增：`backend/src/app/standard_resources/models.py`
- 新增：`backend/src/app/standard_resources/repository.py`
- 新增：`backend/src/app/standard_resources/service.py`
- 修改：`backend/src/app/persistence/postgres_material_repository.py`
- 新增：`backend/src/tests/standard_resources/test_models.py`
- 新增：`backend/src/tests/standard_resources/test_service.py`

**失败测试**

1. 从课程树只提取叶子节点，稳定排序且忽略根节点与中间章节。
2. 稳定材料 ID 为 `standard-<leaf_id>-<kind>`，三种类型映射到 `classroom/report/quiz`。
3. 教师列表返回所有叶子槽位和审核状态；学生列表只返回 `approved_version`。
4. 当新版本待审时，旧的已审核版本仍是学生可见版本。
5. 审核拒绝记录原因；只有 `pending` 版本可以批准或拒绝。

**最小实现**

- 建立 `StandardKind`、`ReviewStatus` 和列表 DTO。
- 仓储使用短事务完成批次、批次项和审核状态更新。
- 扩展材料仓储的列投影与版本载荷，兼容没有新字段的旧调用。
- 服务层接受权限已验证的用户上下文，不在仓储中混入 HTTP 逻辑。

**验证命令**

```powershell
python -m pytest backend/src/tests/standard_resources/test_models.py backend/src/tests/standard_resources/test_service.py -q
```

---

## 任务 3：生成批次、失败重试与审核接口

**涉及文件**

- 新增：`backend/src/app/schemas/standard_resources.py`
- 新增：`backend/src/app/api/standard_resources.py`
- 修改：`backend/src/app/bootstrap.py`
- 修改：`backend/src/app/services/generation_command.py`
- 修改：`backend/src/app/services/generation_task_handlers.py`
- 修改：`backend/src/app/services/classroom_service.py`
- 修改：`backend/src/core/course_storage.py`
- 新增：`backend/src/tests/standard_resources/test_api.py`
- 新增：`backend/src/tests/standard_resources/test_generation_batches.py`

**失败测试**

1. viewer 不能创建批次或审核；owner/editor 可以。
2. 创建批次时仅为所选叶子生成固定三类项目，并返回可轮询批次 ID。
3. 每个批次项使用稳定材料 ID、`knowledge_point` 作用域和独立幂等键。
4. 重试接口只重新提交失败项，不重复成功项。
5. 单项审核和“一键批准全部待审”均保留审核人、时间与版本。
6. 生成完成时只创建 `pending` 版本；失败信息可在批次详情中读取。

**接口**

- `GET /api/courses/{course_id}/standard-resources`
- `POST /api/courses/{course_id}/standard-resource-batches`
- `GET /api/courses/{course_id}/standard-resource-batches/{batch_id}`
- `POST /api/courses/{course_id}/standard-resource-batches/{batch_id}/retry`
- `POST /api/courses/{course_id}/standard-resources/{material_id}/review`
- `POST /api/courses/{course_id}/standard-resource-batches/{batch_id}/approve-pending`

**验证命令**

```powershell
python -m pytest backend/src/tests/standard_resources/test_api.py backend/src/tests/standard_resources/test_generation_batches.py -q
```

---

## 任务 4：测试课程最小知识结构与示例讲义

**涉及文件**

- 新增：`backend/src/scripts/seed_standard_resource_test_course.py`
- 新增：`backend/src/tests/standard_resources/test_seed_test_course.py`
- 新增：`backend/src/tests/fixtures/database_test_lecture.md`

**失败测试**

1. 默认只允许课程 `course-a385a289be0d44e480e343472f6cc8cd`。
2. 非空知识树或已有正式资料时拒绝写入，除非显式提供覆盖开关。
3. 重复执行不会产生重复节点或重复文档。
4. 生成的树包含三个章节和六个叶子知识点，ID 稳定。
5. 示例讲义为一份课程级文档，含六个与叶子名称一致的标题。

**最小结构**

- 关系模型：关系与键、完整性约束
- SQL 查询：单表查询、多表连接
- 事务：ACID、并发控制

**安全执行步骤**

1. 使用 `pg_dump` 备份当前数据库到工作区外的带时间戳文件。
2. 先以 `--dry-run` 输出拟写入对象。
3. 执行脚本后查询课程树和文档数量，只允许目标课程变化。

**验证命令**

```powershell
python -m pytest backend/src/tests/standard_resources/test_seed_test_course.py -q
```

---

## 任务 5：课程知识页的标准学习资源界面

**涉及文件**

- 新增：`frontend/src/stitch/api/standardResources.ts`
- 修改：`frontend/src/stitch/api/types.ts`
- 新增：`frontend/src/stitch/course/knowledge/StandardLearningResources.tsx`
- 新增：`frontend/src/stitch/course/knowledge/standardLearningResources.css`
- 新增：`frontend/src/stitch/course/knowledge/standardLearningResourcesPresentation.ts`
- 新增：`frontend/src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts`
- 修改：`frontend/src/stitch/pages/CourseKnowledge.tsx`

**界面规则**

- 课程知识页保留知识库文档区域，并新增“标准学习资源”区域；不增加知识图谱页签。
- 按章节折叠展示叶子知识点，每个叶子固定展示 AI 课堂、学习指南、练习三个槽位。
- 教师可选择叶子、启动生成、轮询批次、查看失败、重试、预览、批准或拒绝。
- 学生只看到已经批准的资源；待生成、待审核、被拒绝资源不暴露内容和入口。
- 空态明确提示教师先完善叶子知识点；生成按钮显示预计项目数。

**测试先行**

1. 演示层将叶子与三槽位稳定组合。
2. 学生过滤只保留已审核资源。
3. 批次进度文案正确处理 queued/running/partial/failed/completed。

**验证命令**

```powershell
pnpm exec node --import tsx --test src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts
pnpm lint
pnpm build
```

---

## 任务 6：学习任务资源快照与任务类型

**涉及文件**

- 修改：`backend/src/app/learning/models.py`
- 修改：`backend/src/app/learning/service.py`
- 修改：`backend/src/app/learning/store.py`
- 修改：`backend/src/app/persistence/postgres_learning_repository.py`
- 修改：`backend/src/app/schemas/learning.py`
- 修改：`backend/src/app/api/learning.py`
- 新增：`backend/src/tests/learning/test_task_resource_snapshots.py`
- 修改：`backend/src/tests/learning/test_learning_service.py`

**失败测试**

1. 新任务可选择 `reading` 或 `assessed`；旧调用默认 `assessed`。
2. 教师只能选本课程已审核标准资源，或自己拥有的个人资源。
3. 创建任务时立即复制资源标题、内容和文件引用；之后原材料变化不影响任务。
4. 学生读取任务资源只读取快照，不读取原材料权限或最新版本。
5. `reading` 任务不要求测验即可发布；`assessed` 任务继续要求有效测验。

**实现约束**

- 对快照内容做允许字段白名单，排除生成配置、内部路径、提示词和审核备注。
- 新任务的 `resource_refs` 保留兼容投影，但快照 ID 是事件和读取的权威来源。
- 发布后仓储拒绝新增、修改或删除快照。

**验证命令**

```powershell
python -m pytest backend/src/tests/learning/test_task_resource_snapshots.py backend/src/tests/learning/test_learning_service.py -q
```

---

## 任务 7：教师任务编排、学生学习与证据展示

**涉及文件**

- 修改：`frontend/src/stitch/api/learning.ts`
- 修改：`frontend/src/stitch/api/types.ts`
- 修改：`frontend/src/stitch/pages/CourseLearning.tsx`
- 新增：`frontend/src/stitch/course/learning/learningEvidencePresentation.ts`
- 新增：`frontend/src/stitch/course/learning/learningEvidencePresentation.test.ts`
- 修改：`backend/src/app/learning/service.py`
- 修改：`backend/src/app/api/learning.py`

**界面与证据规则**

- 教师创建任务时先选“阅读学习”或“考核任务”，资源选择器分为“标准学习资源”和“个人资源”。
- 学生从任务卡打开快照资源；打开、有效停留/进度、完成分别写入事件。
- 仅点击打开不能判定完成；资源完成形成 `activity_evidenced`，测验成绩形成 `assessment_verified`。
- 教师看板同时展示未开始、学习中、自报完成、活动证据完成、考核验证完成，避免只显示单一完成率。

**失败测试**

1. 证据等级排序固定为 `none < self_reported < activity_evidenced < assessment_verified`。
2. 资源打开事件不会直接完成任务。
3. 阅读资源全部完成时任务可达到活动证据完成；考核成绩只能由服务端验证入口写入。
4. 前端状态标签与后端 completion basis 一一对应。

**验证命令**

```powershell
pnpm exec node --import tsx --test src/stitch/course/learning/learningEvidencePresentation.test.ts
python -m pytest backend/src/tests/learning -q
```

---

## 任务 8：迁移、回归与当前课程端到端验收

**迁移验证**

1. 在测试数据库执行 `alembic upgrade head`。
2. 执行新表、约束、索引和回填查询。
3. 将迁移降到 `20260812_0015` 再升回 head，确认可逆。

**自动化回归**

```powershell
python -m pytest backend/src/tests -q
pnpm test
pnpm lint
pnpm build
```

**当前课程验收路径**

1. 初始化目标课程的三章六叶子结构和一份测试讲义。
2. 教师选择一个叶子生成三类标准资源，观察批次状态与失败重试。
3. 逐项预览并批准，确认教师看见审核状态、学生只看见批准版本。
4. 创建一个阅读任务并发布，随后再创建一个含练习的考核任务。
5. 学生打开任务快照、完成资源和练习；教师看板显示对应证据等级。
6. 再生成一个待审新版本，确认学生任务快照与旧审核版本均不变化。
7. 保存 API 响应、数据库计数和关键页面截图作为验收证据。

**明日真实数据库复验**

- 先备份和导入真实数据库，再运行迁移；不重复执行测试课程种子。
- 审计旧 `course` 可见资源并映射为 `legacy_shared`，暂不删除。
- 选一门真实课程，以同一套接口、权限、版本隔离和任务快照用例复验。

