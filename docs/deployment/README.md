# Edu-AI 部署入口

最近更新：2026-09-01

当前状态：部署前仓库清理中。代码目录、systemd、Nginx 和安装脚本完成统一前，不应直接复制旧配置到服务器运行。

## 支持范围

生产部署只包含：

- React/Vite 前端；
- FastAPI 后端；
- PostgreSQL；
- OpenMAIC sidecar；
- Playwright Chromium 与 FFmpeg 视频导出链路。

不再部署 EduAgent、旧数据采集管道、SearXNG、HTML2PPT、普通 PPT 生成接口、数字人、LiveTalking 或 WebRTC 服务。

## 统一运行基线

| 项目 | 目标 |
| --- | --- |
| Linux | Ubuntu 22.04 x86_64 |
| Python | 3.12，使用 Miniforge/Conda 管理 |
| Node.js | 22 |
| pnpm | 10.28 |
| FFmpeg/ffprobe | 6+ |
| PostgreSQL | 5432，仅内部访问 |
| OpenMAIC sidecar | 3000，仅内部访问 |
| FastAPI | 8001，由 Nginx 代理 |
| 前端开发端口 | 5173，不用于正式生产 |

前端只使用 `pnpm-lock.yaml`。PPTX 只由 OpenMAIC 课堂数据导出，不依赖 46080 或外部 HTML2PPT 服务。

## 目录原则

- 仓库最终目录：Windows `D:\Edu_AI`，Linux `/home/zxqs_ep/Edu_AI`。
- 代码与运行数据分离；课程、上传、模型、缓存、日志和备份放在 `/data/edu_ai/` 下。
- 真实 `.env` 仅保存在服务器，不提交 Git。
- systemd、Nginx 和 PostgreSQL 配置统一从根目录 `deploy/` 发布。

## 当前服务器资料

- [`Linux服务器部署事实与待办.md`](Linux服务器部署事实与待办.md)：已经确认的硬件、权限和软件现状，以及仍需确认的服务器事项。
- [`运行时数据边界.md`](运行时数据边界.md)：代码仓库与用户数据、模型、缓存、日志和备份的目录边界。
- 根目录 [`DEPENDENCIES.md`](../../DEPENDENCIES.md)：项目依赖和安装基线。

在仓库重构完成前，本文只定义目标基线，不代表旧的 `Edu_AI/deploy/` 配置已经可直接上线。
