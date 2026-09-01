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

## 安装环境

项目只使用根目录 `environment.yml`。安装 Miniforge 后，在 Linux 执行：

```bash
bash scripts/install-all.sh
conda activate edu-ai
```

该环境统一提供 Python 3.12、Node.js 22、pnpm 10.28 和 FFmpeg/ffprobe 6+，并安装前端、后端、OpenMAIC 与 Playwright 依赖。真实配置只保存在根目录 `.env`；首次安装会根据 `.env.example` 创建它。

## 本地开发

先把 `.env.example` 复制为 `.env`，并将 `VITE_API_BASE_URL` 临时改为 `http://127.0.0.1:8001`。分别启动：

```bash
cd backend/src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

cd ../../openmaic-sidecar
pnpm dev --hostname 127.0.0.1 --port 3000

cd ../frontend
pnpm dev
```

前端默认地址为 `http://127.0.0.1:5173`。

### Windows 一键启动

完成依赖安装并准备好根目录 `.env` 后，可在项目根目录执行：

```bat
start.bat --check
start.bat
stop.bat
```

`start.bat` 会分别打开 OpenMAIC、FastAPI 和 Vite 三个可见终端，使用端口 `3000`、`8001` 和 `5173`。环境或端口检查失败时不会启动部分服务，也不会自动安装依赖或结束占用端口的未知程序。`stop.bat` 只停止由本次启动记录管理的进程。

Windows 本地开发支持 Node.js 22 或更新版本；Linux 正式部署仍以 `environment.yml` 固定的 Node.js 22 为准。

验证命令：

```bash
pnpm test
pnpm build
```

## OpenMAIC

OpenMAIC sidecar 位于仓库根目录 `openmaic-sidecar/`，默认端口 3000。PPTX 只通过 OpenMAIC 课堂导出，不依赖外部 HTML2PPT 服务。

## 文档

- [项目文档入口](docs/README.md)
- [部署入口](docs/deployment/README.md)
- [依赖与运行基线](DEPENDENCIES.md)

Linux 正式上线按 [部署入口](docs/deployment/README.md) 执行。生产端口为 FastAPI `8001`、OpenMAIC `3000`、PostgreSQL `5432`，三者都只监听本机，由 Nginx 提供公开入口。

真实 `.env`、运行数据、依赖目录、构建产物和日志不得提交。
