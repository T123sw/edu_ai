# 架构文档

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
