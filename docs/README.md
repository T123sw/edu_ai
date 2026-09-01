# Edu-AI 文档中心

最近更新：2026-09-01

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

## 文档边界

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
