# 学习 Agent 分阶段实施记录

日期：2026-09-17。依据[详细设计](../architecture/2026-09-17-learning-agent-technical-design-cn.md)和[实施计划](../superpowers/plans/2026-09-17-learning-agent-implementation-cn.md)。此记录保留各阶段当时的状态；2026-09-17 全阶段实施与最终验证以[最终报告](staged-agent-implementation/final-report.md)为准。

## P0：领域契约与状态投影

已新增：

- `backend/src/app/self_learning/contracts.py`：用户内部身份、完整资源版本引用、四类阅读定位、课程视图、个人事实、独立状态与下一步动作。
- `backend/src/app/self_learning/course_reader.py`：带鉴权边界的 manifest/legacy 只读适配；节点映射保留稳定 ID；明确版本缺失不回退最新正文。
- `backend/src/app/self_learning/projections.py`：核心资料完成投影、自评独立展示、未解决问题提示及继续/回顾动作。
- `backend/src/tests/self_learning/`：上述领域行为测试。

验证命令（工作目录 `backend/src`）：

```bash
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python -m pytest tests/self_learning tests/test_self_learning.py -q
```

结果：**29 passed in 3.39s**，包含新增 23 项与既有学习服务 6 项。先执行新增测试观察到缺少待实现模块的 collection failure，完成实现后运行上面的新增与回归组合得到通过结果。

覆盖：资源类型/版本身份区分、无效版本和位置拒绝、身份字段注入拒绝、旧课程不虚构完成规则、节点重排、用户拒绝访问、旧版本读取失败、manifest 字段适配、到达文末不完成、完成不代表理解、版本间完成隔离、空核心不自动完成、自评独立、可选资料与继续动作、未解决问题不移除继续入口。

当前边界：

- 未接新 API、真实 manifest 服务和前端；读取器测试使用隔离 callback，生产级资源鉴权需由接入适配器提供。
- 未执行数据库迁移、多 worker 并发、真实模型或浏览器验收。
- 理解判断保守为 `unverified`；检查和证据充分性属于 P4，不伪造检查动作。
- 当前运行页面保持已有行为。P0 只为后续阶段提供领域代码，不宣传学习 Agent 已上线。

## 后续阶段

P1 持久化会话已完成代码与隔离环境验收，详见[P1记录](2026-09-17-learning-agent-p1-cn.md)。新路径默认关闭，未在业务库迁移或启用。P2 非聊天学习闭环、P3 上下文答疑、P4 检查与记忆、P5 准备交接、P6 整体验收仍待实施。

## P2：版本化事实与非聊天学习闭环

已实现阅读、显式完成与自评分离，事件幂等/冲突保护、保存回执、离线补发、版本核对及独立继续入口。验证证据、启用边界和下一阶段见[P2验收记录](2026-09-17-learning-agent-p2-cn.md)。业务环境未启用；下一阶段 P3。
