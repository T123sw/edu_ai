# 通用实验 Skill 实施计划

2026-10-15。依据[输出规范](2026-10-15-experiment-design-contract-cn.md)与[Agent 交接](2026-10-15-experiment-agent-handoff-cn.md)。本次实施通用实验设计、三阶段运行和教学证据接口；教学 Agent 的提示词、自动干预、开放回答评价另行设计。保留 MAIC-UI 原生生成；兼容已生成实验，不执行旧 v2 发布脚本。

| 顺序 | 交付 | 验证 |
| --- | --- | --- |
| 1 | 设计 Skill、Pydantic 输出模型及 JSON Schema、算法/力学/随机统计三种样例 | 引用、阶段、动作和判定校验，错误样例拒绝，Skill 检查 |
| 2 | 规格生成与修复，MAIC-UI 原生链路接入，平台生成版本/验收回执 | 模拟模型验证真实调用链、失败不发布、旧任务兼容 |
| 3 | 通用三阶段控制与生成页面适配接口 | 演示、引导、探索、错误重试、重置及状态记录 |
| 4 | 三栏页面、新协议分流、按账号保存运行、冻结教学上下文 | 版本冲突、事件去重、历史与快照、跨用户隔离 |
| 5 | 生成页面运行验收、三种样例及浏览器回归 | 桌面/手机、实际动作与反馈、类型/lint/构建 |

当前状态：五项首版代码工作已完成并上线，最终发布状态见验收记录，验证与边界见下文，不将示例通过称为任意生成实验可靠。

实现约定：首版从设计规范收敛到可执行字段，生成模型只填写内容规格；平台填写标识、摘要和验收信息。通用规则处理字段比较/容差/集合等任务，复杂模拟由生成的沙箱适配器执行，不新增主题分支。完整语义记录可用于未来教学，生成代码上报不冒充独立科学认证。

新请求显式使用 edu-experiment/1，已有队列缺少协议时维持旧入口。部署单独记录，测试与构建产物使用隔离目录。

## 本轮实施结果

五项代码工作已完成，源码未部署。实际实现与最初概念规范的对应如下：

| 工作 | 实现入口 | 状态 |
| --- | --- | --- |
| 输出规范与 Skill | `backend/src/app/practice/experiment/contracts.py`；`practice/skills/design-experiment/` | 已实现，模型加载 Skill、输出约定和实时 JSON Schema；规格错误允许修复一次 |
| MAIC-UI 接入 | `experiment/generation.py`；`practice/native.py`、`native_runtime.py` | 复用原生 ScientificEngine / HeavyGenerator / PostProcessor；实验适配器由生成 HTML 提供，没有生产主题分支 |
| 通用运行与反馈 | `frontend/src/practice/experiment/model.ts`、`runtime.ts` | 三阶段权限、自动判定、显式提交、错误重试、回看/重播、自由探索、状态缺失 unknown、开放评价 awaiting_review |
| 页面与保存 | `experiment/Experiment.tsx`；`experiment/repository.py`；`api/practice.py` | 三栏与手机面板、手机就地反馈、账号隔离、本地草稿、服务端追加保存、幂等/并发冲突、导出、新一轮 |
| 教学接入准备 | `experiment/teaching.py`；`self_learning/skills/teach-experiment/README.md` | 冻结提问与完整语义历史、五个只读工具、迟到响应绑定检查；尚无教学 SKILL.md 或模型调用 |

产物中的 `experiment.spec` 是本轮可执行规格；`revision` 是规范化规格摘要，`runtime` 是运行器源码摘要，原生仓库固定版本及运行验收结果由平台追加。HTML 同时保存可追溯原稿和已包装的沙箱副本。概念规范中的独立 adapter 文件在首版收敛为 HTML 内 `EduExperiment.register({apply, render})`，状态和控制权由宿主 SDK 管理。

新请求显式带 `edu-experiment/1`；已有资源和没有该协议的旧队列维持原路径。新协议不会调用旧 `/ask`，以免把只读取少量旧观察的问答当作新的教学 Agent。

## 已实现的 HTTP 对接

共同前缀：`/api/practice/{identifier}/experiment`。所有接口先校验当前用户拥有且实验已生成成功。

- `GET /runs/latest`：恢复最近运行。
- `POST /runs`：提交完整追加记录，包含 `expected_seq` 和 `view`；重复相同内容幂等，改写旧事件/快照或并发覆盖返回 409。
- `GET /runs/{run_id}`：读取指定运行。
- `POST /runs/{run_id}/teaching-context`：携带问题及 `expected_seq`，冻结背景、当前状态、全部本轮事件与快照；状态变化时返回 409。
- `GET /teaching-context/{context_id}`：读取被冻结的问题与证据。
- `POST /teaching-context/{context_id}/evidence`：`get_design`、`get_snapshot`、`list_events`、`get_attempt`、`compare_snapshots` 五种只读工具。分页保留完整原始事件，不用摘要替代历史。

上下文同时保留当前任务和最近操作/反馈/提交的引用，避免“正确后自动进入下一任务”导致上一操作的解释失去指向。未来教学回答必须带 `context_id/revision/run_id/state_revision/attempt_id`；本轮不注册回答服务，也不开放模型修改进度。

## 验证与边界

验证记录见 `docs/acceptance/2026-10-15-experiment-skill/README.md`。算法、力学和随机统计是协议验收样例，不是完整课程，不会根据用户主题选择这些样板。真实浏览器执行成功/失败动作、演示重放、探索、DPR 与缩放检查；原生生成链路使用真实上游代码与模拟模型回复测试。

尚未进行真实模型端到端生成或批量成功率测试，也未重启/发布生产服务。浏览器生成代码的状态统一标记 `browser_reported`，运行验收不等同科学认证。开放评价当前只能位于最后一个任务，显示待评价并允许探索；实际教学回答、模型评价提交、历史摘要装配、课堂知识点会话接入属于后续教学 Skill 工作。

首版每轮最多 2000 条语义事件、约 1.5MB 运行记录，单个状态不超过 50000 字符。达到上限会明确停止追加并提示保存后新开一轮，不截断历史。首版以完整快照实现恢复与交接；更大实验的分块事件存储和长期历史检索留待后续扩展。数据库保存复用已有 app_state，无新增迁移；PostgreSQL 多进程锁已实现，当前自动测试覆盖 JSON 和 SQLite 持久化路径，未在生产 PostgreSQL 执行并发压测。
