# DeepSeek Harness：普通对话与报告首版接入

日期：2026-09-07。状态：代码已接入，可通过配置开关启用；当前运行服务尚未切换。此前的[功能拆分设计](deepseek-harness-capability-decomposition-cn.md)与[记忆设计](deepseek-harness-memory-design-cn.md)是后续完整目标，不能视为本版全部已实现。

## 覆盖范围

启用 `USE_DEEPSEEK_HARNESS` 后：

- `/api/chat/v2/reply` 和 `/api/chat/v2/stream` 的普通文本请求进入 dsh。
- `generate.report` 的聊天动作进入同一运行路径；`/api/chat/v2/report` 的普通聊天报告入口也复用该路径。
- 支持普通问答、相关用户记忆注入、近期历史恢复、RAG/Web 工具、大纲生成／修改、版本确认、报告任务提交／查询／取消与基础结构检查。
- 图片／视频输入、已有资料修订、其他显式资源动作保留旧入口。知识库直接报告入口（`entry_mode=knowledge_base_report`）和其他专用资源 API 暂未迁移。

**自由文本中的其他资源生成尚未接入本版 Harness 工具集。** 启用后需要教案、习题、课堂等产物时，仍应使用现有资源按钮／专用入口；这也是本版不默认全量启用的原因之一。

## 实际调用结构

```text
Chat V2 / 普通报告入口
  → 原认证与课程／知识点范围解析
  → MainOrchestrator 选择 HarnessRuntime
  → Python DeepSeekHarness SDK → dsh sdk-minimal
      → 常驻教育根角色
      → 原生 edu-report Skill
      → MCP stdio proxy → 请求专属的本地工具桥接
          → RAG / Web 检索
          → typed 报告大纲
          → GenerationCommandService
              → 现有 durable executor / GenerationTaskHandler
              → 现有报告正文生成与资料存储
          → 查询任务、读取报告与结构验证
  → 既有 metadata / delta / tool_* / task_submitted / result / done 协议
```

桥接只负责将 MCP 请求送到 API 进程中已认证的 Python 服务；模型循环和 Skill 加载由 dsh 执行。没有把旧 ReAct/LangGraph 循环包进一个 Harness 工具。

## 代码位置

| 模块 | 职责 |
| --- | --- |
| [harness/runtime.py](../../backend/src/app/chat/harness/runtime.py) | SDK/profile 配置、根角色、逐轮上下文、SSE 事件映射、超时与子进程关闭 |
| [harness/tools.py](../../backend/src/app/chat/harness/tools.py) | 六个 typed 工具、权限复核、证据引用、大纲版本、真实确认、任务提交和读取 |
| [harness/store.py](../../backend/src/app/chat/harness/store.py) | 按用户／课程／范围／会话隔离的状态文件、事件记录、跨进程文件锁 |
| [bridge.py](../../backend/src/app/chat/harness/bridge.py) 与 [mcp_proxy.py](../../backend/src/app/chat/harness/mcp_proxy.py) | 只监听 loopback 的请求级桥接、随机令牌认证、MCP stdio 代理 |
| [edu-report/SKILL.md](../../backend/src/app/chat/harness/skills/edu-report/SKILL.md) | 报告流程、只出大纲、改纲、确认、提交、查询与取消规则 |
| [MainOrchestrator](../../backend/src/app/chat/orchestrator/main_orchestrator.py) | 同步与流式统一选择，报告 action_hint 不再绕开 Harness |
| [ReplyServiceV2](../../backend/src/app/chat/application/reply_service_v2.py) | 沿用消息与长期记忆写入；避免把已存报告重复保存；跳过成功响应重放的重复写入 |
| [schemas_v2.py](../../backend/src/app/chat/api/schemas_v2.py) | 接受新 trace path，并保留 task_id、大纲引用和 verification 字段 |

SDK 固定 `deepseek-harness-sdk==0.1.2rc1`，对应 runtime wheel 由该 SDK 的精确依赖安装。MCP 代理只用 Python 标准库，无需安装额外 MCP 框架。

## 本版执行规则

1. 根角色始终注入；只从受控目录发现报告 Skill。关闭 SDK minimal 的 shell 与文件编辑工具，不加载服务器上其他 Skills。
2. 工具不接受 owner／角色／课程权限参数；使用请求身份并在调用时复核课程访问。资料范围由 capability 与现有检索服务控制。
3. 检索结果保存为显式 evidence_id，大纲引用这些 ID；生成不再读取旧 ctx 的私有缓存。Web 复用现有 `save_to_kb=False` 路径。
4. 大纲是经过验证的章节结构，Markdown 为展示形式。修改增加 revision，并使本轮确认失效。已提交的大纲不可原地修改。
5. 用户回复“确认大纲并继续”时，在模型执行前绑定当前持久化的大纲版本。没有允许模型自行授权的工具或 approved 参数。
6. 提交使用用户、会话、大纲 ID 与版本形成稳定幂等键，复用 GenerationCommandService。入队失败不能显示为提交成功。
7. 已提交的报告继续后台执行，SDK turn 结束或 SSE 断开不自动取消业务任务。取消通过专用工具明确执行。
8. 查询仅能访问本会话记录且属于当前用户和课程的任务。报告完成检查包括产物可读、存在正文和大纲章节顺序；**不等于语义正确性或事实核验**。
9. dsh 出错后返回明确失败，不自动再运行旧 Agent，以免重复产生副作用。

## 记忆与恢复的实际实现

本版没有依赖 SDK minimal 的跨进程自动恢复。每轮启动独立 SDK 进程，从应用保存的近期对话、当前大纲、任务引用和原有 MemoryService 上下文重新组装输入；正常关闭后回收进程。验证中的每一轮都重新创建 runtime，第二轮仍能回答上一轮问题。

持久化目录为 `Config.STORAGE_ROOT/deepseek_harness/<scope-hash>/`：

- `state.json`：近期消息、大纲、证据、任务和近期 request_id 响应记录；原子替换。
- `events.jsonl`：请求、关键 dsh 工具事件、应用工具结果和最终响应；不把 reasoning delta 发给前端。
- `session.lock`：同一范围内的会话串行执行；并发冲突给出忙碌提示。

这是一套**单机／共享本地持久卷的试点存储**。多机器部署、完整事件投影、可靠异步记忆提取、删除传播和原生压缩尚未按目标设计完成。原有长期记忆读写继续复用，不能宣称记忆迁移已经全部完成。

同一 request_id 的已完成响应可重放；重试必须保持请求参数一致。后台任务幂等另由业务命令保障。文件状态需要随应用存储备份，不能放入随容器重建丢失的目录。

## 启用与回退

在后端 Python 环境安装更新后的依赖，然后在项目根 `.env` 设置：

```dotenv
USE_DEEPSEEK_HARNESS=true
DSH_MODEL=deepseek-v4-flash
DSH_TIMEOUT_SECONDS=180
```

复用已有 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`。报告正文服务继续使用平台自身的模型配置；Harness 模型与正文生成模型是两个可独立配置的位置。

配置在进程启动时读取，需要重启后端生效。本次已在本机后端 Python 环境安装 SDK，但未修改根 `.env`，未重启正在运行的服务；`.env.example` 默认开关为 false。

回退时关闭该开关并重启后端。已经提交的报告仍由原 durable runtime 执行。不要删除会话文件或已有 job 来实现回退。

## 验证

使用后端环境中的 Python：

```bash
python scripts/test-deepseek-harness.py
python scripts/verify-deepseek-harness.py --output /tmp/edu-harness-live-new-run
```

第一条运行隔离回归；第二条会真实调用配置的模型，使用专用用户、课程和临时文件存储完成五轮报告验证。验证脚本阻止旧 RAG 模块再次加载 `.env`，并检查 job／报告实际落在指定目录。

结果及尚未覆盖的场景见[首版验收记录](../acceptance/2026-09-07-deepseek-harness-report-dialogue-acceptance-cn.md)。

## 知识点大纲优化增量（2026-09-07）

根角色现从 `harness/root-role.md` 始终加载。报告 Skill 先组织内容，再生成大纲；新增 `organize_report_content`，共七个工具。组织结果绑定主题、受众、要求与来源策略，带目标、先修、实例、误区、自检与独立模型审查。大纲检查模块覆盖和顺序，模型审查不等于完整事实核验。旧无 organization_id 调用保留结构校验兼容，但开始组织后不得跳过该步骤。

`web_search` 新增 domains 与 reference_urls：前者在服务端严格过滤，后者支持 Python 文档、Cornell CS 和 MIT OCW 的 HTTPS 页面，不跟随重定向，限制体积并检查公网地址。检索未命中不会伪造来源。白名单之外的参考页、搜索供应商召回和 rerank 404 尚待后续改善。

内容组织与大纲生成使用专用非思考网关，避免有限输出预算被推理消耗导致空结果；组织结果的语义审查使用独立调用并要求至少四项推演记录，其余业务模型调用路径不受影响。组织记录使用同会话本地存储，不代表已实现长期用户记忆。

## 完整正文审阅增量（2026-09-08）

Harness 报告提交现包含结构化组织与章节快照；后台使用 `reviewed_report.py` 生成、审阅、最多两次修订后再保存。保存与查询都校验同一正文的审阅记录，取代旧的“只有基础结构校验即可交付”行为；非 Harness 报告路径不变。模型审阅会漏检，最终样例另经过外部反馈修订，详见[验收](../acceptance/2026-09-08-reviewed-report-acceptance-cn.md)。

## 主系统启用（2026-09-08）

应用户要求，根 `.env` 已设为 `USE_DEEPSEEK_HARNESS=true`、`DSH_MODEL=deepseek-v4-flash`、`DSH_TIMEOUT_SECONDS=300`。已通过 `systemctl --user restart edu-ai-backend-session.service` 重启主后端（127.0.0.1:8001）。原有前端入口继续使用该后端，无需另起 Harness 演示服务。

实际认证流式接口 `/api/chat/v2/stream` 已返回 `trace.path=deepseek-harness`。验证使用既有测试账号、新建测试对话；没有修改用户原有对话。课程/知识点解析仍在 Harness 前执行，验证报告应先选择课程和具体知识点。

页面新建对话，输入报告需求；大纲后回复“确认大纲并继续”，随后在任务完成后查询报告结果。已支持的范围为普通文本对话与报告；其他显式资源入口保持既有实现。回退时将开关设为 false 并重启同一服务。前文的“尚未启用”描述为历史验证状态，以本节为当前状态。

主系统报告验证已完成：选定“计算思维 / 迭代、递归与终止条件”知识点，经认证流式接口成功调用 organize_report_content 和 draft_report_outline，返回保存的大纲版本；本轮未提交主系统正文任务，留给用户实际验证。[启用证据](../acceptance/evidence/2026-09-08-reviewed-report/main-system-enablement.json)。
