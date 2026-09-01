# 后端架构重构设计

**Date:** 2026-05-06

**Scope:** `backend/src` 后端架构重构，重点是可读性、职责边界和可维护性，外部接口尽量保持兼容。

**Decision:** 保持现有 HTTP 接口和返回结构优先兼容，先重构内部结构，再逐步收口历史实现与测试残留。

---

## 1. 背景

当前后端可以运行，但结构已经明显失去层次感：

1. `backend/src/app/main.py` 同时承担应用装配、Pydantic 模型定义、业务编排、文档拼接、错误处理和部分领域逻辑。
2. `backend/src/app/auth.py`、`pipeline/routes.py`、`video_routes.py`、`speech/routes.py`、`courses.py` 等模块虽然已经按路由分散，但业务与基础设施仍然混在一起。
3. `backend/src/app/chat/` 已经有 `domain / agents / workflows / memory / legacy` 等子目录，说明系统已经具备分层雏形，但没有统一收口。
4. `backend/src/core/config.py`、`core/auth.py`、`core/*_storage.py` 负责配置与持久化，但还没有清晰地和业务层隔离开。
5. `api/frontend/scripts/` 里堆着大量 `test_*.py`、探针脚本和一次性验证脚本，它们对开发有帮助，但不应继续混在主业务结构里。
6. `AI_Lecturer/`、`html2ppt/`、`rag_v2/` 等子系统很重，必须通过明确的适配层接入，不能继续让总入口直接背实现细节。

这个项目的问题不是“没有功能”，而是“功能太多，入口太胖，边界太松”。

## 2. 目标

这次重构要达到以下效果：

1. 让 `main.py` 只负责应用装配，不再承载业务逻辑。
2. 让路由层只做请求接收、参数校验和响应返回。
3. 把业务编排下沉到 service / use case 层。
4. 把领域规则、数据结构和外部适配分开。
5. 保持现有主要接口兼容，减少前端和部署侧改动。
6. 把测试脚本、探针脚本和历史实验代码从正式业务路径中剥离。
7. 让每个模块只做一件事，后续能独立修改和测试。

## 3. 非目标

本阶段不做这些事：

1. 不大改对外 API 路径。
2. 不重做前端联调协议。
3. 不把整个后端拆成微服务。
4. 不一次性删除所有历史代码。
5. 不追求同时清空所有测试和实验脚本。
6. 不把重构和功能扩展混在一起。

## 4. 兼容策略

对外接口尽量不动，特别是这些现有调用面：

1. `/api/auth/*`
2. `/api/pipeline/*`
3. `/api/video/*`
4. `/api/speech/*`
5. `/chat`
6. `/conversations/*`
7. `/teacher/*`
8. `rag_v2` 暴露的现有路由

如果某些内部命名需要变，优先通过适配层、重导出或薄封装来保持旧行为。只有在确认无调用方依赖、且收益明显时，才考虑调整接口形状。

## 5. 选定方案

采用“分层单体”方案。

### 5.1 为什么这样拆

1. 当前系统已经是单体运行模式，先收口结构比重写边界更稳。
2. 主要痛点在可读性和职责混杂，不在分布式部署。
3. 现有功能跨度很大，先统一内部结构，能最大化保留可运行性。
4. 对前端来说，兼容现有接口比接口升级更重要。

### 5.2 为什么不直接改成微服务

微服务化会引入服务发现、接口网关、跨服务测试、部署编排和更多运维复杂度。当前问题还没到这个阶段，先把单体切干净更划算。

## 6. 目标目录结构

```text
backend/src/
  app/
    main.py
    bootstrap.py
    dependencies.py
    exceptions.py

    api/
      __init__.py
      auth.py
      health.py
      chat.py
      chat_v2.py
      courses.py
      pipeline.py
      speech.py
      video.py
      deepsearch.py
      blog.py
      teacher.py

    schemas/
      __init__.py
      auth.py
      chat.py
      lesson_plan.py
      report.py
      quiz.py
      question.py
      video.py
      common.py

    services/
      chat/
      lesson_plan/
      report/
      quiz/
      course/
      pipeline/
      video/
      speech/
      deepsearch/

    domain/
      chat/
      report/
      lesson_plan/
      quiz/
      course/
      pipeline/

    integrations/
      rag/
      llm/
      storage/
      lecturer/
      html2ppt/

    legacy/
      chat/
      route_compat.py
      old_handlers/

  core/
    config.py
    auth.py
    user_storage.py
    user_profile_storage.py
    lesson_plan_storage.py
    course_storage.py
    conversation_storage.py
```

### 6.1 职责定义

`app/main.py`
: 只做 FastAPI 实例创建、中间件注册、路由挂载、启动/关闭事件。

`app/api/*`
: 只做 HTTP 层。这里可以做 `Depends`、参数校验、response_model 绑定，但不直接堆业务流程。

`app/schemas/*`
: 统一放请求/响应模型，避免 `main.py` 或路由文件里塞大量 `BaseModel`。

`app/services/*`
: 负责业务编排，比如“生成教案”、“生成题目”、“聊天上下文拼装”、“课程资源聚合”。

`app/domain/*`
: 放领域对象、枚举、规则、状态结构和纯数据约束。

`app/integrations/*`
: 放 RAG、LLM、外部进程、文件系统、视频/语音等适配器。

`app/legacy/*`
: 放暂时还不能删、但不想继续扩散的旧逻辑，禁止新代码直接依赖。

`core/*`
: 继续承担配置、认证和现有持久化实现，作为基础设施过渡层。

## 7. 当前模块归类

### 7.1 保留并下沉

这些是当前主链路功能，必须保留：

1. `app/main.py`
2. `app/auth.py`
3. `app/courses.py`
4. `app/pipeline/routes.py`
5. `app/video_routes.py`
6. `app/speech/routes.py`
7. `app/deepsearch.py`
8. `app/blog_agent/*`
9. `app/chat/*`
10. `app/chat/api/routes_v2.py`

它们要么迁移到 `app/api`，要么拆出 service / integration 层，再由路由层调用。

### 7.2 保留为共享基础设施

1. `core/config.py`
2. `core/auth.py`
3. `core/*_storage.py`

这些文件先保留，但要逐步收紧职责。`config` 只管配置，`auth` 只管身份校验，`storage` 只管持久化。

### 7.3 进入 legacy

1. `app/chat/legacy/*`
2. 旧的兼容处理逻辑
3. 不再作为主入口的历史分支代码

进入 legacy 后，新代码不再反向依赖它们，只允许兼容层短期读取。

### 7.4 进入 devtools / scripts

1. `scripts/test_*.py`
2. 探针脚本
3. 一次性验证脚本

它们属于开发工具，不属于正式业务层。后续可整理到 `tools/` 或保留在 `scripts/` 但不再被运行入口引用。

## 8. 重构顺序

### 第 1 步：瘦身入口

把 `app/main.py` 改成纯装配层：

1. 创建 `FastAPI` 实例。
2. 注册 CORS。
3. 挂载所有 router。
4. 注册 startup / shutdown。
5. 不再定义领域模型和大段业务函数。

### 第 2 步：抽出 schema

把 `main.py` 和路由文件里的请求/响应模型移动到 `app/schemas/*`，避免模型定义散落。

### 第 3 步：抽出 service

把以下逻辑下沉：

1. 教案生成的 prompt 拼接和文档解析。
2. 题目生成的 JSON 清洗与结构化。
3. Chat 的上下文装配、历史读取、文档解析和来源整理。
4. 课程资源聚合逻辑。
5. 视频、语音、RAG、AI Lecturer 的调用编排。

### 第 4 步：整理 integrations

把外部系统接入统一封装：

1. RAG 系统的查询、文档解析、文档 ID 解析。
2. LLM 模型选择和调用。
3. AI Lecturer 进程管理。
4. 视频流、语音转写、html2ppt 调用。

### 第 5 步：收口 legacy

把旧兼容逻辑从主业务里移走，保留短期兼容，但禁止新功能继续堆进去。

### 第 6 步：整理开发脚本

把 `scripts/` 中的验证脚本标记为开发工具，避免它们再被误当成正式业务代码。

## 9. 具体边界

### 9.1 `main.py`

只保留这些内容：

1. `FastAPI` 初始化。
2. `Config.ensure_directories()`。
3. 路由挂载。
4. 中间件。
5. 启动/关闭钩子。

不再保留：

1. Pydantic 请求/响应模型。
2. prompt 拼接逻辑。
3. RAG 文档解析。
4. Chat 历史组织。
5. 题目清洗和 JSON 修复逻辑。

### 9.2 `app/api`

路由层只做这些事：

1. 读取请求。
2. 调用 service。
3. 返回 response model。
4. 将业务异常转换成 HTTP 异常。

### 9.3 `app/services`

service 层负责：

1. 业务流程的顺序控制。
2. 领域规则组合。
3. 输入预处理和输出整理。
4. 不关心 HTTP 细节。

### 9.4 `app/domain`

domain 层只放纯结构和规则：

1. conversation state
2. route decision
3. artifact reference
4. lesson plan / report / quiz / question 相关结构

不得在 domain 中直接调用 FastAPI、文件系统、LLM 或外部网络。

### 9.5 `app/integrations`

这里放所有“世界边缘”：

1. 文件存储。
2. 模型调用。
3. RAG。
4. 外部服务适配。
5. 进程启动与守护。

## 10. 迁移策略

### 10.1 先保持兼容

所有主要接口先保持：

1. 路径不变。
2. 返回字段不变。
3. 请求字段尽量不变。
4. 错误码语义尽量不变。

### 10.2 先搬运，再提纯

先把逻辑移动到新文件，再决定是否可以继续拆细。不要一边搬一边大改行为。

### 10.3 先机械拆分，再优化

先把“能读懂”做到位，再谈“更漂亮”。

## 11. 验收标准

重构完成时，至少满足这些条件：

1. `app/main.py` 只负责装配，不再包含大段业务逻辑。
2. 路由、服务、领域、集成层职责清楚。
3. `main.py` 中不再定义大量请求/响应模型。
4. `chat`、`pipeline`、`video`、`speech`、`courses`、`deepsearch` 的核心流程都能在独立 service 中看懂。
5. `legacy` 只保留兼容代码，不再被新代码依赖。
6. `scripts/` 不再作为主业务代码的入口依赖。
7. 主要接口保持兼容，调用方不需要同步大改。
8. 代码结构能让新维护者快速定位“请求在哪进、业务在哪做、数据在哪存、外部服务在哪接”。

## 12. 验证

至少做这些验证：

```bash
cd D:\Edu_AI_1\Edu_AI
python -m compileall backend\src
python -m pytest api\frontend\tests
```

另外再做一次导入检查，确保主线代码没有反向依赖 legacy：

```bash
rg "from ['\"].*legacy|from ['\"].*/legacy" backend/src
```

以及确认入口文件已经足够薄：

```bash
rg -n "class .*BaseModel|@app\\.|def .*lesson_plan|def .*chat|def .*questions" backend/src/app/main.py
```

## 13. 风险与控制

### 风险：入口拆薄时路由断开

控制：每迁移一组路由就跑一次基础验证，别把所有文件一起搬完再试。

### 风险：兼容层变成新负担

控制：legacy 只允许短期保留，并在每次迭代里收敛一个小块。

### 风险：服务层继续膨胀

控制：按业务域拆 service，不按“技术名词”堆文件。

### 风险：外部适配和业务逻辑重新混在一起

控制：凡是调用 RAG、LLM、视频、语音、文件系统、外部进程的逻辑，都先放进 integrations。

### 风险：测试脚本影响主结构判断

控制：把 `scripts/` 视为开发工具，不再让它们参与架构边界判断。

## 14. 后续阶段

等这一轮结构稳定后，再做这些事：

1. 把 `app/chat` 继续拆细，去掉过多的聚合职责。
2. 给路由和 service 加更明确的单元测试。
3. 清理历史兼容层。
4. 统一 API 客户端和模型调用封装。
5. 处理编码混乱和文案重复。
6. 再考虑是否需要版本化 API。

## 15. 结论

这次重构的重点不是改接口，而是把后端从“一个能跑的大堆栈”整理成“入口薄、边界清、职责明”的分层单体。

这样做能保住现有前端和部署方式，同时让后端变得真正可读、可改、可测。
