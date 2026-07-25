# Edu-AI 部署依赖

更新日期：2026-07-25

## 部署单元

| 单元 | 路径 | 安装 | 默认端口 |
| --- | --- | --- | --- |
| Web 前端 | `Edu_AI/` | `npm ci` | 5173 |
| FastAPI 后端 | `Edu_AI/api/src/` | `pip install -r requirements-media.txt` | 8001 |
| OpenMAIC packages | `openmaic-sidecar/` | 由前端 file dependencies 使用 | 无独立生产端口 |

AI 课堂在前端完成课件编辑与 PPTX 导出；后端的课堂导出任务使用 Playwright 与 FFmpeg 生成 MP4、SRT 和时间轴文件。

## 主机依赖

- Python 3.12
- Node.js 20 与 npm 10
- FFmpeg、ffprobe
- Playwright Chromium

Windows 和 Linux 的统一安装入口分别是仓库根目录下的 `scripts/install-all.ps1` 与 `scripts/install-all.sh`。

## 环境变量

前端：

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

后端课堂导出：

```env
OPENMAIC_BASE_URL=http://localhost:3000
CLASSROOM_VIDEO_FRONTEND_URL=http://127.0.0.1:4173
CLASSROOM_VIDEO_NODE=node
CLASSROOM_VIDEO_FFMPEG=ffmpeg
```

其余模型、Embedding、搜索和语音识别变量以 `Edu_AI/api/src/.env.example` 为准。

## 启动顺序

1. 启动 FastAPI 后端；
2. 启动前端；
3. 打开 AI 课堂进行编辑、播放或导出。

```bash
cd Edu_AI/api/src
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

cd Edu_AI
npm run dev -- --host 0.0.0.0 --port 5173
```

## 发布检查

```bash
python -m pip check
python -m pytest tests/app tests/chat -q
npm test --prefix Edu_AI
npm run lint --prefix Edu_AI
npm run build --prefix Edu_AI
```

同时检查 FFmpeg、ffprobe、Chromium，并执行一次 AI 课堂 PPTX 与 MP4 真实导出。

## 本地运行产物

以下内容不能作为部署依赖提交：`.env`、`node_modules/`、`dist/`、`.venv*`、课程生成物、视频成品、浏览器缓存和真实密钥。
