# Edu-AI Linux 服务器部署事实与待办

核验日期：2026-09-01

本文只记录已经确认的服务器事实和仍待确认事项，不包含可以直接执行的安装步骤。部署目标基线见 [`README.md`](README.md)。当前未在服务器安装或启动项目组件。

## 已确认事实

| 类别 | 事实 | 部署影响 |
| --- | --- | --- |
| 系统 | Ubuntu 22.04.5 LTS，x86_64，主机名 `server163` | 符合 Linux 目标平台 |
| CPU | 2 路 Intel Xeon Silver 4210R，共 20 物理核、40 逻辑 CPU | 足以运行主应用和视频任务 |
| 内存 | 250 GiB，检查时可用约 247 GiB；Swap 8 GiB | 资源充足 |
| 系统盘 | 约 1.8 TiB，可用约 1.6 TiB | 可安装代码和依赖 |
| 数据盘 | `/data` 约 3.6 TiB，可用约 3.1 TiB | 计划承载 `/data/edu_ai/` 运行数据 |
| GPU | 2 张 RTX 3090 24 GiB；驱动 535.309.01，CUDA 12.2 | 首轮远程模型部署不依赖 GPU |
| 账号 | `zxqs_ep`，属于 `sudo` 组；sudo 需要密码 | 可安装系统依赖和系统服务 |
| 用户服务 | `systemd --user` 可用，`Linger=no` | 正式部署优先使用系统级 systemd |
| 容器 | Docker 未安装 | 部署方案不依赖 Docker |
| Python | 系统 Python 3.10.12；无 Python 3.12、Conda 或 Mamba | 需要安装 Miniforge/Conda |
| Node | Node.js、npm、pnpm 均未安装 | 需要安装 Node.js 22 和 pnpm 10.28 |
| 媒体 | FFmpeg、ffprobe 未安装 | 需要安装 FFmpeg 6+ |
| 构建工具 | Git 2.34.1、curl 7.81、GCC/G++ 11.4、Make 4.3 | 具备基础下载和编译条件 |

服务器登录密码、API Key 和其他密钥不写入本文。

## 已确认的项目决策

- 仓库目标目录：`/home/zxqs_ep/Edu_AI`。
- 运行数据目标目录：`/data/edu_ai/`。
- 使用 Miniforge/Conda、Python 3.12、Node.js 22、pnpm 10.28 和 FFmpeg 6+。
- FastAPI 使用 8001，OpenMAIC 使用 3000，PostgreSQL 使用 5432。
- 普通 PPT/HTML2PPT 接口删除，只保留 OpenMAIC PPTX 导出。
- 不部署 EduAgent、旧数据采集管道、SearXNG、数字人、LiveTalking 或 WebRTC。
- 首轮使用远程模型 API；GPU 本地模型另立部署任务。
- PostgreSQL 使用 Ubuntu 系统服务，不安装 Docker。

## 仍待确认

- [ ] `zxqs_ep` 是否能够在 `/data` 下创建并长期读写 `/data/edu_ai/`。
- [ ] 学校分配的正式域名、HTTP/HTTPS 入口和 TLS 方式。
- [ ] 3000、5432、8001 的当前占用情况和防火墙策略。
- [ ] PyPI、npm registry、GitHub、模型提供方、MinerU Cloud、Bocha 和 Tavily 的网络连通性。
- [ ] 现有 Windows 用户、课程、知识库和媒体数据的迁移范围、规模与停机窗口。
- [ ] 系统时区、NTP 状态和备份保留策略。

## 执行前置条件

只有在项目目录重构、统一 `environment.yml`、安装脚本、systemd 和 Nginx 配置完成并通过本地部署检查后，才开始修改服务器。任何服务器安装、端口开放、服务创建和数据迁移都需要单独执行并记录结果。
