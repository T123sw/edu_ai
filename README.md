# Edu-AI

Edu-AI 是由 React/Vite 前端、FastAPI 后端和 OpenMAIC sidecar 组成的 AI 教学平台。当前结构与模块状态见 [`项目总览地图.md`](项目总览地图.md)。

```text
Edu_AI/
├── frontend/          # React/Vite 前端
├── backend/           # FastAPI、迁移与后端测试
├── openmaic-sidecar/  # OpenMAIC 课堂生成服务
├── deploy/            # PostgreSQL、systemd 与 Nginx 配置
├── scripts/           # 安装、迁移与诊断脚本
└── docs/              # 架构、规格、验收和部署文档
```

## 支持的产品主线

教师使用课程资料、RAG、知识图谱和检索结果生成 OpenMAIC AI 课堂，并从同一份课堂数据获得互动播放、PPTX、MP4、字幕和时间线。

普通 PPT/HTML2PPT、EduAgent、旧数据采集管道、数字人和 WebRTC 不再属于支持范围。

## 本地前端

要求 Node.js 22 与 pnpm 10.28：

```bash
cd frontend
corepack enable
corepack prepare pnpm@10.28.0 --activate
pnpm install --frozen-lockfile
pnpm dev
```

默认地址：`http://127.0.0.1:5173`。

验证命令：

```bash
pnpm test
pnpm build
```

## 本地后端

```bash
cd backend/src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Python 目标版本为 3.12，正式环境使用根目录统一的 Conda 环境。旧 `start_api.*` 和 `start_simple_chat.*` 仅是待清理的历史脚本，不作为生产部署方式。

## OpenMAIC

OpenMAIC sidecar 位于仓库根目录 `openmaic-sidecar/`，默认端口 3000。PPTX 只通过 OpenMAIC 课堂导出，不依赖外部 HTML2PPT 服务。

## 文档

- [项目文档入口](docs/README.md)
- [部署入口](docs/deployment/README.md)
- [依赖与运行基线](DEPENDENCIES.md)

真实 `.env`、运行数据、依赖目录、构建产物和日志不得提交。
