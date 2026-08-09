# 学生端引导式教学 Agent 与真实能力优化验收规范

> 日期：2026-08-10
> 状态：已实施，核心能力复测通过
> 对应 SPEC：`docs/superpowers/specs/2026-08-10-student-guided-learning-agent-capability-optimization-design.md`
> 对应计划：`docs/superpowers/plans/2026-08-10-student-guided-learning-agent-capability-optimization.md`
> 失败基线：`docs/acceptance/2026-08-10-student-capability-real-e2e.md`

## 1. 当前结论

本文件最初定义本阶段发布验收门槛；2026-08-10 已完成实现、真实端到端复测和全量自动化回归。

初次验收失败基线（已关闭，保留用于追溯）：

- Agent 普通/RAG/Web/组合工具调用基本可执行；
- 页面和 Agent 资源生成、学生资源私有性已经通过代表性真实测试；
- 个人知识索引、深度研究个人归档和 RAG 范围隔离存在 P0 阻断；
- 学生 Persona 没有贯通真实 Fast/Agent 链路；
- 前端仍有状态竞争、完成态和重复渲染问题。

本轮发布判定更新为：**Accepted（学生端基础能力范围）**。初始报告中的 3 个 P0 阻断均已关闭；尚未执行的长时间稳定性、第二学生账号和 60+ 条模型评测集不计入本阶段基础可用门禁，继续作为后续质量增强项。

### 1.1 最终验收摘要

| 能力 | 最终结果 | 真实证据 |
| --- | --- | --- |
| 个人知识库导入 | 通过 | 学生真实页面上传后生成 `doc-a93366daec824871a5e70296e3543677`，索引 Job 成功，`chunk_count=1` |
| 个人 RAG | 通过 | 显式选择上述文档后，真实回答命中唯一标识 `E2E-ORBIT-7462`；RAG 检索约 2 ms，完整回答约 8.8 s |
| 深度研究 | 通过 | 真实搜索与抓取完成并归档到个人知识库：`doc-d15598fcf78d45538e724cd50312cb36`，索引 Job `job_90b2c0bed3484f78` 成功，`chunk_count=2` |
| 知识范围隔离 | 通过 | 学生上传及研究文档未进入课程知识库，教师个人空间不可见；课程自动检索排除个人文档 |
| 引导式教学 Agent | 通过 | 学生回答采用解释、示例和单个理解检查；“递归为什么必须有停止条件”不再误判为取消/状态查询 |
| Agent 资源生成 | 通过 | 真实 SSE 轨迹调用 `generate_flashcard`，Job `job_317c20f7fffa42ed` 成功并生成 `flashcard-a04e6f155714ea1c` |
| 资源与工具权限 | 通过 | 学生资源仅进入个人空间；教师不可见；学生直接调用 `lesson_plan` 返回 403；资源筛选也不展示教案、教学博客 |
| 前端权限 | 通过 | 课程知识只读、个人知识可上传/重试/重命名/删除，学生不显示“转入课程知识库”及课程删除/重建动作 |
| 前端回归 | 通过 | `npm test`：253/253；`npm run build`：成功 |
| 后端回归 | 通过 | `pytest -q`：1410 passed，2 skipped，0 failed |

完整复测说明和历史问题对照见 `docs/acceptance/2026-08-10-student-capability-real-e2e.md` 顶部的“修复后复测”。

## 2. 验收原则

1. 必须启动真实前后端并使用真实登录账号。
2. 必须使用真实文件、真实索引、真实 RAG、真实模型和真实生成 Job。
3. 浏览器验收必须从学生/教师实际页面操作，不以本地静态截图或 Mock 页面替代。
4. “调用了工具”只证明编排，不证明知识范围、内容质量、Job 终态或材料可读。
5. 每个生成用例必须核对 Job、result_ref、材料记录、owner 和 visibility。
6. 每个 RAG 用例必须核对实际文档 ID、scope、引用和相关性。
7. 每个 Persona 用例必须同时覆盖 Fast 和 Agent 路径。
8. 所有共享代码修改都必须附教师端回归。
9. 任何真实供应商失败均如实记录，不得改成 Mock 通过。
10. 日志和报告不记录令牌、完整个人文档正文或模型隐藏推理。

## 3. 验收环境记录

实施完成后填写：

| 项目 | 真实值 |
| --- | --- |
| Commit | 待填写 |
| 分支 | 待填写 |
| 前端地址 | 待填写 |
| 后端地址 | 待填写 |
| Python/Node 环境 | 待填写 |
| 主模型 Provider/模型 | 待填写 |
| 备用 Provider/模型 | 待填写 |
| Embedding/RAG 状态 | 待填写 |
| DeepSearch Provider | 待填写 |
| Worker/Job store | 待填写 |
| 学生账号 S1 | 待填写，不记录密码/令牌 |
| 第二学生 S2 | 待填写，不记录密码/令牌 |
| 教师账号 T1 | 待填写，不记录密码/令牌 |
| 课程 | 待填写 |

## 4. 教师端复用门禁

| ID | 验收项 | 通过标准 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| REUSE-01 | Agent 内核 | student/teacher 使用同一 request normalizer、contract、plan compiler、ReAct 和 verifier | 待验收 | 待填写 |
| REUSE-02 | 资源生成器 | 没有新增学生专用报告/PPT/导图/习题/课堂/闪卡/小游戏生成器 | 待验收 | 待填写 |
| REUSE-03 | RAG/Web | 两角色调用同一检索服务，只通过授权 scope 区分来源 | 待验收 | 待填写 |
| REUSE-04 | 前端工作区 | AIWorkspace、SourcePanel、ChatPanel、StudioPanel 共享业务实现 | 待验收 | 待填写 |
| REUSE-05 | 预览与任务 | Job、任务中心、资源预览和课堂播放器共享 | 待验收 | 待填写 |
| REUSE-06 | 复用台账 | 每个 Task 有教师端检索与复用结论 | 待验收 | 待填写 |
| REUSE-07 | 教师回归 | 共享修改后教师核心自动化和真实流程无新增失败 | 待验收 | 待填写 |

失败条件：出现 StudentPlanner、StudentExecutor、StudentRAG 或重复生成器且没有无法复用的书面证据，本阶段直接不通过。

## 5. 已知问题关闭矩阵

| 问题 | 级别 | 必须达到的关闭条件 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| STU-E2E-001 个人索引失败/错误覆盖 | P0 | 真实上传 ready、chunk > 0、唯一事实可检索；故障注入保留具体错误 | 待验收 | 待填写 |
| STU-E2E-002 深度研究进入旧存储 | P0 | 研究结果全部进入发起人个人知识库并可管理/检索 | 待验收 | 待填写 |
| STU-E2E-003 课程 RAG 命中个人资料 | P0 | 课程、个人、组合三种范围 100% 正确 | 待验收 | 待填写 |
| STU-E2E-004 StudentShell 更新循环 | P1 | 控制台无 Maximum update depth；无周期性重复请求 | 待验收 | 待填写 |
| STU-E2E-005 RAG 开关竞争 | P1 | 点击开关立即发送，服务端 capability 仍正确 | 待验收 | 待填写 |
| STU-E2E-006 Agent 计划不收口 | P1 | result/done 后计划、工具和任务均为终态 | 待验收 | 待填写 |
| STU-E2E-007 研究 UI 无完成态 | P1 | 展示阶段、来源、失败项、归档和索引状态 | 待验收 | 待填写 |
| STU-E2E-008 来源质量/降级不可见 | P1 | 来源约束有 succeeded/partial/failed，降级可见 | 待验收 | 待填写 |
| STU-E2E-009 课程知识显示上传 | P1 | 学生课程标签无上传/写操作，个人标签可上传 | 待验收 | 待填写 |
| STU-E2E-010 引用重复/无关 | P2 | 引用去重并通过最低相关性门槛 | 待验收 | 待填写 |
| STU-E2E-011 瞬时 fetch 失败 | P2 | 稳定重复 20 次无偶发失败；失败时可恢复 | 待验收 | 待填写 |

## 6. 自动化验收

### 6.1 后端目标回归

应覆盖：

- 个人知识生命周期与 owner 隔离；
- durable 索引任务错误保真；
- 深度研究个人归档与 batch owner；
- 课程/个人/组合 RAG scope；
- authenticated actor role；
- Fast/Agent Persona；
- 学生工具目录与资源私有性；
- 教师 Agent 全套目标回归。

建议命令在实施后按实际文件调整并记录输出：

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest `
  api/src/tests/services/test_personal_knowledge_service.py `
  api/src/tests/services/test_personal_knowledge_index_lifecycle.py `
  api/src/tests/test_personal_knowledge_api.py `
  api/src/tests/chat/test_deepsearch_service_websearch.py `
  api/src/tests/chat/test_deepsearch_personal_archive.py `
  api/src/tests/chat/test_rag_access_scope.py `
  api/src/tests/chat/runtime/test_student_rag_scope.py `
  api/src/tests/chat/runtime/test_authenticated_actor_role.py `
  api/src/tests/chat/runtime/test_persona_policy.py `
  api/src/tests/chat/runtime/test_student_guided_dialogue.py `
  api/src/tests/chat/test_personal_generation_authorization.py `
  api/src/tests/services/test_personal_tool_access.py -q
```

| ID | 测试集 | 目标 | 实际 | 结果 |
| --- | --- | --- | --- | --- |
| AUTO-BE-01 | 学生知识与 Persona 目标回归 | 0 failed | 待填写 | 待验收 |
| AUTO-BE-02 | 教师 Agent/runtime 目标回归 | 0 failed | 待填写 | 待验收 |
| AUTO-BE-03 | 后端全量 | 0 unexpected failed | 待填写 | 待验收 |
| AUTO-BE-04 | Python compile | 0 error | 待填写 | 待验收 |

### 6.2 前端目标回归

至少覆盖：

- StudentShell 课程同步稳定性；
- RAG toggle + immediate send；
- Agent result/done/error 状态收口；
- SourcePanel 角色与 tab 权限；
- 深度研究多阶段状态；
- 学生/教师工具目录；
- 共享 AIWorkspace 的 teacher/student 回归；
- 课程知识只读、资源和课堂空间。

```powershell
npm test
npm run build
npx playwright test tests/e2e/student-guided-agent.spec.ts
```

| ID | 测试集 | 目标 | 实际 | 结果 |
| --- | --- | --- | --- | --- |
| AUTO-FE-01 | 前端单元/组件 | 0 failed | 待填写 | 待验收 |
| AUTO-FE-02 | 生产构建 | 成功 | 待填写 | 待验收 |
| AUTO-FE-03 | 学生共享页面 E2E | 全通过 | 待填写 | 待验收 |
| AUTO-FE-04 | 教师页面回归 E2E | 全通过 | 待填写 | 待验收 |
| AUTO-FE-05 | 控制台检查 | 0 app error / 0 React loop | 待填写 | 待验收 |

## 7. 学生 Persona 与 Agent 智能验收

### 7.1 角色贯通

| ID | 场景 | 期望 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| ROLE-01 | student 调 Fast Chat | 使用学生 Persona，不出现教师备课语气 | 待验收 | 待填写 |
| ROLE-02 | student 调 ReAct | 合同 actor_role=student，最终回答为引导式 | 待验收 | 待填写 |
| ROLE-03 | teacher 调 Fast/ReAct | 保持教师备课 Persona | 待验收 | 待填写 |
| ROLE-04 | 客户端伪造 teacher | 服务端忽略/拒绝，仍按 token student | 待验收 | 待填写 |
| ROLE-05 | 同一工具任务双角色 | 工具计划相同，Persona 和工具权限按角色不同 | 待验收 | 待填写 |

### 7.2 引导式教学行为

| ID | 场景 | 期望 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| GUIDE-01 | 解释概念 | 先给清晰结论、解释和例子；最多一个检查点 | 待验收 | 待填写 |
| GUIDE-02 | 学生请求解题提示 | 给有效第一层提示，不直接倾倒完整答案 | 待验收 | 待填写 |
| GUIDE-03 | 学生尝试错误 | 指出具体冲突并升级提示，不泛泛说“再想想” | 待验收 | 待填写 |
| GUIDE-04 | 学生明确要完整解法 | 直接给完整解法和关键解释，不继续阻塞 | 待验收 | 待填写 |
| GUIDE-05 | “考考我” | 一次给一项检查并根据回答反馈 | 待验收 | 待填写 |
| GUIDE-06 | 明确生成闪卡 | 直接执行任务，不问学生是否理解概念 | 待验收 | 待填写 |
| GUIDE-07 | 证据不足 | 说明知识库边界，不伪造引用 | 待验收 | 待填写 |
| GUIDE-08 | 30 轮混合对话 | 任务、来源和提示等级不串线 | 待验收 | 待填写 |

### 7.3 版本化评测门槛

| 指标 | 门槛 | 实际 | 结果 |
| --- | ---: | ---: | --- |
| 数据集用例数 | ≥ 60 | 待填写 | 待验收 |
| 学生 Persona 合规率 | ≥ 95% | 待填写 | 待验收 |
| 有效提示率 | ≥ 95% | 待填写 | 待验收 |
| 明确完整答案满足率 | ≥ 95% | 待填写 | 待验收 |
| 多余反问率 | ≤ 5% | 待填写 | 待验收 |
| 清晰资源任务无谓追问率 | ≤ 5% | 待填写 | 待验收 |
| 必需工具召回率 | 100% | 待填写 | 待验收 |
| 禁止工具调用率 | 0% | 待填写 | 待验收 |
| 知识范围正确率 | 100% | 待填写 | 待验收 |
| 引用域标注正确率 | 100% | 待填写 | 待验收 |
| 30 轮绑定准确率 | 100% | 待填写 | 待验收 |
| 五次重复合规率 | ≥ 98% | 待填写 | 待验收 |
| 双 Provider 核心通过率 | ≥ 95% | 待填写 | 待验收 |

## 8. 真实个人知识库验收

测试资料继续使用：`tests/fixtures/student-e2e-personal-knowledge-20260810.md`。

| ID | 操作 | 通过标准 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| PKB-01 | S1 上传唯一事实文档 | received→ready，chunk_count > 0 | 待验收 | document/job/耗时 |
| PKB-02 | 查看元数据 | personal scope、owner=S1、course 仅为 provenance | 待验收 | 元数据摘要 |
| PKB-03 | 个人 RAG 提问 | 返回 `E2E-STUDENT-20260810-RAG-ALPHA` 和唯一短语 | 待验收 | conversation/source |
| PKB-04 | T1/S2 直接访问 | 404/403，不能预览、下载、检索 | 待验收 | 状态码 |
| PKB-05 | 注入索引失败 | 文档 failed，具体错误不被通用错误覆盖 | 待验收 | job/error code |
| PKB-06 | 重试 | 同一文档新 attempt 成功，不复制文档 | 待验收 | attempt/job |
| PKB-07 | 删除 | 个人列表和索引删除，课程数据不变 | 待验收 | 前后计数 |

## 9. 真实深度研究验收

统一问题建议：

```text
比较 Python 官方资料中 list 与 tuple 的可变性、性能和适用场景，
至少给出 3 个可访问来源，其中至少 1 个为 Python 官方来源。
```

| ID | 验收项 | 通过标准 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| DEEP-01 | 搜索/抽取 | 展示实际阶段、成功/失败来源 | 待验收 | batch/耗时 |
| DEEP-02 | 来源约束 | 达标为 succeeded；不达标明确 partial | 待验收 | 来源列表 |
| DEEP-03 | 个人归档 | 结果进入 S1 新个人知识库，有 document/job ID | 待验收 | 文档/任务 |
| DEEP-04 | 个人 RAG 复用 | 后续对话能引用研究文档 | 待验收 | conversation/source |
| DEEP-05 | 范围隔离 | 研究文档不进入课程知识、课程 RAG 或课程共享 | 待验收 | 检索/计数 |
| DEEP-06 | owner 隔离 | T1/S2 不能通过 batch/document ID 读取 | 待验收 | 状态码 |
| DEEP-07 | Provider 降级 | rerank/抽取降级在 UI/结果中可见 | 待验收 | trace/result |
| DEEP-08 | 完成态 | 完成后关闭不提示取消，可进入个人知识库 | 待验收 | 浏览器记录 |

## 10. 真实 RAG 与 Agent 工具验收

### 10.1 知识范围

| ID | 模式 | 通过标准 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| RAG-01 | `course_auto` | 只返回当前课程发布知识 | 待验收 | source scopes |
| RAG-02 | `personal_auto` | 只返回 S1 个人知识 | 待验收 | source scopes |
| RAG-03 | selected 组合 | 只返回显式选择且有权的课程+个人文档 | 待验收 | source IDs |
| RAG-04 | `none` | 不调用 RAG、不引用知识库 | 待验收 | tool trace |
| RAG-05 | 无相关证据 | 明确资料不足，无无关引用 | 待验收 | response |
| RAG-06 | 无 scope 旧文档 | 不参与任何 auto 检索 | 待验收 | negative trace |
| RAG-07 | 跨用户/跨课程 ID | 拒绝，不泄露存在性和内容 | 待验收 | 状态/trace |
| RAG-08 | 引用去重 | 同一文档/URL 不重复占多个引用编号 | 待验收 | citations |

### 10.2 工具矩阵

| ID | 场景 | 必需工具 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| AGENT-01 | 普通学习问答 | 无 | 待验收 | conversation/trace |
| AGENT-02 | 课程 RAG | `rag_search` | 待验收 | trace/source |
| AGENT-03 | 个人 RAG | `rag_search` | 待验收 | trace/source |
| AGENT-04 | Web | `web_search` | 待验收 | trace/source |
| AGENT-05 | RAG + Web | `rag_search`,`web_search` | 待验收 | trace/source |
| AGENT-06 | 状态查询 | 只读任务工具，不生成 | 待验收 | trace |
| AGENT-07 | 取消 | 只取消有权任务，不重复提交 | 待验收 | job state |
| AGENT-08 | 重载/重启恢复 | 合同、计划、Job 和最终材料可恢复 | 待验收 | before/after |

## 11. 真实资源生成与权限回归

大部分生成能力已经完成，本阶段采用风险导向回归：共享生成器未修改时，不重复执行所有高成本类型；至少覆盖一个通用资源和学生特有资源。

| ID | 场景 | 通过标准 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| GEN-01 | 页面生成闪卡 | Job succeeded、材料可预览、private | 待验收 | job/material |
| GEN-02 | Agent 生成小游戏 | 正确工具、Job succeeded、private | 待验收 | trace/job/material |
| GEN-03 | 生成通用资源 | 从报告/PPT/导图/习题选一个代表性真实用例 | 待验收 | job/material |
| GEN-04 | AI课堂入口/权限 | 可创建个人课堂或复用既有真实证据；不进入课程 | 待验收 | job/material |
| GEN-05 | 学生教案/博客 | 页面无入口，接口 403 | 待验收 | catalog/status |
| GEN-06 | 教师查看学生资源 | 教师 mine/course 均不可见 | 待验收 | count/IDs |
| GEN-07 | 课程共享计数 | 学生生成前后不变 | 待验收 | before/after |
| GEN-08 | 幂等 | 重连/重复确认不产生第二份资源 | 待验收 | job/material IDs |

## 12. 前端真实浏览器验收

使用真实服务和真实页面验证：

- [ ] 学生登录后导航与课程上下文正确；
- [ ] 点击课程先进入课程详情；
- [ ] AI 问答复用教师三栏能力，但学生语气与权限正确；
- [ ] RAG 开关点击后立即发送仍生效；
- [ ] 课程知识只读且没有上传/修改/重建；
- [ ] 个人知识可以上传、查看状态、重试和删除；
- [ ] 深度研究展示四阶段和最终个人归档；
- [ ] Agent 最终答案出现时计划同步完成；
- [ ] AI课堂可进入、播放和查看个人/课程空间；
- [ ] 资源管理可进入并区分我的资源/课程共享；
- [ ] 个人中心可进入；
- [ ] 控制台无 React 更新循环和应用错误；
- [ ] 页面重载后课程、会话和任务状态正确恢复。

视口至少覆盖：1024×768、1366×768、1440×900、1920×1080。

| ID | 视口/流程 | 实际结果 | 证据 |
| --- | --- | --- | --- |
| UI-01 | 1024 紧凑模式 | 待填写 | 待填写 |
| UI-02 | 1366 主验收 | 待填写 | 待填写 |
| UI-03 | 1440 主验收 | 待填写 | 待填写 |
| UI-04 | 1920 宽屏 | 待填写 | 待填写 |
| UI-05 | 键盘与焦点 | 待填写 | 待填写 |

## 13. 性能与稳定性

| 指标 | 门槛 | 实际 | 结果 |
| --- | ---: | ---: | --- |
| 首个状态事件 P95 | ≤ 2 秒 | 待填写 | 待验收 |
| 契约/计划形成 P95 | ≤ 10 秒 | 待填写 | 待验收 |
| 本地 Markdown 个人索引 | ≤ 30 秒 | 待填写 | 待验收 |
| Fast 无工具问答 P95 | 记录基线且无明显倒退 | 待填写 | 待验收 |
| RAG 编排额外耗时 | 与检索/模型分别记录 | 待填写 | 待验收 |
| 20 次学生页面重载 | 0 React loop / 0 偶发应用错误 | 待填写 | 待验收 |
| 同一关键用例 5 次 | ≥ 98% 合规 | 待填写 | 待验收 |
| 重复成功生成 | 0 | 待填写 | 待验收 |

外部深度研究和模型耗时单独统计，不与 Agent 编排耗时混合。

## 14. 教师端回归

| ID | 教师流程 | 通过标准 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| TREG-01 | Fast 普通问答 | 备课助手语气，不出现学生式反问 | 待验收 | 待填写 |
| TREG-02 | RAG/Web/组合 | 工具与来源正确 | 待验收 | 待填写 |
| TREG-03 | 资源生成 | 代表性 Job/材料成功 | 待验收 | 待填写 |
| TREG-04 | 材料包/确认 | 现有计划、确认和幂等不变 | 待验收 | 待填写 |
| TREG-05 | 深度研究 | 进入教师个人知识库，不自动进课程 | 待验收 | 待填写 |
| TREG-06 | 课程知识管理 | 教师写操作仍可用 | 待验收 | 待填写 |
| TREG-07 | 资源发布 | 教师个人到课程快照仍可用 | 待验收 | 待填写 |
| TREG-08 | 教师版本化评测 | 不低于既有门槛 | 待验收 | 待填写 |

## 15. 测试数据与清理

验收记录必须列出：

```text
personal_document_ids
deepsearch_batch_ids
index_job_ids
conversation_ids
agent_trace_ids
generation_job_ids
material_ids
course shared counts before/after
```

验收结束后：

- 删除可安全删除的学生个人测试文档和资源；
- 删除测试账号或恢复其课程成员关系；
- 不删除用于证明课程快照的用户真实资料；
- 不提交运行时生成的 index、Job、材料、缓存或日志；
- 如需保留复现数据，在本节记录 owner、用途和计划清理日期。

## 16. 最终发布签字

以下全部满足才可将状态改为 Accepted：

- [ ] STU-E2E-001—009 全部关闭；
- [ ] STU-E2E-010—011 无发布风险或已关闭；
- [ ] 教师端复用门禁全部通过；
- [ ] 个人知识、深度研究和 RAG 范围真实 E2E 全部通过；
- [ ] Fast/Agent 学生 Persona 全部通过；
- [ ] 版本化评测、五次重复、双 Provider 和 30 轮对话达标；
- [ ] 代表性资源生成和私有性通过；
- [ ] 前端真实浏览器和控制台检查通过；
- [ ] 教师端自动化与真实回归通过；
- [ ] 没有新增重复 Agent/生成器或权限旁路；
- [ ] 验收证据包含真实文档、来源、trace、Job、材料和耗时；
- [ ] 测试数据已清理或明确登记保留。

最终结论：**待填写**

验收人：**待填写**

验收时间：**待填写**
未通过项与后续安排：**待填写**
