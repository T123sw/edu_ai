# 教师端 P1：可信生成、RAG、资源治理与配置中心 SPEC

**状态：** 待评审
**日期：** 2026-08-06
**适用范围：** `Edu_AI` 教师端
**前置条件：** P0 的统一任务中心、课程资源入口、AI 课堂同源模型和基础权限检查已经完成
**目标：** 让教师能够判断资料是否生效、生成是否可信、结果是否保存、配置是否真正被系统使用
**不包含：** 主 Agent 长期记忆升级、大型协作系统、资源市场、全量数据库迁移

---

## 1. 文档目的

P1 解决的是“功能看起来存在，但教师不敢依赖”的问题。范围包括：

1. 课程知识库上传后无法判断是否真正进入 RAG；
2. 生成工厂入口、配置、任务、结果和资源之间没有统一闭环；
3. 生成资源使用文件与 JSON 存储，但缺少原子性、所有者、完整删除和一致授权；
4. API、模型、语音、搜索和 PDF 服务必须修改环境变量，普通用户无法配置；
5. 用户中心存在静态模拟资料和模拟改密；
6. 系统配置、任务和最终资源之间缺少可追踪关系。

P1 完成后的目标体验：

> 教师上传资料后可以看到解析和索引状态，用测试问题验证检索；生成资源时可以看到统一任务进度；结果保存后能在课程资源中找到，并知道使用了哪些资料和配置；授权用户可以在前端安全配置模型与语音服务。

---

## 2. P1 设计原则

### 2.1 输入、过程、结果、配置四层分离

```text
课程知识库文档（输入）
        ↓
EduJob（过程）
        ↓
课程资源（结果）
        ↑
配置快照（本次使用的模型与服务）
```

- 文档不承担任务状态；
- 任务不内嵌完整资源内容；
- 资源不作为运行中进度记录；
- 配置修改不反向改变历史资源；
- 每个结果都能追踪来源资料和配置版本。

### 2.2 不提前宣告成功

- 上传文件成功不等于 RAG 可检索；
- 模型输出成功不等于资源保存成功；
- sidecar 成功不等于后处理成功；
- 配置保存成功不等于连接可用；
- 前端提示成功必须以最终后端状态为准。

### 2.3 一个资源事实来源

- AI 课堂、PPT、报告等都使用统一课程资源身份；
- 问答工作台中的临时预览不能成为第二套持久化资源；
- 课程资源页读取后端，不以 Zustand 或 `localStorage` 为权威；
- 资源 ID 在任务、课程资源、预览和导出中保持一致。

### 2.4 安全默认

- API Key 只提交给后端；
- 密钥加密保存，只返回掩码；
- 课程、资源、文档、任务都进行后端授权；
- 兼容旧数据不能无限期放宽所有者检查；
- 错误、日志和前端状态不泄漏密钥、路径和完整文档。

### 2.5 P1 继续坚持 YAGNI

- 不新增大量模型供应商；
- 不开放未形成保存和预览闭环的资源类型；
- 不为了配置中心重写所有业务服务；
- 不在 P1 强制迁移数据库；
- 不把 RAG 做成复杂研究平台，只完成教师可验证的最小闭环。

---

## 3. P1 范围

| 编号 | 模块 | 本期结果 |
|---|---|---|
| P1-RAG | 课程知识库 | 索引状态、失败重试、测试检索、引用定位 |
| P1-GEN | 生成工厂 | 统一四步生成流程和正式能力矩阵 |
| P1-RES | 课程资源 | 统一资源模型、原子保存、完整删除、所有者与权限 |
| P1-CFG | 配置中心 | 模型、RAG、语音、搜索、PDF、课堂服务可安全配置 |
| P1-ACC | 用户中心 | 真实资料、真实改密、配置权限入口 |
| P1-OBS | 可追踪性 | 资源记录来源资料、任务和配置版本 |
| P1-QA | 质量验证 | RAG 黄金集、生成样例集、权限与故障注入验收 |

---

## 4. P1 总体系统架构

```text
┌────────────────────────────── 教师端 ──────────────────────────────┐
│ 课程知识库        生成工厂        课程资源        模型与服务配置      │
│ 文档状态/测试      四步流程        统一管理        测试/启用/回滚      │
└────────┬──────────────┬──────────────┬──────────────┬──────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────────────────────── API 层 ─────────────────────────────┐
│ Knowledge API │ Generation API │ Material API │ Config API │ Job API │
└──────┬────────┴──────┬─────────┴──────┬───────┴──────┬─────┴────────┘
       │               │                │              │
       ▼               ▼                ▼              ▼
┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ RAG Service │ │ Generation   │ │ Material     │ │ Runtime Config   │
│ parse/index │ │ Orchestrator │ │ Repository   │ │ Registry         │
│ retrieve    │ │              │ │ manifest     │ │ secret store     │
└──────┬──────┘ └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘
       │               │                │                  │
       └───────────────┴────────┬───────┴──────────────────┘
                                ▼
                        ┌───────────────┐
                        │ EduJob Ledger │
                        │ 统一过程状态   │
                        └───────────────┘
```

### 4.1 建议的领域边界

#### KnowledgeDocument

负责：

- 原文件；
- 文档所有者与课程范围；
- 解析、分块、索引状态；
- 解析统计；
- 测试检索。

不负责：

- AI 生成结果；
- 生成任务的完整生命周期；
- 模型密钥。

#### EduJob

负责：

- 后台过程；
- 阶段、进度、失败、重试；
- 输入摘要；
- 结果引用；
- 配置快照引用。

不负责：

- 保存最终大文本或二进制；
- 作为课程资源列表。

#### CourseMaterial

负责：

- 最终生成结果；
- 资源所有者、课程、类型、版本；
- 来源文档；
- 文件清单；
- 预览与导出；
- 置顶、重命名、删除。

不负责：

- 运行中进度；
- 当前活动配置。

#### RuntimeConfig

负责：

- 服务提供商、Base URL、模型名和非敏感参数；
- 密钥密文引用；
- 草稿、已验证、已启用、停用和回滚；
- 连接测试；
- 运行时解析。

不负责：

- 历史资源内容；
- 用户会话记忆。

---

## 5. RAG 课程知识库设计

## 5.1 目标

教师必须能回答：

1. 文件是否上传成功；
2. 文件是否解析成功；
3. 是否已经进入向量检索；
4. 失败在哪一步；
5. 这个文件能否回答某个问题；
6. 回答引用的是哪一页／哪一段；
7. 删除文件后是否同时删除索引。

## 5.2 文档状态模型

建议统一为：

```text
received
parsing
chunking
embedding
indexing
ready
partially_ready
failed
deleting
deleted
```

### 5.2.1 状态含义

| 状态 | 含义 | 是否可用于检索 |
|---|---|---:|
| `received` | 原文件已保存，尚未处理 | 否 |
| `parsing` | 提取文本、页码、媒体 | 否 |
| `chunking` | 文本分块 | 否 |
| `embedding` | 生成向量 | 否 |
| `indexing` | 写入向量与关键词索引 | 否 |
| `ready` | 所有必要步骤成功 | 是 |
| `partially_ready` | 部分页面／媒体失败，文本主体可用 | 是，需提示 |
| `failed` | 无可用索引 | 否 |
| `deleting` | 正在删除原文件和索引 | 否 |
| `deleted` | 逻辑删除完成 | 否 |

前端不得仅凭知识库 index 中存在文件就显示“已接入”。

## 5.3 文档目标数据模型

| 字段 | 说明 |
|---|---|
| `document_id` | 公开稳定 ID，不使用物理路径作为 ID |
| `course_id` | 所属课程 |
| `scope_type/scope_id` | 课程或知识点范围 |
| `library_type` | course / personal |
| `owner_user_id` | 所有者 |
| `display_name` | 教师可见文件名 |
| `source_type` | pdf/docx/pptx/image/video/web 等 |
| `source_file_ref` | 后端内部文件引用 |
| `status` | 文档状态 |
| `active_index_version` | 当前可用索引版本 |
| `pending_index_version` | 重建中的版本 |
| `page_count` | 页数或媒体时长信息 |
| `chunk_count` | 可检索块数 |
| `failed_units` | 失败页／媒体片段数量 |
| `parser_name` | 解析器标识 |
| `embedding_profile_id` | Embedding 配置引用 |
| `created_at/updated_at` | 时间 |
| `indexed_at` | 最近可用索引完成时间 |
| `last_job_id` | 最近处理任务 |
| `error_code/error_message` | 失败信息 |

## 5.4 上传与索引数据流

```text
前端上传文件
   ↓
后端校验类型、大小、权限
   ↓
保存原文件 + 创建 KnowledgeDocument(received)
   ↓
创建 rag_import EduJob
   ↓ 202
前端显示“已接收，处理中”
   ↓
解析 → 分块 → 向量化 → 索引
   ↓
原子切换 active_index_version
   ↓
KnowledgeDocument=ready
   ↓
任务 succeeded，前端可测试检索
```

关键要求：

- API 不再同步执行 `import_document()` 后忽略异常；
- 上传返回 `document + job`；
- 旧索引重建时继续提供旧 `active_index_version`；
- 新索引成功后再切换；
- 新索引失败不破坏旧可用版本；
- 任务和文档状态都必须更新，但文档状态是检索可用性的最终依据。

## 5.5 RAG 接口

### 上传

`POST /api/courses/{course_id}/knowledge-base/documents`

返回 202：

```json
{
  "document": {
    "document_id": "...",
    "status": "received"
  },
  "job": {
    "edu_job_id": "...",
    "kind": "rag_import"
  }
}
```

### 文档列表

`GET /api/courses/{course_id}/knowledge-base/documents`

支持：

- 状态筛选；
- library_type；
- scope；
- 搜索；
- 排序；
- 分页。

### 文档详情

`GET /api/courses/{course_id}/knowledge-base/documents/{document_id}`

返回状态、统计、最近任务和安全诊断。

### 重试／重建

- `POST .../{document_id}/retry`
- `POST .../{document_id}/reindex`

重试失败步骤；重建创建新 index version。

### 测试检索

`POST .../{document_id}/test-retrieval`

请求：

```json
{
  "query": "什么是快速排序的分治过程？",
  "top_k": 5
}
```

返回：

- 命中片段；
- 页码／时间码；
- 相关度；
- chunk ID；
- 是否经过 rerank；
- 索引版本；
- 耗时。

测试检索只检索此文档，不生成开放式 LLM 回答，避免把“模型会说”误当作“检索命中”。

### 删除

`DELETE .../{document_id}`

流程：

1. 标记 deleting；
2. 创建删除任务或同步执行小文件清理；
3. 删除课程索引引用；
4. 删除向量／关键词索引；
5. 删除派生页面和媒体；
6. 删除或归档原文件；
7. 标记 deleted。

任何一步失败都保留可重试记录。

## 5.6 知识库页面设计

### 页面头部

- 当前课程；
- 文档总数；
- ready 数量；
- 处理中数量；
- 失败数量；
- 上传资料；
- 批量操作。

### 文档卡／列表

显示：

- 文件名和类型；
- 所属课程／知识点；
- 状态；
- 页数／时长；
- chunk 数；
- 最近索引时间；
- 上传者；
- 错误摘要；
- 测试检索、重试、重建、删除。

### 详情抽屉

- 基本信息；
- 处理阶段；
- 解析统计；
- 索引配置；
- 失败页；
- 最近任务；
- 测试检索。

### 状态文案

- received：资料已接收，等待处理；
- parsing：正在读取文档内容；
- embedding：正在建立检索索引；
- ready：可用于问答；
- partially_ready：部分内容处理失败，可用于问答；
- failed：处理失败，尚不可用于问答。

禁止笼统显示“上传成功”代表可检索。

## 5.7 引用体验

问答引用必须包含：

- 文档名；
- 页码／幻灯片号／时间码；
- 命中片段；
- document ID；
- chunk ID；
- index version。

教师点击引用：

- 打开文档预览；
- 定位到对应页或片段；
- 无法定位时仍显示命中文本；
- 权限失效时显示无权限，不泄漏内容。

## 5.8 RAG 效果验证

建立每门示例课程的黄金集：

| 类型 | 至少数量 | 验证点 |
|---|---:|---|
| 精确事实 | 5 | 正确片段与页码 |
| 概念解释 | 5 | 关键段落覆盖 |
| 跨段总结 | 3 | 多片段组合 |
| 相似概念区分 | 3 | 不混淆来源 |
| 指定文档检索 | 3 | 不命中其他资料 |
| 无答案 | 3 | 不伪造引用 |
| 更新后检索 | 2 | 使用新索引版本 |

记录：

- Top-5 命中率；
- 首条命中率；
- 引用定位正确率；
- 无答案误命中率；
- P50/P95 检索耗时；
- 解析失败率。

P1 不要求一次打开所有高级检索选项。Reranker 和查询改写通过配置中心受控启用，并用同一黄金集比较。

## 5.9 RAG 验收标准

- 上传后立即显示 received/处理中，而不是 ready；
- RAG 导入失败时文档显示 failed；
- 刷新后任务和文档状态可恢复；
- ready 文档可以执行单文档测试检索；
- 测试检索显示片段和页码／时间码；
- 重建失败不破坏旧索引；
- 删除文档后无法继续检索旧 chunk；
- 用户不能测试或读取无权限文档；
- 黄金集结果有可保存的基线报告。

---

## 6. 生成工厂设计

## 6.1 正式能力矩阵

| 能力 | P1 状态 | 创建入口 | 结果类型 |
|---|---|---|---|
| 报告 | 正式 | 生成工厂 | report |
| 教案 | 正式 | 生成工厂 | lesson_plan |
| 教学博客 | 正式 | 生成工厂 | blog |
| 习题 | 正式 | 生成工厂 | quiz |
| 小游戏 | 正式 | 生成工厂 | game |
| 思维导图 | 正式 | 生成工厂 | graph |
| AI 课堂 | 正式、独立主入口 | AI 课堂／工作台主卡 | classroom |
| PPT | 正式、恢复既有入口 | 生成工厂 | ppt |
| 闪卡 | 正式、恢复既有入口 | 生成工厂 | flashcard |
| 视频 | AI 课堂派生导出 | 课堂页面 | video artifact |
| 音频 | 不开放独立生成 | 无 | 兼容历史 |

未开放能力不得出现在空状态承诺、帮助文案或正式卡片中。

## 6.2 统一四步流程

### 第一步：选择来源

- 当前课程；
- 当前知识点；
- 课程知识库资料；
- 个人资料；
- 是否允许 Web；
- 已选择资料数量和状态。

只有 `ready` 或明确允许的 `partially_ready` 文档可以选为 RAG 来源。处理中和失败文档不可选。

### 第二步：配置

所有类型共享：

- 标题；
- 面向对象；
- 语言；
- 输出长度／规模；
- 资料使用范围；
- 保存课程和知识点。

类型专属配置保持最少：

- 报告：结构、重点；
- 教案：课时、教学目标、难度；
- 习题：题型、数量、难度、是否含解析；
- 游戏：玩法模板、题量；
- 思维导图：层级深度；
- 博客：语气、长度。
- PPT：页数、模板风格、是否包含讲稿、图文偏好；生成前允许确认大纲；
- 闪卡：卡片数量、难度或受众、可选分类、是否显示来源。

### 第三步：生成

- 提交后立即获得 `edu_job_id`；
- 弹窗可以关闭；
- 任务进入全局任务中心；
- 显示阶段、进度、耗时和安全输入摘要；
- 支持取消和失败重试；
- 刷新不丢任务；
- 不在组件内自行轮询。

### 第四步：结果

- 生成完成且资源保存成功才显示“已完成”；
- 显示预览；
- 显示保存位置；
- 显示来源资料；
- 显示配置快照；
- 支持重命名、导出、添加到对话、置顶和删除；
- 支持“基于此资源继续生成”时引用原资源 ID。

## 6.3 生成请求架构

建议统一命令结构：

```text
GenerationCommand
├─ kind
├─ owner_user_id（后端注入）
├─ course_id
├─ scope_type/scope_id
├─ source_document_ids
├─ source_artifact_refs
├─ parameters
├─ runtime_profile
└─ idempotency_key
```

每个业务生成器继续保留独立实现，但通过统一入口完成：

1. 权限校验；
2. 来源文档状态校验；
3. 配置解析；
4. 创建 EduJob；
5. 执行业务生成；
6. 保存 CourseMaterial；
7. 生成 result_ref；
8. 更新终态。

PPT 与闪卡不重写生成器。生成工厂只增加统一适配层，把既有输入和输出映射到 `GenerationCommand`、`EduJob` 和 `CourseMaterial`；如果历史链路依赖组件内轮询或临时前端文件，必须在恢复入口前改为后端任务账本和正式资源保存。

## 6.4 任务阶段规范

通用阶段：

```text
queued
validating_input
loading_sources
retrieving_context
planning
generating
validating_output
saving_resource
completed
```

类型可以增加阶段，但前端通过稳定映射显示教师文案。

`saving_resource` 失败时：

- 若生成内容仍可恢复，任务为 `partially_succeeded`；
- 后端保存可恢复的临时 result；
- 前端提供“重新保存”；
- 不显示“资源已生成并保存”。

## 6.5 输出质量检查

每类资源至少进行：

- schema 验证；
- 必填字段验证；
- 长度和空内容检查；
- 来源引用存在性；
- 文件导出有效性；
- 危险 HTML／脚本处理；
- 游戏预览沙箱；
- PPTX 文件可打开检查；
- PPT 大纲、页数和导出文件一致性；
- 闪卡正反面非空、数量范围、顺序稳定及来源引用有效性；
- AI 课堂场景校验。

## 6.6 固定样例集

每个正式生成类型准备至少 3 组样例：

1. 单一文档；
2. 多文档；
3. 无明确资料或资料不足。

记录：

- 任务成功率；
- 保存成功率；
- 平均耗时；
- 输出 schema 完整率；
- 来源引用正确率；
- 人工可用性评分；
- 刷新恢复成功率。

## 6.7 生成工厂验收标准

- 八个正式资源卡片和 AI 课堂入口清晰；
- PPT、闪卡按既有能力恢复，不以“开发中”占位结果通过验收；
- 不宣传未开放的独立音频；
- 所有正式入口使用四步流程；
- 关闭配置弹窗后任务继续；
- 刷新后任务恢复；
- 失败保留输入参数；
- 成功结果进入课程资源；
- 结果显示来源资料和配置版本；
- 保存失败不显示完全成功；
- 每类三组固定样例完成测试记录。

---

## 7. 统一课程资源模型

## 7.1 目标模型

| 字段 | 必填 | 说明 |
|---|---:|---|
| `schema_version` | 是 | 资源结构版本 |
| `material_id` | 是 | 稳定资源 ID |
| `material_type` | 是 | 统一类型 |
| `course_id` | 是 | 所属课程 |
| `scope_type/scope_id` | 是/否 | 课程或知识点 |
| `owner_user_id` | 是 | 创建者／所有者 |
| `title` | 是 | 可编辑标题 |
| `summary` | 否 | 列表摘要 |
| `status` | 是 | ready/partial/archived 等 |
| `version` | 是 | 资源版本 |
| `content_ref` | 是 | 主内容位置或嵌入内容引用 |
| `files` | 是 | 所有附件清单 |
| `source_document_ids` | 是 | 来源资料 |
| `source_artifact_refs` | 是 | 来源资源 |
| `generation_job_id` | 否 | 生成任务 |
| `config_snapshot_id` | 否 | 运行配置快照 |
| `created_at/updated_at` | 是 | 时间 |
| `created_by` | 是 | 创建者 |
| `is_pinned/pinned_at` | 是/否 | 置顶 |

## 7.2 文件清单

每个资源维护 manifest：

```json
{
  "files": [
    {
      "role": "primary",
      "path": "relative/path",
      "media_type": "application/json",
      "size": 1234,
      "checksum": "sha256:..."
    },
    {
      "role": "audio",
      "path": "relative/audio.mp3",
      "media_type": "audio/mpeg",
      "size": 4567,
      "checksum": "sha256:..."
    }
  ]
}
```

删除、备份、迁移和完整性检查全部依赖 manifest，不再只读取单个 `file_path`。

## 7.3 存储写入

文件存储继续可用，但流程必须：

1. 在资源临时目录写入所有内容；
2. 计算校验和；
3. 验证主内容 schema；
4. 写入 manifest；
5. fsync 或等效持久化；
6. 原子移动为正式版本；
7. 更新资源索引；
8. 任务标记 succeeded。

任一步失败：

- 正式资源不指向半成品目录；
- 临时目录可被清理；
- 任务记录失败或部分成功；
- 不覆盖上一可用版本。

## 7.4 类型目录

正式类型必须全部进入映射：

```text
reports
lesson_plans
blogs
quizzes
games
graphs
ppts
flashcards
classrooms
videos（若独立资源）
audio（兼容）
```

正式类型不得落入 `others`。未知旧类型可以兼容读取，但不能作为新写入默认。

## 7.5 资源接口

### 列表

`GET /api/courses/{course_id}/materials`

增加：

- 类型多选；
- 搜索；
- owner／created_by；
- 状态；
- 置顶；
- 时间范围；
- cursor 分页；
- 排序。

后端根据当前用户和课程成员权限过滤，不依赖前端 owner 参数。

### 详情

`GET /api/courses/{course_id}/materials/{material_type}/{material_id}`

- 返回统一元数据；
- 内容可内嵌或通过安全文件 URL 获取；
- AI 课堂返回课堂专用数据；
- 未知类型返回基本详情，不执行错误预览。

### 重命名

`PATCH .../{material_type}/{material_id}`

P1 只允许安全字段：

- title；
- summary；
- is_pinned。

### 删除

`DELETE .../{material_type}/{material_id}`

- 校验课程权限；
- 标记 deleting；
- 根据 manifest 删除全部文件；
- 删除索引；
- 删除关联但非共享的派生物；
- 保留审计事件；
- 完成后返回删除结果。

### 完整性检查

管理员或后台任务可检查：

- manifest 文件是否存在；
- checksum；
- 孤儿文件；
- 缺失附件；
- 无 owner 旧资源。

## 7.6 资源授权

至少定义：

```text
course_owner
course_teacher/editor
course_viewer
system_admin
```

| 操作 | owner/editor | viewer | admin |
|---|---:|---:|---:|
| 查看资源 | 是 | 是 | 是 |
| 下载 | 是 | 是，可配置 | 是 |
| 创建 | 是 | 否 | 是 |
| 重命名 | 是 | 否 | 是 |
| 置顶 | 是 | 否 | 是 |
| 删除 | 是 | 否 | 是 |
| 修改配置 | 取决于角色 | 否 | 是 |

课程 CRUD、知识库和课程资源必须使用同一授权服务。不能只在部分路由加认证。

## 7.7 AI 课堂关联

- `classroom_id == material_id`；
- AI 课堂页和课程资源页读取同一资源；
- 课堂音频、视频、字幕、时间线均进入 manifest；
- 视频导出可以是课堂 `derivatives`，或单独 video 资源指向 parent classroom；
- 删除课堂时明确是否同时删除派生视频；
- 若允许保留视频，前端必须在删除确认中说明；
- 课堂重命名后两个入口同步。

## 7.8 旧数据迁移

- 缺少 owner 的资源进入“待归属”队列；
- 单用户历史数据可在明确管理员操作下归属给指定用户；
- `others` 中 material_type=game 的资源迁移到 games；
- 缺少 manifest 的资源通过现有字段重建；
- 无法重建的标记 legacy_partial，不静默删除；
- 迁移工具先 dry-run，输出变更清单；
- 未完成归属的旧资源不得在多用户模式下默认公开。

## 7.9 资源验收标准

- 并发生成 10 个资源不损坏索引；
- 资源保存使用原子流程；
- 课程资源刷新和重登后存在；
- game 不再写入 others；
- AI 课堂两个入口同源；
- 删除课堂清理 manifest 中全部附件；
- A 教师无法读取或删除无权限资源；
- 保存失败产生部分成功或失败，不产生虚假成功；
- 旧资源迁移有 dry-run 报告。

---

## 8. 模型与服务配置中心

## 8.1 目标

教师可以配置自己使用的 API，管理员可以配置系统默认 API。授权用户无需修改源码、`.env` 或启动脚本，就能：

- 查看当前服务配置状态；
- 新建或修改配置；
- 测试连接；
- 启用；
- 停用；
- 回滚；
- 知道哪些功能使用该配置；
- 确认下一次请求已经使用新配置。

## 8.2 配置分类

### 对话与 Agent

- 默认对话模型；
- 深度回答模型；
- ReAct 模型；
- Planner；
- Executor；
- Vision；
- PPT／报告模型。

### RAG

- Embedding；
- Reranker；
- Query Rewrite；
- PDF 解析；
- 图片检索相关模型。

### 语音

- ASR；
- TTS；
- 百度语音；
- Qwen TTS 或 sidecar 服务端 TTS；
- 默认音色、语言、采样率。

### 搜索

- Web 搜索；
- 图片搜索；
- 视频检索；
- Bocha、Tavily 等当前已存在供应商。

### 课堂与 sidecar

- OpenMAIC Base URL；
- sidecar 健康检查；
- sidecar 所需模型配置引用；
- 视频导出服务状态。

### 本地兼容服务

- Ollama；
- OpenAI-compatible Base URL；
- 自定义模型名。

## 8.3 配置数据模型

### RuntimeProfile

| 字段 | 说明 |
|---|---|
| `profile_id` | 配置 ID |
| `category` | chat/rag/speech/search/pdf/classroom |
| `purpose` | default_chat、embedding、tts 等 |
| `provider` | qwen/deepseek/openrouter/ollama/custom 等 |
| `display_name` | 显示名称 |
| `base_url` | 服务地址 |
| `model` | 模型名 |
| `parameters` | timeout、temperature、dimensions 等非敏感参数 |
| `secret_ref` | 后端密钥存储引用 |
| `status` | draft/verified/active/disabled/error |
| `scope` | `system` 或 `user` |
| `owner_user_id` | 用户级配置的所有者；系统级为空 |
| `version` | 配置版本 |
| `last_verified_at` | 最近验证 |
| `last_verified_latency_ms` | 响应时间 |
| `last_error_code` | 最近错误 |
| `created_by/updated_by` | 审计 |
| `created_at/updated_at` | 时间 |

### ConfigSnapshot

每个任务开始时按“个人配置 → 系统默认 → 环境变量”的优先级解析，并保存只读快照：

- profile IDs；
- profile versions；
- provider；
- model；
- 非敏感参数；
- 不包含密钥明文。

资源保存 `config_snapshot_id`，用于解释历史结果使用了什么配置。

## 8.4 密钥存储

### 必须要求

- 密钥不写入前端持久化；
- 密钥不进入普通配置 JSON；
- 密钥使用服务端主密钥加密；
- 推荐 AES-256-GCM 或等价的认证加密；
- 主密钥由 `CONFIG_MASTER_KEY` 或部署环境秘密管理提供；
- 没有主密钥时允许读取环境变量兜底，但禁止在 UI 保存新密钥；
- 每条密文使用独立 nonce；
- 保存后 API 只返回掩码和是否已配置；
- 日志、错误和测试结果不返回密钥；
- 更新密钥时不要求前端先读取旧明文。

### 掩码

例如：

```text
sk-****9a2f
已配置（最后更新 2026-08-06）
```

掩码不是密钥的一部分，不用于鉴权。

## 8.5 配置状态

```text
draft
verifying
verified
active
disabled
error
```

规则：

- 保存产生 draft；
- 测试时为 verifying；
- 测试通过为 verified；
- 只有 verified 可以 active；
- 同一 purpose、同一 scope、同一 owner 默认只有一个 active；
- 启用新版本前保留旧 active；
- 启用失败自动回滚旧版本；
- error 不自动停用仍在工作的旧 active。

## 8.6 配置接口

### 列表

`GET /api/runtime-configs`

- 仅返回掩码；
- 支持 category/purpose/status；
- 返回当前 active 标识；
- 普通教师只能看到自己的用户级配置和系统级配置的非敏感健康状态；
- 管理员可以查看系统级配置和按权限查看用户配置审计；
- 系统级配置管理可以使用 `/api/admin/runtime-configs` 管理员别名或同一接口的 `scope=system`。

### 创建与修改

- `POST /api/runtime-configs`
- `PATCH /api/runtime-configs/{profile_id}`

请求中的 `api_key` 只作为写入字段，不在响应回显。

- 普通教师只能创建和修改 `scope=user` 且 `owner_user_id` 为自己的配置；
- 管理员才能创建和修改 `scope=system` 的配置；
- 部署策略可以禁用个人 API，此时教师只能查看系统服务健康状态。

### 测试连接

`POST /api/runtime-configs/{profile_id}/verify`

创建短任务或同步执行受限探针：

- DNS／连接；
- 鉴权；
- 模型存在；
- 最小请求；
- 响应格式；
- 延迟。

返回稳定错误码：

```text
missing_secret
authentication_failed
model_not_found
endpoint_unreachable
timeout
invalid_response
quota_exceeded
```

### 启用

`POST /api/runtime-configs/{profile_id}/activate`

- 仅 verified；
- 原子切换 active；
- 记录审计；
- 通知 RuntimeConfigRegistry 刷新；
- 返回是否立即生效；
- 不能热更新的服务返回 `restart_required` 和服务名称。

### 停用与回滚

- `POST .../{profile_id}/disable`
- `POST .../{profile_id}/rollback`

回滚选择最近 verified 版本。

## 8.7 RuntimeConfigRegistry

业务代码通过统一解析器取配置：

```text
resolve(purpose, scope)
  1. 当前用户 active 的 user profile
  2. active 的 system profile
  3. 安全的环境变量兼容配置
  4. 明确默认值
  5. 无可用配置则抛出稳定 configuration_missing
```

业务服务不得继续在多个位置直接读取不同环境变量并形成不一致优先级。

迁移策略：

- 先为对话、Embedding、TTS 建适配器；
- 再迁移搜索、PDF 和 sidecar；
- 保留现有 `Config` 作为兼容来源；
- 每次迁移一个 purpose，并加入配置来源诊断；
- 不一次性重写所有服务。

## 8.8 sidecar 配置

- 浏览器不直接向 sidecar 提交密钥；
- 主 API 保存配置；
- sidecar 通过服务端安全通道获得所需配置，或由部署层注入；
- 主 API 只向前端返回 sidecar 健康状态；
- TTS、视频和 OpenMAIC 请求记录使用的配置版本；
- sidecar 不可用时课堂本体仍可读取，生成和导出任务明确失败。

## 8.9 配置中心页面

```text
模型与服务配置
├─ 对话与 Agent
├─ RAG
├─ 语音
├─ 搜索
├─ PDF 解析
└─ AI 课堂服务
```

页面提供“我的配置”和“系统默认”两个清晰范围。普通教师管理自己的配置；管理员可以切换到系统默认配置。每张配置卡显示：

- 用途；
- 供应商；
- 模型；
- Base URL；
- API Key 掩码；
- 状态；
- 最近验证；
- 延迟；
- 使用此配置的功能；
- 编辑、测试、启用、停用、查看历史。

编辑表单：

- Provider；
- Base URL；
- Model；
- API Key；
- Timeout；
- 用途专属参数；
- 保存草稿；
- 保存并测试。

### 8.10 配置中心验收标准

- 不修改源码即可配置新的对话模型和 TTS；
- API Key 只在写请求出现一次，响应不回显；
- 页面刷新只显示掩码；
- 错误 Key 显示 authentication_failed；
- verified 配置可以启用；
- 下一次任务记录新的 config snapshot；
- 历史资源仍显示原配置版本；
- 启用失败回滚旧 active；
- 非授权用户不能修改；
- 日志和错误不泄漏密钥；
- sidecar 密钥不经过浏览器。

---

## 9. 用户中心与真实账户

## 9.1 当前问题

- 页面包含硬编码姓名外的邮箱、电话、部门、角色和简介；
- 资料修改主要保存在浏览器；
- 修改密码没有调用后端；
- 用户可能误以为安全操作已经生效。

## 9.2 P1 范围

### 个人资料

- 从当前用户 API 读取；
- 只展示后端真实字段；
- 暂未接入字段不显示模拟值；
- 可编辑字段由后端白名单控制；
- 修改后重新读取确认。

### 修改密码

- 输入旧密码；
- 新密码与确认；
- 密码强度；
- 服务端验证旧密码；
- 成功后撤销其他会话或按策略处理；
- 失败显示明确原因；
- 不在日志记录密码。

### 配置入口

- 管理员或授权角色看到“模型与服务配置”；
- 普通教师可以看到只读服务健康状态，是否开放由产品权限决定；
- 配置中心不与个人资料表单混在同一保存动作中。

## 9.3 验收标准

- 用户中心不存在硬编码个人资料；
- 修改密码真实影响下一次登录；
- 错误旧密码不会显示成功；
- 浏览器刷新后资料来自后端；
- 无配置权限用户看不到密钥表单；
- 用户退出登录时清理任务和配置相关前端缓存。

---

## 10. 跨模块数据流

## 10.1 从知识库生成报告

```text
教师选择 ready 文档
   ↓
生成报告配置
   ↓
后端校验文档权限与状态
   ↓
解析 active RuntimeProfile
   ↓
保存 ConfigSnapshot
   ↓
创建 generate_report EduJob
   ↓
检索 → 生成 → 验证 → 原子保存 CourseMaterial
   ↓
任务 result_ref 指向 report
   ↓
全局任务中心通知
   ↓
课程资源页刷新并显示来源与配置版本
```

## 10.2 从 AI 课堂导出视频

```text
课堂资源(classroom)
   ↓
创建 render_video EduJob
   ↓
解析 TTS / sidecar 配置快照
   ↓
无头浏览器按内部时间线渲染
   ↓
视频进入 classroom manifest 或关联 video 资源
   ↓
任务完成
   ↓
AI课堂页与课程资源页同时显示导出结果
```

## 10.3 配置切换

```text
管理员保存 draft
   ↓
verify
   ↓
verified
   ↓
activate（原子切换）
   ↓
RuntimeConfigRegistry 刷新
   ↓
新任务使用新版本
   ↓
旧任务和旧资源保留原 snapshot
```

---

## 11. 错误处理规范

## 11.1 稳定错误类别

```text
validation_error
permission_denied
source_not_ready
configuration_missing
authentication_failed
provider_unavailable
provider_timeout
generation_invalid_output
resource_save_failed
indexing_failed
storage_unavailable
quota_exceeded
```

每个错误返回：

- `error_code`；
- 用户可读 `message`；
- `retryable`；
- 可选 `action`；
- 诊断 ID。

不返回：

- Python/JS 堆栈；
- 本机路径；
- API Key；
- 下游完整响应；
- 其他用户信息。

## 11.2 部分成功

适用：

- 文档部分页面解析失败但其余可检索；
- 内容生成完成但持久化失败；
- 课堂生成成功但部分语音降级；
- 视频生成成功但字幕或次要附件失败。

前端必须明确：

- 已完成什么；
- 未完成什么；
- 结果是否已保存；
- 可以如何补做。

---

## 12. 可观测性与审计

## 12.1 资源追踪

每个资源可追踪：

- generation_job_id；
- source_document_ids；
- source_artifact_refs；
- config_snapshot_id；
- 创建者；
- 版本；
- 文件 manifest。

## 12.2 配置审计

记录：

- 谁创建／修改；
- 修改了哪些非敏感字段；
- 是否更新密钥；
- verify 结果；
- 谁启用／停用／回滚；
- 生效时间；
- 旧 active 版本。

不记录密钥明文。

## 12.3 指标

### RAG

- 文档处理成功率；
- 各阶段耗时；
- ready 文档数；
- 测试检索命中率；
- 引用定位正确率。

### 生成

- 各类型任务成功率；
- 保存失败率；
- P50/P95 耗时；
- 重试率；
- 部分成功率。

### 资源

- 孤儿文件数量；
- manifest 缺失；
- checksum 失败；
- 未归属旧资源数。

### 配置

- 当前 active 健康状态；
- verify 成功率；
- 供应商错误码；
- 最近成功请求时间。

---

## 13. 测试策略

## 13.1 RAG

- 上传创建 document + job；
- 各阶段状态；
- 导入失败；
- 重试；
- 重建保持旧索引；
- 单文档测试检索；
- 引用定位；
- 删除清理；
- owner 权限；
- 黄金集基线。

## 13.2 生成工厂

- 八种正式资源四步流程；
- PPT 大纲确认、PPTX 导出和刷新重开；
- 闪卡数量／正反面结构、逐张预览和刷新重开；
- 文档未 ready 时阻止提交；
- 关闭弹窗后继续；
- 刷新恢复；
- 保存失败部分成功；
- idempotency；
- 结果来源和配置快照；
- 未开放能力不出现。

## 13.3 资源存储

- 原子写入故障注入；
- 并发保存；
- checksum；
- manifest；
- 完整删除；
- 孤儿扫描；
- game、ppt、flashcard 类型目录；
- 旧数据 dry-run 迁移；
- 课程权限。

## 13.4 配置中心

- 密钥加密／解密；
- API 响应不回显；
- 连接测试错误映射；
- verified 才可启用；
- 原子切换；
- 回滚；
- 热更新；
- restart_required；
- sidecar 不经过浏览器；
- config snapshot。

## 13.5 用户中心

- 获取真实资料；
- 修改允许字段；
- 错误旧密码；
- 成功改密；
- 权限；
- 退出清理。

## 13.6 端到端场景

### 场景 A：资料到报告

1. 上传 PDF；
2. 看到 received；
3. 刷新页面；
4. 恢复 rag_import；
5. ready；
6. 测试检索命中页码；
7. 生成报告；
8. 刷新；
9. 任务完成；
10. 课程资源出现报告；
11. 报告显示来源和配置。

### 场景 B：配置到课堂视频

1. 管理员创建 TTS 配置；
2. 测试成功；
3. 启用；
4. 创建 AI 课堂；
5. 导出视频；
6. 任务使用新配置快照；
7. 资源页和 AI 课堂页显示同一结果；
8. 历史课堂仍保留旧配置版本。

### 场景 C：失败恢复

1. 使用错误模型 Key；
2. verify 返回鉴权失败；
3. 不能启用；
4. 旧 active 继续可用；
5. 生成任务不受错误 draft 影响；
6. 修正后 verify 和 activate；
7. 新任务使用新版本。

### 场景 D：越权

1. 用户 A 创建资料、任务和资源；
2. 用户 B 猜测所有 ID；
3. B 对文档、任务、资源、配置接口均无法读取或删除；
4. 响应不泄漏内容。

---

## 14. 完整验收标准

## 14.1 RAG

- [ ] 上传返回 document + job；
- [ ] 文档状态反映真实索引过程；
- [ ] RAG 失败不显示 ready；
- [ ] ready 文档可测试检索；
- [ ] 命中包含页码／时间码和片段；
- [ ] 重建失败保留旧索引；
- [ ] 删除同时清理索引和派生物；
- [ ] 黄金集有基线结果；
- [ ] 文档按用户和课程授权。

## 14.2 生成工厂

- [ ] 八种正式资源使用统一四步流程；
- [ ] AI 课堂保持独立入口；
- [ ] PPT 和闪卡恢复为正式入口，并完成生成、预览、保存、刷新恢复；
- [ ] 音频不作为正式独立能力展示；
- [ ] 所有后台生成进入统一任务中心；
- [ ] 失败保留配置输入；
- [ ] 成功结果进入课程资源；
- [ ] 保存失败不显示完全成功；
- [ ] 结果显示来源资料、任务和配置版本；
- [ ] 固定样例集完成记录。

## 14.3 课程资源

- [ ] 所有正式类型使用统一 ID 和字段；
- [ ] AI 课堂两个入口同源；
- [ ] 资源记录 owner；
- [ ] 写入原子；
- [ ] 文件 manifest 完整；
- [ ] game 不落入 others；
- [ ] 删除清理全部附件；
- [ ] 并发生成不损坏索引；
- [ ] 无权限用户不能查看或操作；
- [ ] 旧数据迁移支持 dry-run。

## 14.4 配置中心

- [ ] 可配置对话模型、Embedding 和 TTS 最小闭环；
- [ ] 教师可以配置并启用自己的 API，且只影响自己的任务；
- [ ] 管理员可以配置系统默认，未配置个人 API 的用户使用系统默认；
- [ ] API Key 加密保存；
- [ ] 响应只返回掩码；
- [ ] 可测试连接；
- [ ] verified 后才能启用；
- [ ] 激活失败自动回滚；
- [ ] 新任务实际使用新配置；
- [ ] 资源记录配置快照；
- [ ] 非授权用户不能修改；
- [ ] sidecar 密钥不经过浏览器；
- [ ] 日志和错误不泄漏密钥。

## 14.5 用户中心

- [ ] 不存在模拟个人资料；
- [ ] 修改密码调用后端并真实生效；
- [ ] 错误旧密码不显示成功；
- [ ] 配置入口受角色控制；
- [ ] 刷新后资料从后端读取。

## 14.6 系统质量

- [ ] P0 全部验收保持通过；
- [ ] 现有测试无回归；
- [ ] 新增 RAG、资源、配置、权限和故障注入测试；
- [ ] 生产构建成功；
- [ ] 关键端到端场景通过；
- [ ] 无高危密钥泄漏和越权；
- [ ] 监控可查看失败率和处理耗时。

---

## 15. 分阶段交付建议

### P1-A：RAG 可见状态与任务化

- 文档状态模型；
- rag_import 接入 EduJob；
- 用户任务恢复；
- 文档详情；
- 重试和测试检索；
- 引用定位。

出口：教师可以判断资料是否可检索。

### P1-B：生成与资源一致性

- 八类正式能力四步流程；
- 统一资源 schema；
- owner 与授权；
- 原子写入；
- manifest；
- AI 课堂同源；
- 完整删除。

出口：教师可以确认结果保存且不会串课／串用户。

### P1-C：配置中心最小闭环

优先接入：

1. 默认对话模型；
2. Embedding；
3. TTS。

完成密钥加密、测试、启用、回滚和配置快照。

出口：不修改源码即可切换三类关键服务。

### P1-D：其余服务与真实用户中心

- Reranker；
- 搜索；
- PDF；
- sidecar；
- 用户资料；
- 真实改密；
- 旧数据迁移。

出口：教师端主要外部服务均可安全管理。

---

## 16. 发布与回滚

### 16.1 功能开关

- `ENABLE_RAG_DOCUMENT_LIFECYCLE_V2`；
- `ENABLE_MATERIAL_MANIFEST_V2`；
- `ENABLE_RUNTIME_CONFIG_REGISTRY`；
- `ENABLE_SECURE_CONFIG_UI`；
- `ENABLE_REAL_PROFILE_SETTINGS`。

### 16.2 兼容读取

- 旧知识库 index 可转换为 Document 状态；
- 旧资源缺少 manifest 时使用兼容适配器；
- 旧环境变量继续作为配置兜底；
- 旧资源不因新 schema 无法打开；
- 新写入始终使用新 schema。

### 16.3 回滚原则

- UI 可以回退，数据 schema 必须向后兼容；
- 配置激活可以回滚到上一 verified；
- RAG 重建失败继续使用旧 active index；
- 资源新版本失败继续保留旧版本；
- 禁止回滚时批量删除新任务、资源或文档。

---

## 17. 实现定位参考

- 课程知识库页面：`src/stitch/pages/CourseKnowledgeBase.tsx`、`src/pages/KnowledgeBasePage.tsx`
- 教师来源面板：`src/components/teacher/SourcePanel.tsx`
- RAG 前端服务：`src/services/rag.ts`、`src/services/knowledgeBase.ts`
- 课程知识库 API：`api/src/app/api/courses.py`
- RAG 主线：`api/src/modules/rag_v2/`
- 生成工厂：`src/components/teacher/StudioPanel.tsx`
- 课程资源页面：`src/stitch/pages/CourseResources.tsx`
- 前端资源类型：`src/stitch/api/types.ts`、`src/store/teacher/useStore.ts`
- 课程资源 API：`src/stitch/api/courses.ts`、`src/services/teacher/api.ts`
- 课程资源存储：`api/src/core/course_storage.py`
- 统一任务：`api/src/app/api/jobs.py`、`api/src/app/services/job_store.py`
- 后端配置：`api/src/core/config.py`
- 语音：`api/src/app/speech/transcribe.py`
- 搜索：`api/src/app/services/deepsearch_service.py`
- PDF：`api/src/app/integrations/pdf/mineru_cloud.py`
- OpenMAIC：`api/src/app/integrations/openmaic/client.py`
- 用户中心：`src/pages/UserCenterPage.tsx`、`src/stitch/pages/Profile.tsx`
- 认证：`api/src/core/auth.py`

---

## 18. P1 完成定义

P1 完成不是“页面上出现了更多配置和状态”，而是以下闭环真实成立：

```text
资料上传
→ 状态可见
→ 检索可验证
→ 生成可恢复
→ 结果原子保存
→ 资源统一管理
→ 来源与配置可追踪
→ 权限明确
→ 失败可以恢复
```

只有这条链路通过固定样例、权限测试、故障注入和端到端验收，教师端才达到“基本可信可用”，之后再进入 P2 的 Agent 智能、记忆和工程优化。
