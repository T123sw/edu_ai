# OpenMAIC 迁移规格索引

最近更新：2026-08-12

状态：Phase 0–6 与 AI 课堂实时问答已完成；连续授课与常驻问答体验优化、课程知识库可配置图谱先行构建待实施

本目录规定迁移后的接口、数据和运行时约束；验收证据见 [`../acceptance/`](../acceptance/README.md)。

| 规格 | 主题 | Phase | 状态 |
| --- | --- | --- | --- |
| SPEC-00 | Web 检索层 | 1.5 前置 | 已纳入主线 |
| SPEC-01 | Sidecar 裁剪与部署 | 0 | 完成 |
| SPEC-02 | Stage/Scene/Action/Slide 数据契约 | 全阶段 | 完成 |
| SPEC-03 | ParsePDF 解析迁移 | 1 | 完成 |
| SPEC-04 | GenerateClassroom 课件生成与注入 | 2 | 完成 |
| SPEC-05 | 异步任务协议 | 横切 | 完成 |
| SPEC-06 | Provider 配置与 BYOK 安全边界 | 横切 | 完成 |
| SPEC-07 | OpenMaicClient Python 客户端 | 横切 | 完成 |
| SPEC-08 | 前端 DSL/Renderer 播放 | 3 | 完成 |
| SPEC-09 | PPTX 导出 | 4 | 完成 |
| SPEC-10 | 视频 A 导出 | 5 | 完成 |
| [SPEC-11](SPEC-11_旧模块下线.md) | 旧模块下线 | 6 | 完成 |
| [SPEC-12](SPEC-12_AI课堂实时问答与中断恢复.md) | AI 课堂实时问答与中断恢复 | 产品增量 | 完成，ACC-12 通过 |
| [SPEC-13](SPEC-13_AI课堂连续授课与常驻问答体验优化.md) | AI 课堂连续授课与常驻问答体验优化 | 产品增量 | 设计已确认，待实施 |
| [SPEC-14](SPEC-14_课程知识库可配置图谱先行构建.md) | 课程知识库可配置、图谱先行构建 | 产品增量 | 已实施，核心真实 E2E 通过；扩展场景待签收 |

## 全局约束

1. `@openmaic/dsl` 是 Stage/Scene/Action/Slide 的事实源。
2. scene、action、element、clip id 在编辑和导出过程中保持稳定。
3. 长任务使用统一 job/poll 协议。
4. AI 课堂、PPTX 和 MP4 消费同源课堂数据与 LessonTimeline。
5. 主运行时只保留 OpenMAIC 课堂路径；历史设计文档不构成部署依赖。
6. 数字人/唇形同步不属于当前产品范围。

可选视频 B（确定性逐帧渲染）按产品需求单独立项，不影响 Phase 0–6 完成状态。
