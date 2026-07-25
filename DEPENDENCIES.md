# Edu-AI 依赖与安装

更新日期：2026-07-25

迁移完成后的主应用只需要三组运行时：React 前端、FastAPI 后端和仓库内的 OpenMAIC packages。课程 PPTX 与视频均由 AI 课堂链路导出，不需要额外的课件或数字人服务。

## 系统要求

| 依赖 | 建议版本 | 用途 |
| --- | --- | --- |
| Python | 3.12 | FastAPI、RAG、媒体处理 |
| Node.js / npm | 20 / 10 | 前端与仓库内 OpenMAIC packages |
| FFmpeg / ffprobe | 6+ | AI 课堂 MP4、音频与字幕合成 |
| Chromium | 当前稳定版 | Playwright 课堂渲染 |

## 一键安装

Windows：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\scripts\install-all.ps1
```

Linux / macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
bash scripts/install-all.sh
```

安装器会：

1. 安装 `Edu_AI/api/src/requirements-media.txt`；
2. 安装 `Edu_AI/package-lock.json` 锁定的前端依赖；
3. 安装 Playwright Chromium；
4. 可选安装 `EduAgent`；
5. 在本地配置不存在时复制 `.env.example`。

可用跳过参数：`SkipPython`、`SkipNode`、`SkipOptional`、`SkipPlaywrightBrowsers`、`SkipEnvFiles`。bash 版本使用对应的 `--skip-*` 参数。

## 配置

前端配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

后端视频导出配置：

```env
OPENMAIC_BASE_URL=http://localhost:3000
CLASSROOM_VIDEO_FRONTEND_URL=http://127.0.0.1:4173
CLASSROOM_VIDEO_NODE=node
CLASSROOM_VIDEO_FFMPEG=ffmpeg
```

模型、Embedding、搜索与语音识别配置见 `Edu_AI/api/src/.env.example`。真实密钥只写入本机 `.env`，不要提交。

## 启动

Windows 可执行：

```powershell
Edu_AI\api\src\start_api.bat
```

也可以分别启动：

```bash
cd Edu_AI/api/src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

cd Edu_AI
npm run dev
```

## 验证

```bash
python -m pip check
npm test --prefix Edu_AI
npm run build --prefix Edu_AI
```

视频导出还需要确认 `ffmpeg -version`、`ffprobe -version` 和 Playwright Chromium 可用。

## 不应提交

不要提交 `.env`、虚拟环境、`node_modules/`、`dist/`、运行缓存、课程生成物、视频成品或真实密钥。
