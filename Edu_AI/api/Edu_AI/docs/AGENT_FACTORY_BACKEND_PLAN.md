# Agent 生成工厂：后端快速集成方案（MVP 优先，后续迭代优化）

本文档用于指导在现有 Edu-AI 后端（FastAPI + rag_v2 + 课程/知识图谱存储）中快速集成 Agent，以支持“生成大纲 → 分段生成 → 组装输出”的长文本生成编排，并将课程知识图谱作为结构化约束注入生成流程。

## 0. 目标与原则

### 0.1 最短可用路径（MVP）

MVP 的目标是**尽快在后端工程中跑通一个可用的 Agent 工作流**，满足：

- 支持多步生成（Plan-and-Execute）
- 支持异步/长任务（thread_id + status 轮询）
- 支持状态持久化（先用本地 JSON 文件）
- Planner 阶段接入课程知识图谱（先做轻量匹配，后续再做语义检索/图检索）

### 0.2 MVP 暂不做（避免拖慢上线）

- 暂不引入 LangGraph / Celery 等重依赖（后续优化再上）
- 暂不做人工审查回环（HITL），先全自动闭环；第二阶段再加 `/resume`
- 暂不做 SSE/WebSocket 流式输出，先轮询；第二阶段再加流式提升体验

---

## 1. 当前后端工程可复用能力（基于现有代码）

### 1.1 FastAPI 主入口与路由风格

- 主入口：`Edu_AI/api/Edu_AI/app/main.py`
- 课程管理：`Edu_AI/api/Edu_AI/app/courses.py`
- 课程存储：`Edu_AI/api/Edu_AI/core/course_storage.py`

现有工程已经实现了多类生成接口（教案、报告、题目），可复用其：

- Pydantic 请求/响应模型
- 调用 LLM 的封装（通过 `rag_v2` 系统）
- 本地 JSON 存储（`Edu_AI/api/Edu_AI/storage/*`）

### 1.2 课程知识图谱能力

- 课程知识图谱落盘：`Edu_AI/api/course_data/courses/{course_id}/knowledge_graph.json`
- 获取全图：`GET /api/courses/{course_id}/knowledge-graph`
- 获取子树（已实现）：`GET /api/courses/{course_id}/knowledge-graph/nodes/{node_id}`

**提示**：计算思维课程的图谱文件：

- `Edu_AI/api/course_data/courses/computational-thinking/knowledge_graph.json`

---

## 2. Agent 架构设计（MVP：Plan-and-Execute）

### 2.1 状态定义（State Schema）

建议使用 Pydantic 或 TypedDict 约束结构（MVP 可先用 dict 存储，Pydantic 用于入参/出参校验）。

必备字段：

- `thread_id`: str 任务ID
- `course_id`: str 课程ID
- `topic`: str 用户输入主题
- `knowledge_graph_subtree`: dict | null 与 topic 相关的知识图谱子树（用于约束/引导大纲）
- `outline`: list 结构化大纲（章节列表）
- `current_section_idx`: int 当前生成进度
- `drafts`: dict 每个章节的草稿内容（markdown）
- `final_markdown`: str 最终文章
- `status`: str 任务状态
  - `planning` / `executing` / `assembling` / `completed` / `failed` / （后续）`waiting_for_review`
- `error_message`: str | null 错误信息

### 2.2 节点划分（最少 3 个节点）

1. **Planner（规划器）**

- 输入：`topic` + `course`信息（可选）+ `knowledge_graph_subtree`
- 输出：结构化 `outline`（JSON）

2. **Executor（执行器）**

- 循环按 outline 的章节逐段生成
- 每段生成建议注入：
  - 当前章节标题
  - 当前章节关键概念（如果大纲中提供）
  - 上一章节摘要（滚动摘要，避免上下文膨胀）
  - （可选）RAG 检索片段

3. **Assembler（组装器）**

- 按大纲顺序拼接 `drafts` → `final_markdown`
- 输出：完整 Markdown

### 2.3 最小失败保护（防死循环/成本失控）

- 每个章节生成失败最大重试次数：建议 2~3
- Planner JSON 解析失败：可做 1~2 次重试
- 任务失败时：`status=failed` 并写入 `error_message`

---

## 3. 后端 API 设计（MVP：轮询模式）

本节推荐接口路径以“教学博客生成”为例（与 `agent生成工厂.md` 保持一致）。

### 3.1 启动任务

- `POST /api/blog/generate/start`

请求体（示例）：

```json
{
  "course_id": "computational-thinking",
  "topic": "排序算法",
  "selected_doc_ids": ["..."],
  "top_k": 5
}
```

返回：

```json
{
  "thread_id": "blog_1730000000_xxxx"
}
```

### 3.2 查询状态

- `GET /api/blog/task/{thread_id}/status`

返回字段建议：

```json
{
  "thread_id": "...",
  "status": "planning|executing|assembling|completed|failed|waiting_for_review",
  "progress": {
    "current_section_idx": 1,
    "total_sections": 6
  },
  "outline": [],
  "final_markdown": "...",
  "error_message": null
}
```

### 3.3（第二阶段）人工审查后恢复

- `POST /api/blog/task/{thread_id}/resume`

请求体：

```json
{
  "updated_outline": [
    {"title": "...", "key_concepts": ["..."], "word_count": 600}
  ]
}
```

---

## 4. 状态持久化方案（MVP：本地 JSON 文件）

### 4.1 为什么先用本地 JSON

- 实现最快
- 和现有工程存储风格一致（已有 `Edu_AI/api/Edu_AI/storage/*`）
- 适合验证 Agent 工作流是否有效

### 4.2 建议存储位置

- `Edu_AI/api/Edu_AI/storage/agent_tasks/`

文件命名：

- `blog_{thread_id}.json` 或 `{thread_id}.json`

写入策略：

- 每个节点完成后落盘（Planner、每章 Executor、Assembler）
- status 查询接口只需读文件

---

## 5. 知识图谱接入（先轻量匹配，后续再增强）

### 5.1 MVP：topic → 相关子树（关键词包含匹配）

实现要点：

- DFS 遍历图谱树，收集所有节点的 `label`
- 计算匹配：`topic` 是否出现在 `label` 中，或简单分词后做包含
- 找到 top-N（建议 1~3）最相关节点
- 将这些节点（含其 children）作为 `knowledge_graph_subtree` 注入 Planner prompt

收益：

- 大纲更贴合课程结构
- 减少“误差传播”：大纲错了导致后续章节都错

### 5.2 后续增强方向

- 节点向量化 + 语义检索（更鲁棒）
- 结合教学目标：生成大纲时强制覆盖某些 pillar/category
- 更细粒度：章节生成时根据章节标题再次定位子树，给当前段落更强约束

---

## 6. 快速落地的代码组织建议（最少侵入）

建议新增一个 app 子模块，参考现有 `app/pipeline/` 组织方式。

推荐目录：

- `Edu_AI/api/Edu_AI/app/blog_agent/`

包含：

- `models.py`：请求/响应模型、State schema
- `storage.py`：任务状态 JSON 存储（create/update/load）
- `engine.py`：Planner/Executor/Assembler 逻辑，封装对 `rag_system._call_llm` 的调用
- `routes.py`：FastAPI 路由（start/status/resume）
- `__init__.py`：导出 router

在 `app/main.py` 注册：

- `app.include_router(blog_agent_router, prefix="/api/blog")`

---

## 7. Prompt 设计（MVP 版本）

### 7.1 Planner Prompt（输出结构化 JSON）

核心约束：

- 必须输出 JSON（便于前端树状展示、后续章节迭代）
- 大纲章节建议包含：
  - `title`
  - `key_concepts`（可为空数组）
  - `estimated_word_count`

Planner 输入内容：

- topic
- 课程名（可选）
- knowledge_graph_subtree（结构化约束，告诉模型“只围绕这些概念组织大纲”）

### 7.2 Executor Prompt（每章 500~800 字）

建议每章生成控制在 500~800 字，避免一次性输出过长导致质量下降/截断。

每章输入：

- 章节标题
- 章节关键概念
- 上一章摘要（可选）
- （可选）RAG 片段（top_k=3）

输出：

- Markdown 段落（带小标题/代码块可选）

---

## 8. 第二阶段优化路线（按收益优先级）

1. **人机回环（HITL）**

- Planner 后进入 `waiting_for_review`
- 前端编辑大纲后调用 `/resume`

2. **SSE/WebSocket 流式输出**

- 每生成一章 push 一次
- 显著提升体验

3. **Hierarchical RAG（父子文档检索）**

- 子块索引提高召回
- 父块返回保证上下文

4. **Reviewer / Reflection 节点**

- 检查重复、逻辑连贯、结构一致
- 设置最大重试次数，避免死循环

---

## 9. 与现有功能的集成建议

### 9.1 优先落地目标

建议先集成到“教学博客生成”，因为它最符合长文本、多步骤编排的需求。

后续可复用同一套 Agent 基架到：

- 教案生成（拆分：目标→流程→活动→作业）
- 报告生成（拆分：摘要→章节→结论→建议）

### 9.2 与课程系统集成

- `course_id` 作为 Agent 的核心上下文
- 规划阶段读取 `knowledge_graph.json`，并可选读取 `course_info.json` 的教学目标

---

## 10. 验收清单（MVP）

- 能通过 `POST /api/blog/generate/start` 启动生成并返回 thread_id
- 能通过 `GET /api/blog/task/{thread_id}/status` 查询状态与进度
- 任务完成后 `final_markdown` 可用
- 状态可持久化（服务重启后仍可查询已完成任务）
- Planner prompt 使用课程知识图谱约束，生成大纲结构更稳定

