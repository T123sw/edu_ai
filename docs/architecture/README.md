# 架构文档

## 当前开发主基线（2026-09-17）

学习 Agent 当前进展：[P2版本化事实与非聊天闭环验收](../acceptance/2026-09-17-learning-agent-p2-cn.md)已完成代码与隔离验证，业务环境尚未启用。以下设计文档中的历史阶段说明按各自编写时点理解，最新实施状态以验收记录为准。

- [课程准备 Agent 主设计](2026-09-17-course-preparation-agent-design-cn.md)：首页需求、个人配置与上传资料、全自动研究和资源准备、自检交付，以及两个 Agent 的交接契约。
- [学习辅导 Agent 主设计](2026-09-17-learning-agent-design-cn.md)：知识点独立会话、全局偏好与课程摘要、安静陪学、不聊天的学习路径、资料补充和修订衔接。

两份文档是用户已确认的后续开发方向，新增能力待实施。旧设计中与其明确冲突的产品要求由新基线替代；既有权限、存储、任务和资源版本约束继续适用。具体实施进度以对应验收记录为准。

- [课程准备 Agent 具体设计 V1](2026-09-17-course-preparation-agent-technical-design-cn.md)：细化独立运行、版本化课程清单、工具、任务恢复、质量门禁及交接 API；P1 契约与原子接收已实现，其余按阶段推进。
- [课程准备 Agent 运行核心](2026-09-17-course-preparation-agent-runtime-design-cn.md)：根角色、分层记忆/删除水位、上下文装配、完整工具目录与挂载矩阵、Skills/Harness 取舍、严格模型循环和恢复；设计已细化，开放网络研究/路径运行切片已实现，长期记忆等完整能力仍待接入。
- [课程准备 Agent 七阶段实施计划](../superpowers/plans/2026-09-17-course-preparation-agent-implementation-cn.md)：按契约存储、后台恢复、研究规划、资源制作、质量交付、首页及学习交接推进；[P1 验收](../acceptance/2026-09-17-course-preparation-agent-p1-cn.md)记录首阶段实现与验证边界。

## 既有架构契约与能力复用资料

- [学习 Agent 运行、工具与记忆设计 V1](2026-09-17-learning-agent-runtime-design-cn.md)：独立 function calling 运行器、角色提示、工具注册与契约、调用恢复、记忆读写/压缩/删除传播及验收。设计已补齐，运行层待实施，本轮未推进 P1。

学习 Agent 的下一层细化见[详细技术设计 V1](2026-09-17-learning-agent-technical-design-cn.md)和[P0—P6 分阶段实施计划](../superpowers/plans/2026-09-17-learning-agent-implementation-cn.md)：运行结构、状态与工具契约、API、并发去重、迁移及验收。P0 领域契约与状态纯函数已通过测试，尚未接运行入口，其余阶段待实施；详见[实施记录](../acceptance/2026-09-17-learning-agent-implementation-cn.md)。

本目录保存跨版本仍需遵守的架构契约：

- [Agent 读取权限与跨对话记忆约定](2026-09-08-agent-access-memory-contract-cn.md)：用户确认的权限、任务定位、记忆生命周期和读写边界；区分已实现与待办。
- [`openmaic-migration-overview.md`](openmaic-migration-overview.md)：OpenMAIC 主线与旧能力替换边界；
- [`lesson-timeline-contract.md`](lesson-timeline-contract.md)：课堂播放、音频、字幕和视频的统一时间线；
- [`video-playback-interfaces.md`](video-playback-interfaces.md)：视频上传、搜索、流式播放与前端调用接口；
- [`database-migration-spec.md`](database-migration-spec.md)：数据库迁移约束；
- [`computational-thinking-knowledge-graph.md`](computational-thinking-knowledge-graph.md)：计算思维知识图谱设计资料。

具体功能的当前行为仍以 [`../spec/`](../spec/README.md) 为准。

## DeepSeek Harness 接入设计（待实施）

- [功能拆分与代码审查](deepseek-harness-capability-decomposition-cn.md)：当前能力、复用边界、接入前准备顺序与验收条件。
- [Agent 角色与 Skills 设计](deepseek-harness-agent-skills-design-cn.md)：总入口职责、工作流选择、工具边界及现有 Skills 迁移。
- [记忆与任务状态设计](deepseek-harness-memory-design-cn.md)：长期偏好、对话历史、任务状态和业务事实的归属与恢复。

以上为目标设计，不代表当前运行时已切换到 DeepSeek Harness。

[普通对话与报告首版接入](deepseek-harness-pilot-integration-cn.md)：已实现的代码路径、启用开关、恢复方式与试点限制；附[验证记录](../acceptance/2026-09-07-deepseek-harness-report-dialogue-acceptance-cn.md)。

[知识点大纲优化计划](2026-09-07-harness-outline-optimization-plan-cn.md)：根角色、报告 Skill、搜索、内容组织与大纲质量验收。

- [根角色与报告完整流程计划](2026-09-08-reviewed-report-plan-cn.md)：正文审阅与交付门槛的实施记录。
