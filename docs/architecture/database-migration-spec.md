# Edu AI 数据库迁移 Spec

- 状态：Completed（结构化业务存储已切换）
- 版本：2.0
- 日期：2026-08-10
- 目标数据库：PostgreSQL 17
- 当前数据库版本：Alembic `20260810_0010`

## 1. 背景与问题

Edu AI 当前的大部分业务状态由 JSON 文件持久化。这个方案适合早期原型，但随着用户、课程、对话、生成任务、教学资源和知识库持续增长，已经出现以下问题：

1. 数据分散在 `backend/storage`、`backend/src/storage` 和 `backend/course_data`，运行目录不同会产生两套数据根目录。
2. 多进程或并发请求写同一文件时，只能依赖进程内锁和临时文件替换，无法提供跨进程事务。
3. 课程、用户、任务、对话和资源之间缺少数据库级外键，孤立记录和重复记录难以及时发现。
4. 分页、筛选、统计、审计和后台管理需要加载大量文件，性能和可维护性会持续恶化。
5. JSON 文件既承担业务主数据，又承担运行日志、缓存、文件索引和评估产物，边界不清晰。
6. 无法可靠支持教师“一键构建课程知识库”所需要的长任务状态、来源审查、版本、发布和回滚。

## 2. 现状盘点

以下数字来自 2026-08-10 的本地工作区，仅用于确定迁移规模，不作为固定产品上限。

| 数据域 | 当前主要位置 | 当前规模 | 备注 |
|---|---|---:|---|
| 用户 | `backend/src/storage/users.json` | 7 用户 | 另有历史根目录 3 用户 |
| 课程 | `backend/course_data/courses/*/course_info.json` | 6 个正式课程已导入 | 文件系统还存在测试/临时课程目录 |
| 课程成员 | `backend/src/storage/course_memberships.json` | 42 条 | 另有历史根目录 18 条 |
| 对话 | `backend/src/storage/conversations.json` | 149 个对话、1147 条消息 | 单文件约 2 MB；另有历史根目录 12 个对话 |
| 后台任务 | `backend/src/storage/jobs/*.json` | 272 个 | 以 RAG 导入、课堂、报告生成为主 |
| 抓取批次 | `backend/src/storage/crawl_batches` | 396 个 JSON | 部分批次包含多文件状态 |
| 课程数据 | `backend/course_data` | 203 个 JSON，约 6.23 MB | 包含课程信息、资源清单、知识库索引及备份 |
| 生成教学资源 | `generated_materials` | 约 172 个 JSON | 测验、报告、教案、课堂、博客等 |
| 课程知识库索引 | `knowledge_base/index.json` | 计算思维课程 149 条 | 文档本体仍是文件 |
| 全局文档索引 | `backend/src/storage/document_index.json` | 183 条 | 当前键包含用户和绝对文件路径 |
| 图片索引 | `backend/src/storage/image_index.json` | 47 条 | 图片本体不应放入普通关系表 |
| 搜图缓存元数据 | `backend/src/storage/searched_images` | 601 个 JSON | 属于可重建或可过期数据 |
| 学习任务和进度 | `backend/src/storage/learning.db` | SQLite | 已是数据库，但不是统一数据源 |

### 2.1 双存储根目录

`Config.STORAGE_ROOT` 当前默认值是相对路径 `storage`。从 `backend/src` 启动时，活跃目录是 `backend/src/storage`；从 `api` 启动过的历史进程则产生了 `backend/storage`。迁移工具必须同时扫描这两个目录，但不得简单覆盖：

- 同 ID、内容相同：去重。
- 同 ID、内容不同：按业务时间戳选取较新版本，同时记录冲突报告。
- 缺少时间戳：不得自动覆盖，进入人工审查清单。
- 导入完成后，运行时必须使用绝对 `STORAGE_ROOT`，避免继续分叉。

## 3. 目标与非目标

### 3.1 目标

1. PostgreSQL 成为结构化业务数据的最终唯一事实来源。
2. 迁移期间不中断现有功能，并可以按数据域独立回滚。
3. 所有迁移脚本可预检、可重复执行、可对账、可审计。
4. 为课程知识库自动构建提供任务、来源、文档、版本、质量门禁和发布记录。
5. 为管理后台提供可靠的查询、分页、统计和数据治理基础。
6. 保留现有业务 ID，避免一次迁移同时改变所有 API 合同。

### 3.2 非目标

1. 不把图片、视频、PDF、PPTX、Markdown 原文等大文件直接存入 PostgreSQL。
2. 不迁移 `package.json`、模板 schema、测试 fixture、国际化文件和构建配置。
3. 不在本阶段立即替换现有向量数据库；先迁移知识文档元数据和索引状态。
4. 不在切换当天删除 JSON；JSON 将先转为兼容投影或只读归档。
5. 不同时重写所有 API 和前端。

## 4. 数据存放边界

### 4.1 必须进入 PostgreSQL

- 用户、角色与账号状态
- 课程、课程目标、课程成员和权限
- 对话、消息、工作流状态和产物引用
- 后台任务、任务尝试、进度事件和错误信息
- 教学资源清单、资源版本、可见性和文件引用
- 知识库、来源候选、知识文档、文档版本、索引状态和质量报告
- 抓取批次及抓取条目
- 个人知识库的结构化元数据
- 可审计的运行配置快照
- 学习任务和进度（后续从 SQLite 合并）

### 4.2 保留在文件或对象存储

- 用户上传的原始文档
- 解析后的 Markdown、图片、音频、视频、PPTX 和课堂导出文件
- 现阶段的向量索引文件
- 可下载的生成产物

数据库只保存相对 URI、SHA-256、MIME 类型、字节数、创建者和生命周期状态。路径不得继续保存为绑定某台机器的绝对路径。

### 4.3 继续保留为仓库 JSON

- 动态模板 schema
- 测试 fixture 和评估场景
- 前端、Node、TypeScript 和第三方组件配置
- 只读研究报告与评估快照

## 5. 数据建模原则

1. 所有时间使用 UTC `timestamptz`；API 层负责显示时区。
2. 迁移期保留原字符串 ID。新实体优先使用 UUID，但不强制改写历史 ID。
3. 业务会筛选、关联或排序的字段必须建普通列；不把整个业务对象只放在 JSONB 中。
4. JSONB 仅用于变化较快的状态、提供方响应、工作流上下文和 `legacy_payload`。
5. 表必须包含明确的唯一约束、外键和必要索引。
6. 可修改的核心记录使用 `revision` 或 `version` 做乐观锁。
7. 用户可见数据优先软删除；缓存和临时记录可以按保留策略硬删除。
8. 所有后台任务状态变更必须在同一事务中写任务表和事件表。
9. 密码只保存现有安全哈希，不保存明文；第三方 API 密钥继续由环境变量或密钥服务管理。

## 6. 目标表设计

### 6.1 已完成的基础表

| 表 | 关键字段 | 约束与用途 |
|---|---|---|
| `users` | `id`, `username`, `role`, `password_hash`, `display_name`, `raw_payload` | `username` 唯一；保留历史载荷用于审计 |
| `courses` | `id`, `name`, `description`, `creator_id`, `status`, `raw_payload` | 课程主数据；创建者允许在历史导入时为空 |
| `course_objectives` | `id`, `course_id`, `position`, `content` | 课程目标有序列表 |
| `course_memberships` | `id`, `course_id`, `user_id`, `role`, `added_by` | `(course_id, user_id)` 唯一 |

### 6.2 对话域

| 表 | 关键字段 | 索引/约束 |
|---|---|---|
| `conversations` | `id`, `owner_user_id`, `course_id`, `scope_type`, `scope_id`, `title`, `state`, `created_at`, `updated_at`, `deleted_at` | `(owner_user_id, updated_at desc)`；课程和知识点范围索引 |
| `conversation_messages` | `id`, `conversation_id`, `ordinal`, `role`, `message_kind`, `content`, `input_assets`, `metadata`, `created_at` | `(conversation_id, ordinal)` 唯一 |
| `conversation_artifacts` | `id`, `conversation_id`, `message_id`, `material_id`, `artifact_kind`, `artifact_uri` | 连接对话与生成资源 |

`state` 暂时使用 JSONB，以兼容当前工作流状态；课程 ID、范围类型和范围 ID 必须提升为普通列，以支持筛选和权限校验。

### 6.3 后台任务域

| 表 | 关键字段 | 索引/约束 |
|---|---|---|
| `jobs` | `id`, `kind`, `status`, `owner_user_id`, `course_id`, `scope_type`, `scope_id`, `progress`, `input_summary`, `result_ref`, `error_code`, `error_message`, `retry_of_job_id`, `parent_job_id`, `created_at`, `started_at`, `finished_at`, `updated_at`, `revision` | 状态、用户、课程、更新时间索引 |
| `job_attempts` | `id`, `job_id`, `attempt_no`, `provider_ref`, `started_at`, `finished_at`, `status`, `error` | `(job_id, attempt_no)` 唯一 |
| `job_events` | `id`, `job_id`, `sequence`, `event_type`, `payload`, `created_at` | `(job_id, sequence)` 唯一；用于进度流和审计 |

任务领取使用事务和 `SELECT ... FOR UPDATE SKIP LOCKED`，避免多个 worker 重复执行。

### 6.4 教学资源域

| 表 | 关键字段 | 索引/约束 |
|---|---|---|
| `materials` | `id`, `course_id`, `material_type`, `title`, `status`, `visibility`, `owner_user_id`, `scope_type`, `scope_id`, `current_version`, `source_job_id`, `created_at`, `updated_at`, `deleted_at` | `(course_id, material_type, id)` 唯一 |
| `material_versions` | `id`, `material_id`, `version`, `content`, `created_by`, `created_at` | `(material_id, version)` 唯一；内容先使用 JSONB |
| `artifact_files` | `id`, `owner_type`, `owner_id`, `purpose`, `storage_uri`, `sha256`, `mime_type`, `size_bytes`, `created_at`, `deleted_at` | `sha256` 和 owner 索引 |
| `material_publications` | `id`, `material_id`, `version`, `published_by`, `published_at`, `publication_state` | 保留发布历史 |

资源正文结构差异较大，第一版在 `material_versions.content` 使用 JSONB；稳定且需要查询的公共字段提升到 `materials`。

### 6.5 知识库域

| 表 | 关键字段 | 索引/约束 |
|---|---|---|
| `knowledge_libraries` | `id`, `library_type`, `course_id`, `owner_user_id`, `status`, `active_version`, `created_at`, `updated_at` | 课程库和个人库统一建模；所有者约束 |
| `knowledge_builds` | `id`, `library_id`, `triggered_by`, `status`, `phase`, `progress`, `quality_score`, `source_policy`, `started_at`, `finished_at`, `published_at`, `error` | 库、状态、时间索引 |
| `knowledge_source_candidates` | `id`, `build_id`, `url`, `title`, `domain`, `authority_tier`, `license_info`, `language`, `review_status`, `review_reason`, `metadata` | `(build_id, url)` 唯一 |
| `knowledge_documents` | `id`, `library_id`, `source_candidate_id`, `title`, `status`, `current_version`, `active_index_version`, `created_at`, `updated_at`, `deleted_at` | 库、状态、来源索引 |
| `knowledge_document_versions` | `id`, `document_id`, `version`, `storage_uri`, `sha256`, `mime_type`, `size_bytes`, `extraction_metadata`, `created_at` | `(document_id, version)` 唯一 |
| `knowledge_index_runs` | `id`, `build_id`, `document_version_id`, `index_version`, `status`, `chunk_count`, `embedding_model`, `started_at`, `finished_at`, `error` | 文档版本、索引版本索引 |
| `knowledge_quality_checks` | `id`, `build_id`, `check_type`, `status`, `score`, `details`, `created_at` | 构建质量门禁和审查证据 |
| `knowledge_graph_versions` | `id`, `library_id`, `version`, `graph_payload`, `source_build_id`, `created_at`, `published_at` | 第一阶段用 JSONB 保存图版本 |

教师“一键构建知识库”的状态流：

```text
draft → discovering → reviewing → ingesting → indexing
      → quality_check → ready_for_review → published
```

任何阶段都可进入 `failed` 或 `canceled`。只有通过来源审查、索引完成和质量门禁的构建才能发布；发布操作只切换 `knowledge_libraries.active_version`，因此可以快速回滚上一版本。

### 6.6 抓取、媒体和辅助数据

| 表 | 用途 |
|---|---|
| `crawl_batches` / `crawl_items` | 保存抓取批次、单 URL 状态、来源、错误和归档结果 |
| `media_assets` | 保存图片、音视频和搜索图片的元数据；二进制仍在文件/对象存储 |
| `runtime_config_snapshots` | 保存非敏感配置快照和内容哈希；密钥不入库 |
| `learning_tasks` / `learning_progress` | 后期替换当前 `learning.db` |

搜图缓存和临时抓取结果必须有 `expires_at`，由定时清理任务控制容量。

## 7. 应用访问层

业务代码不得直接依赖 SQLAlchemy Session 或 JSON 路径。每个数据域建立仓储接口：

```text
UserRepository
CourseRepository
ConversationRepository
JobRepository
MaterialRepository
KnowledgeRepository
```

迁移期间每个仓储支持以下状态，而不是全系统一次切换：

| 模式 | 读取 | 写入 | 用途 |
|---|---|---|---|
| `json` | JSON | JSON | 现状和紧急回滚 |
| `shadow` | JSON | JSON + PostgreSQL | PostgreSQL 失败不影响请求，但必须记录待重放事件 |
| `postgres_shadow_read` | PostgreSQL 与 JSON 同读并比对，响应仍取 JSON | 两边 | 发现读取差异 |
| `postgres_dual` | PostgreSQL | PostgreSQL + JSON 兼容投影 | 切换后的观察期 |
| `postgres` | PostgreSQL | PostgreSQL | 最终状态 |

模式按数据域配置，例如 `COURSE_PERSISTENCE_MODE`、`CONVERSATION_PERSISTENCE_MODE`，避免一个总开关同时影响所有功能。

## 8. 迁移流程

每个数据域都必须走同一条流水线：

1. **Discover**：扫描所有已知根目录，输出文件数量、大小、更新时间和解析错误。
2. **Validate**：校验 schema、主键、外键、枚举、时间戳和重复项；只生成报告，不写数据库。
3. **Import**：在事务中幂等 upsert，保存来源文件和内容哈希。
4. **Reconcile**：比较记录数、ID 集合、关键字段哈希、孤立记录和冲突清单。
5. **Shadow write**：JSON 仍权威，PostgreSQL 接收影子写入和重放。
6. **Shadow read**：同一请求读取两边并记录差异，不改变用户响应。
7. **Cutover**：把该数据域切换为 PostgreSQL 读取。
8. **Compatibility window**：至少保留一个稳定发布周期的 JSON 兼容投影。
9. **Archive**：停止 JSON 写入，打包只读归档；不得直接删除原数据。

所有导入记录进入 `data_migration_runs` 和 `data_migration_conflicts`，至少包含：运行 ID、数据域、源路径、源哈希、开始/结束时间、导入数、跳过数、冲突数、错误摘要和代码版本。

## 9. 分阶段实施

### Phase 0：基础设施与首轮核心导入（已完成）

- PostgreSQL 17 Docker 部署
- SQLAlchemy 与 Alembic
- 用户、课程、课程目标、课程成员表
- JSON 只读预检和幂等导入
- 数据库健康检查

### Phase 1：核心仓储与双写（已完成）

- 为用户、课程、目标、成员实现仓储接口
- 增加按域持久化模式
- JSON→PostgreSQL 影子写入、失败重放和差异报告
- 修复教师端“创建课程”入口后，课程创建直接进入仓储层

实施进度（2026-08-10）：仓储契约、`json`/`shadow` 分域模式、PostgreSQL
核心仓储、非阻塞影子写入、脱敏失败日志和只读对账 CLI 已完成。当前读取源仍为
JSON；本机开发环境已启用三个核心域的 `shadow`，仓库默认值仍为 `json`。

退出条件：连续 7 天或 1000 次核心写入无未解释差异，主键和外键对账 100%。

### Phase 2：对话与消息（已完成）

- 导入两个存储根目录的对话并处理冲突
- 将对话和消息拆表
- 保留 `state` JSONB，提升课程与范围字段
- 验证分页、删除、截断、多轮上下文和权限行为一致

退出条件：149 个活跃对话和 1147 条消息全部可追溯；API 契约回归通过；差异率为 0。

### Phase 3：任务与教学资源（已完成）

- 迁移 272 个任务及其状态
- 新任务使用数据库事务领取和状态机
- 迁移生成资源清单与版本，文件本体保留原位
- 建立任务、资源、对话产物之间的关系

退出条件：任务不可重复领取；重启后可恢复；所有现有资源可列出、打开、删除和发布。

### Phase 4：知识库元数据与一键构建（存储迁移已完成）

- 迁移课程/个人知识文档索引和文件引用
- 引入知识库构建、来源候选、审查、索引运行和质量门禁表
- 构建 API 支持启动、查看进度、取消、人工审查、发布和回滚
- 现有向量库继续工作，PostgreSQL 保存其索引版本和文档映射

退出条件：教师新建课程后可启动一键构建；构建全程可恢复、可审计；发布失败不影响上一知识库版本。

### Phase 5：抓取、媒体、运行配置和学习数据（已完成）

- 迁移抓取批次、搜图元数据、配置快照
- 评估将 `learning.db` 合并到 PostgreSQL
- 为缓存数据设置过期和清理策略

### Phase 6：最终切换与归档（已完成）

- 所有业务域切到 `postgres`
- 生成最终对账报告和 `pg_dump` 备份
- JSON 改为只读归档，保留至少 30 天
- 删除运行时代码中的 JSON 写入路径，但保留受控回滚工具

## 10. 数据一致性与验收标准

每个阶段必须满足：

- 所有源 JSON 均可解析，或每个坏文件都有明确隔离记录。
- 源记录 ID 集合与目标记录 ID 集合一致。
- 关键字段标准化后 SHA-256 一致率为 100%，差异均在批准清单中。
- 外键孤立数为 0；无法映射的历史记录进入冲突表，不静默丢弃。
- 重复执行导入后表记录数不增加。
- 双写失败可重放，且不会重复创建业务实体。
- PostgreSQL 不可用时，应用给出明确健康状态，不产生半完成写入。
- 每个仓储有契约测试；同一套测试运行在 JSON 和 PostgreSQL 实现上。
- 切换前完成真实备份和恢复演练，而不只是生成备份文件。

## 11. 备份与回滚

### 切换前

1. 停止该数据域的写入或进入短暂维护窗口。
2. 归档对应 JSON 和文件目录，记录 SHA-256 清单。
3. 执行 PostgreSQL 逻辑备份并在临时数据库恢复验证。
4. 保存当前 Alembic revision、应用提交号和持久化模式。

### 切换后回滚

- 生产配置不再允许切回 JSON；需要回滚时，先停止写入，再恢复已验证的 PostgreSQL 逻辑备份。
- 应用代码按 `db-migration-phase*` 标签回退，数据库按对应 Alembic revision 或备份恢复，二者必须成对操作。
- 原 JSON/SQLite 数据只作为迁移证据保留至少 30 天，不再作为运行时事实来源。
- PostgreSQL 数据不得直接删除；记录回滚时间点并生成增量差异报告。
- 知识库发布通过版本指针回滚，不覆盖已发布版本。

## 12. 可观测性与运维

至少提供以下指标和管理视图：

- 数据库连接、连接池占用和查询延迟
- 各域双写成功率、重放队列长度和读取差异数
- 任务按状态/类型的数量和运行时长
- 知识库构建阶段、失败率、文档数、索引数和质量分
- 文件引用丢失数、孤立文件数和缓存容量
- Alembic revision 与应用期望 revision 是否一致

日志必须携带 `request_id`、`user_id`、`course_id`、`job_id` 或 `build_id` 中适用的关联 ID，但不得记录密码、API 密钥和完整敏感正文。

## 13. pgvector 决策门

当前不立即迁移向量索引。Phase 4 完成后，用真实课程语料评估：

- 检索质量是否与当前向量库相当或更好
- 10 万、100 万 chunk 下的延迟和索引体积
- 备份、恢复和版本切换复杂度
- 混合检索和元数据过滤收益

只有评估通过后，才将镜像切换到支持 `pgvector` 的 PostgreSQL 17 镜像并增加 `knowledge_chunks.embedding vector(...)`。否则 PostgreSQL 继续管理文档与索引元数据，向量本体留在专用向量库。

## 14. 实施完成记录

2026-08-10 已完成 Phase 0–6：

- 24 张结构化业务表已建立，数据库 revision 为 `20260810_0010`。
- 用户、课程、成员、对话、消息、任务、材料、知识库元数据、运行索引、应用状态、学习数据和 durable task queue 均已切到 PostgreSQL。
- `PERSISTENCE_PROFILE=database` 会在 API 启动时校验全部十个持久化域；任一域不是 `postgres` 都会拒绝启动，不会静默回落到 JSON/SQLite。
- 大文件本体继续留在文件系统，PostgreSQL 保存其结构化元数据和引用，符合第 4.2 节边界。
- 4 个无法解析的历史材料 JSON 已保存在 `migration_quarantine`，包含原始内容、哈希、来源和错误信息。
- 最终逻辑备份已经恢复到临时数据库验证，恢复后的用户、课程、对话和后台任务数量分别为 7、6、149、286。

教师“一键构建课程知识库”的产品交互、来源审查体验和质量门禁仍可继续迭代；这些属于上层产品能力，不再受 JSON 主存储限制。
