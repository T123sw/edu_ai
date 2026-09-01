# Edu-AI 依赖与运行基线

更新日期：2026-09-01

本文记录项目重构和 Linux 部署采用的唯一环境基线。具体服务器事实与上线待办见 [`docs/deployment/`](docs/deployment/README.md)。

## 支持的运行组件

- React/Vite 前端；
- FastAPI 后端；
- PostgreSQL；
- OpenMAIC sidecar；
- Playwright Chromium 与 FFmpeg 视频导出。

不安装 EduAgent、旧数据采集管道、SearXNG、HTML2PPT、普通 PPT 服务、数字人或 WebRTC 组件。

## 版本基线

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| Miniforge/Conda | 当前稳定版 | Python 与系统库环境管理 |
| Python | 3.12 | FastAPI、RAG、媒体处理 |
| Node.js | 22 | 前端、OpenMAIC 和视频脚本 |
| pnpm | 10.28 | 唯一 Node 包管理器 |
| FFmpeg/ffprobe | 6+ | MP4、音频、字幕和媒体探测 |
| PostgreSQL | 14+ | 生产数据库 |
| Chromium | 与 Playwright 匹配 | 课堂渲染与视频导出 |

## 依赖文件

- 根目录 `environment.yml`：唯一 Conda 环境定义。
- 后端 `requirements.txt`、`requirements-lock.txt`、`requirements-media.txt`：Python 依赖来源。
- 前端和 sidecar 的 `pnpm-lock.yaml`：Node 依赖锁文件。
- `.env.example`：配置字段模板，不包含真实密钥。

项目不再使用 `package-lock.json`、应用目录内重复的 `environment.yml` 或生产 venv 安装说明。

## 统一端口

| 端口 | 服务 | 暴露方式 |
| --- | --- | --- |
| 3000 | OpenMAIC sidecar | 仅内部访问 |
| 5432 | PostgreSQL | 仅内部访问 |
| 8001 | FastAPI | 由 Nginx 代理 |
| 5173 | Vite 开发服务器 | 仅本地开发 |

## 包管理规则

```bash
bash scripts/install-all.sh
conda activate edu-ai
```

前端、sidecar 和仓库内 OpenMAIC packages 均使用 pnpm。安装脚本先构建 sidecar 工作区依赖，再安装前端文件依赖；旧的 npm、批处理启动器和 Docker 数据库入口已删除。

## 运行数据

代码与运行数据必须分离。Linux 目标数据根目录为 `/data/edu_ai/`，用于保存课程、上传、模型、缓存、日志和备份。以下内容不得提交：

- `.env` 和密钥；
- Conda 环境、虚拟环境和 `node_modules/`；
- `dist/`、`.next/`、测试输出和缓存；
- 用户数据、课程生成物、向量库、模型和日志。
