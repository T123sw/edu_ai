# Edu-AI 部署依赖文件说明

本文档汇总当前仓库中应作为部署依据的依赖文件，并说明哪些目录属于本地运行产物，不应提交到远程仓库。

## 前端

- `Edu_AI/package.json`
  - Vite + React 前端工程的主依赖清单。
  - 主要运行依赖包括 `react`、`react-dom`、`antd`、`@antv/g6`、`react-markdown`、`katex`、`zustand`。
  - 主要开发依赖包括 `vite`、`typescript`、`eslint`、`tailwindcss`、`@vitejs/plugin-react-swc`。
- `Edu_AI/package-lock.json`
  - 锁定前端依赖版本，部署和 CI 应优先使用 `npm ci` 或在锁文件可信时使用 `npm install`。

常用命令：

```bash
cd Edu_AI
npm install
npm run build
```

## 主后端

- `Edu_AI/api/Edu_AI/requirements.txt`
  - FastAPI 主后端依赖清单。
  - 覆盖 API 服务、鉴权、课程资料、RAG、知识图谱、报告/PPT/测验工作流、教材导入解析等能力。
  - 当前包含 `fastapi`、`uvicorn`、`pydantic`、`python-dotenv`、`baidu-aip`、`chardet`、`ffmpeg-python`、`langchain-*`、`langgraph`、`chromadb`、`PyMuPDF`、`python-docx`、`rank-bm25`、`jieba` 等。

常用命令：

```bash
cd Edu_AI/api/Edu_AI
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## AI Lecturer

- `Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/requirements.txt`
  - LiveTalking/WebRTC 实时数字人链路依赖。
  - 覆盖 WebRTC、TTS、音频处理、数字人模型推理等能力。
  - 主要依赖包括 `aiortc`、`aiohttp_cors`、`edge_tts`、`openai`、`websockets`、`librosa`、`opencv-python-headless`、`transformers`、`onnxruntime-gpu` 等。
- `Edu_AI/api/Edu_AI/AI_Lecturer/offline_video_maker.py`
  - 离线整套课程视频生成入口，依赖 Edge-TTS、Wav2Lip、FFmpeg。
  - 该链路 CPU/GPU 占用高，生产或演示环境中建议按需开启。
- `Edu_AI/api/Edu_AI/AI_Lecturer/Wav2Lip_Offline/`
  - 离线唇形同步推理代码目录。
  - 其中模型权重、临时导出视频和运行缓存不应作为普通业务数据提交。

离线链路开关：

```env
AI_LECTURER_OFFLINE_ENABLED=1
```

关闭离线整套视频生成，以保留算力给实时教学链路：

```env
AI_LECTURER_OFFLINE_ENABLED=0
```

支持的关闭值：`0`、`false`、`off`、`no`。

## 环境变量

- `Edu_AI/api/Edu_AI/.env.example`
  - 可提交的示例配置。
  - 包含 Baidu Speech、AI Lecturer 网关、离线链路开关等示例项。
- `Edu_AI/api/Edu_AI/.env`
  - 本地真实配置，可能包含密钥，应保持在 `.gitignore` 中，不提交。

常用 AI Lecturer 相关变量：

```env
AI_LECTURER_AUTOSTART=1
AI_LECTURER_OFFLINE_ENABLED=0
AI_LECTURER_GATEWAY_URL=http://127.0.0.1:8008
AI_LECTURER_LIVETALKING_URL=http://127.0.0.1:8010
AI_LECTURER_ENTRYPOINT=...
AI_LECTURER_STARTUP_TIMEOUT_SEC=15
```

## 系统级依赖

以下命令行工具需要由操作系统或运行环境提供：

- `ffmpeg`
- `ffprobe`
- PowerPoint 桌面组件，仅在需要将 PPTX 导出为图片时使用
- Chromium/Edge/Chrome，仅在 HTML deck 截图导出时使用

## 不应提交的本地运行产物

以下目录通常是本地缓存、虚拟环境、生成物或测试临时目录，不应作为依赖文件提交：

- `node_modules/`
- `dist/`
- `.venv/`、`.venv_local/`
- `.tmp_runtime/`
- `temp_export/`
- `tmp/`
- `.worktrees/`
- `course_data/**/generated_materials/`
- `html2ppt/data/`
- `html2ppt/temp-runlogs/`

如确实需要提交模型代码或资源，请只提交可复现的源码、配置和小型示例资产；大模型权重、导出视频、用户课程数据应通过外部制品仓库或部署脚本管理。
