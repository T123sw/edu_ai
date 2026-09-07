# Edu-AI 文档中心

最近更新：2026-09-07

本目录是项目文档的唯一入口。应用源码目录不再维护独立的 `docs/` 副本；`openmaic-sidecar/` 内的文档属于上游 vendored 项目，保持其原有结构。

## 当前文档

| 目录 | 内容 | 使用方式 |
| --- | --- | --- |
| [`spec/`](spec/README.md) | 当前产品与 OpenMAIC 主线规格 | 判断系统应当如何工作 |
| [`acceptance/`](acceptance/README.md) | 验收标准、结果和证据 | 判断功能是否达到签收条件 |
| [`deployment/`](deployment/README.md) | Linux 部署基线、服务器事实和上线待办 | 部署前唯一入口 |
| [`architecture/`](architecture/) | 数据库迁移、播放协议等长期架构契约 | 修改相关模块前阅读 |
| [`operations/`](operations/) | 数据切换、发布检查和运维清单 | 迁移、发布和故障处理时使用 |
| [`superpowers/`](superpowers/) | 仍在推进或近期完成的设计、计划和验收记录 | 开发过程追踪，不作为部署配置来源 |

## 前端体验并行实施文档

[三个 Agent 执行入口](superpowers/plans/2026-09-07-frontend-experience-parallel-handoff-cn.md)：三项设计分别配有设计、实施计划、验收文档，共九份，并明确共享文件所有权、协议交接和组合验收。A/C 已交付，B 已完成共享入口接入与分层验证；参见 [B 验收记录](superpowers/acceptance/2026-09-07-knowledge-context-acceptance-cn.md)。

最新 [A／B／C 总结验收](superpowers/acceptance/2026-09-07-frontend-experience-integration-acceptance-cn.md)：汇总各分项交付、C 旧阻塞后续修复、组合结果和剩余实现／验收缺口。

## 文档边界

近期设计记录：[前端体验优化：对话纪要与交互设计](superpowers/specs/2026-09-07-frontend-experience-conversation-design-cn.md)。涵盖首页继续按钮、课程与知识点对话上下文、Agent 修改已有资料；实现及分层验证已落地，完整端到端待验项见各验收记录。

1. 当前运行事实以源码、根目录 [`项目总览地图.md`](../项目总览地图.md) 和本目录索引为准。
2. `docs/superpowers/` 中的历史计划记录当时的实施过程，不自动代表当前部署方式。
3. 普通 PPT/HTML2PPT、EduAgent、旧数据采集管道和 SearXNG 已退出支持范围，不再保留专属文档。
4. 项目只保留 OpenMAIC 课堂数据导出的 PPTX 能力；相关规格和验收继续保留。
5. 密码、API Key、生产 `.env`、用户数据和运行日志不得写入文档或提交到 Git。

长期架构资料包括 [OpenMAIC 迁移总纲](architecture/openmaic-migration-overview.md)、[课堂统一时间线](architecture/lesson-timeline-contract.md)、[视频播放接口](architecture/video-playback-interfaces.md) 和 [数据库迁移规格](architecture/database-migration-spec.md)。

## 维护规则

- 新规格放入 `docs/spec/`，需要过程设计时放入 `docs/superpowers/specs/`。
- 验收结果放入 `docs/acceptance/`，截图等证据放在对应子目录。
- 部署文档不得复制到前端或后端目录。
- 文档引用使用仓库相对路径，不写本机盘符或旧服务器绝对路径。
