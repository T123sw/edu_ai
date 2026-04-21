# Edu-AI 全项目依赖与一键安装说明

更新时间：2026-04-21

本文档整理当前仓库在新设备上安装、运行、配置模型与环境变量时需要的依赖。默认安装路径以仓库根目录 `D:\Edu_AI_1` 为例，Linux/macOS 请替换成自己的项目路径。

## 1. 依赖分层

| 模块 | 路径 | 安装方式 | 是否默认安装 | 说明 |
| --- | --- | --- | --- | --- |
| 前端主应用 | `Edu_AI/` | `npm ci --prefix Edu_AI` | 是 | Vite + React + Ant Design 5 |
| 后端主服务 | `Edu_AI/api/Edu_AI/` | `pip install -r requirements_api.txt` | 是 | FastAPI、RAG、PPT/视频桥接、课程存储 |
| PPT 生成服务 | `Edu_AI/api/Edu_AI/html2ppt/` | `npm ci --prefix Edu_AI/api/Edu_AI/html2ppt` | 是 | 已同步 `Sun-Jia-Jun/ppt-generation-service` 最新 `main`：`ce0ccfd` |
| PPT 导出子包 | `Edu_AI/api/Edu_AI/html2ppt/dom-to-pptx/` | `npm ci --prefix Edu_AI/api/Edu_AI/html2ppt/dom-to-pptx` | 是 | 当前版本 `1.1.6` |
| AI Lecturer 离线视频 | `Edu_AI/api/Edu_AI/AI_Lecturer/` | `pip install -r requirements-offline-py312.txt` | 可选，默认安装 | Python 3.12 兼容版，避免原始 requirements 冲突 |
| EduAgent | `EduAgent/` | `pip install -r requirements.txt` | 可选，默认安装 | Agent / 抓取辅助模块 |
| RAG standalone | `Edu_AI/api/Edu_AI/rag_v2/rag-main/` | `pip install -r requirements.txt` 或 `pip install -e .` | 可选，不默认 | 独立 RAG 实验工程，包含 `docling`、`streamlit` 等较重依赖 |
| LiveTalking GPU 栈 | `Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/` | 手动独立环境安装 | 不默认 | CUDA、`onnxruntime-gpu`、`aiortc` 等，建议单独 conda 环境 |
| 根目录 Node 包 | `package.json` | 手动可选 | 不默认 | 旧的根级实验依赖，包含 Ant Design 6；不要和主前端依赖混用 |

## 2. 系统级依赖

建议版本：

| 依赖 | 推荐版本 | 用途 |
| --- | --- | --- |
| Git | 2.40+ | 克隆、同步、提交 |
| Python | 3.12.x | 后端主服务、AI Lecturer Python 3.12 兼容依赖 |
| Node.js | 20.x | 前端、html2ppt、dom-to-pptx |
| npm | 10.x | Node 20 自带即可 |
| ffmpeg | 6.x 或系统包管理器最新版 | 视频处理、AI Lecturer、html2ppt 媒体处理 |
| Chrome / Chromium / Edge | 当前稳定版 | html2ppt 使用浏览器渲染并导出 PPT |

Windows 推荐使用 PowerShell 7 或 Anaconda Prompt。Linux/macOS 推荐使用 bash/zsh。

## 3. 一键安装

### Windows

```powershell
cd D:\Edu_AI_1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\scripts\install-all.ps1
```

常用参数：

```powershell
.\scripts\install-all.ps1 -SkipOptional
.\scripts\install-all.ps1 -SkipPlaywrightBrowsers
.\scripts\install-all.ps1 -SkipPython
.\scripts\install-all.ps1 -SkipNode
.\scripts\install-all.ps1 -Python py
.\scripts\install-all.ps1 -IncludeRagStandalone
```

### Linux / macOS

```bash
cd /path/to/Edu_AI_1
python3 -m venv .venv
source .venv/bin/activate
bash scripts/install-all.sh
```

常用参数：

```bash
bash scripts/install-all.sh --skip-optional
bash scripts/install-all.sh --skip-playwright-browsers
bash scripts/install-all.sh --skip-python
bash scripts/install-all.sh --skip-node
bash scripts/install-all.sh --python=python3.12
bash scripts/install-all.sh --include-rag-standalone
```

默认脚本会做这些事：

1. 升级 `pip`、`setuptools`、`wheel`
2. 安装后端主依赖：`Edu_AI/api/Edu_AI/requirements_api.txt`
3. 安装可选 Python 依赖：AI Lecturer 离线视频、EduAgent
4. 安装 Playwright Chromium 浏览器
5. 安装前端依赖：`Edu_AI/package-lock.json`
6. 安装 html2ppt 依赖：`html2ppt/package-lock.json`
7. 安装 dom-to-pptx 依赖：`dom-to-pptx/package-lock.json`
8. 如果本机还没有 `.env` / `config.toml`，从 example 文件复制一份

如果网络或磁盘空间有限，可以先执行：

```powershell
.\scripts\install-all.ps1 -SkipOptional -SkipPlaywrightBrowsers
```

之后再单独补：

```bash
python -m playwright install chromium
python -m pip install -r Edu_AI/api/Edu_AI/AI_Lecturer/requirements-offline-py312.txt
```

## 4. Conda 方案

根级全栈环境：

```bash
cd Edu_AI
conda env create -f environment.yml
conda activate edu-ai
npm ci
```

只建后端环境：

```bash
cd Edu_AI/api/Edu_AI
conda env create -f environment.yml
conda activate edu-ai-backend
```

Conda 文件只覆盖 Python/Node/ffmpeg 基础运行时；Node 包仍建议用各自的 `npm ci --prefix ...` 安装。

## 5. 前端依赖

路径：`Edu_AI/`

安装：

```bash
npm ci --prefix Edu_AI
```

主要依赖：

- React 18、React DOM 18、React Router 6
- Ant Design 5
- Zustand
- React Markdown、KaTeX、remark/rehype
- `@antv/g6`
- Vite 6、TypeScript 5、Tailwind CSS、ESLint

前端 env：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_AI_LECTURER_BASE_URL=http://127.0.0.1:8008
VITE_AI_LECTURER_LIVETALKING_URL=http://127.0.0.1:8010
VITE_AI_LECTURER_WEBRTC_URL=http://127.0.0.1:8010/webrtcapi.html
VITE_AI_LECTURER_OFFER_TIMEOUT_MS=15000
VITE_PPT_BASE_URL=http://127.0.0.1:46080
```

模板文件：`Edu_AI/.env.example`

## 6. 后端主服务依赖

路径：`Edu_AI/api/Edu_AI/`

安装：

```bash
python -m pip install -r Edu_AI/api/Edu_AI/requirements_api.txt
```

`requirements_api.txt` 会先引用 `requirements.txt`，然后补充语音/转写等 API 运行依赖。

主要依赖：

- Web/API：FastAPI、Uvicorn、Pydantic、python-multipart
- 认证/HTTP：PyJWT、python-jose、requests、httpx
- RAG/Agent：ChromaDB、LangChain、LangGraph、rank-bm25、jieba
- 文档处理：PyMuPDF、docx2txt、python-docx、Pillow
- 模型客户端：OpenAI SDK、langchain-openai、langchain-ollama
- 语音/视频辅助：baidu-aip、ffmpeg-python、faster-whisper、openai-whisper
- 浏览器自动化：Playwright

启动：

```bash
cd Edu_AI/api/Edu_AI
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

模板文件：`Edu_AI/api/Edu_AI/.env.example`

## 7. 模型与 env 样式

后端 `.env` 按功能分组，不把真实密钥提交到 Git。

### 7.1 轻量规划 / 逻辑模型

```env
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=
LOGIC_MODEL_MINI=openai/gpt-5.4-mini
DEFAULT_LLM_MODEL_ID=logic-gpt-5.4-mini
```

用途：聊天工作流里的轻量规划、路由和小模型推理。这里记录的是当前项目 `.env.example` 的默认模型名。

### 7.2 深度回答模型

```env
ANSWER_LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
ANSWER_LLM_API_KEY=
ANSWER_LLM_MODEL=qwen3.5-plus
```

用途：深度回答、报告正文、复杂内容生成。

### 7.3 视觉 / 多模态模型

```env
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=
VISION_MODEL_ID=qwen3.5-plus
```

用途：图片理解、多模态输入、AI Lecturer 脚本生成的兼容默认值。

### 7.4 兼容旧模块的 LLM 变量

```env
REMOTE_MODEL_API_BASE=https://api.deepseek.com/v1
REMOTE_MODEL_API_KEY=
LLM_MODEL=openai/gpt-5.4-mini
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=
```

用途：旧模块和 RAG v2 中仍会读取这些变量。新模块优先使用 `ANSWER_LLM_*`、`QWEN_*`。

### 7.5 Embedding

OpenAI-compatible / Gemini 风格：

```env
EMBEDDING_BACKEND=openai
EMBEDDING_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai
EMBEDDING_API_KEY=
EMBEDDING_MODEL=gemini-embedding-2-preview
GEMINI_EMBEDDING_DIMENSIONS=0
```

Ollama 本地方案：

```env
EMBEDDING_BACKEND=ollama
EMBEDDING_API_BASE=http://127.0.0.1:11434/v1
EMBEDDING_API_KEY=dummy-key
OLLAMA_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL=nomic-embed-text
```

### 7.6 RAG 可选 reranker

```env
RAG_ENABLE_RERANKER=0
RERANKER_API_BASE=
RERANKER_API_KEY=
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TIMEOUT=30
```

### 7.7 PPT 生成模型

```env
HTML2PPT_BASE_URL=http://127.0.0.1:46080
HTML2PPT_JOBS_ROOT=html2ppt/data/jobs
PPT_LLM_API_BASE=
PPT_LLM_API_KEY=
PPT_LLM_MODEL=
POWERPOINT_EXPORT_TIMEOUT_SEC=120
```

`PPT_LLM_*` 是后端报告/PPT 代理可读的 OpenAI-compatible 配置。`html2ppt` 服务自身默认通过 `PPT_CLAUDE_CMD` 调外部 agent 命令。

### 7.8 AI Lecturer

```env
AI_LECTURER_AUTOSTART=1
AI_LECTURER_OFFLINE_ENABLED=1
AI_LECTURER_GATEWAY_URL=http://127.0.0.1:8008
AI_LECTURER_LIVETALKING_URL=http://127.0.0.1:8010
AI_LECTURER_LIVETALKING_HUMAN_URL=http://127.0.0.1:8010/human
AI_LECTURER_CONDA_ENV=
AI_LECTURER_PYTHON=
AI_LECTURER_AVATAR_ID=my_teacher
AI_LECTURER_REF_FILE=zh-CN-XiaoxiaoNeural
AI_LECTURER_MODEL=wav2lip
AI_LECTURER_TTS=edgetts
AI_LECTURER_SCRIPT_MODEL=qwen-plus
AI_LECTURER_OUTLINE_MODEL=qwen-plus
```

如果 LiveTalking 或 Wav2Lip 放在独立环境，设置 `AI_LECTURER_CONDA_ENV` 或 `AI_LECTURER_PYTHON` 指向那个环境。

### 7.9 语音识别

```env
BAIDU_SPEECH_APP_ID=
BAIDU_SPEECH_API_KEY=
BAIDU_SPEECH_SECRET_KEY=
BAIDU_SPEECH_SAMPLE_RATE=16000
BAIDU_SPEECH_DEV_PID=1537
```

## 8. html2ppt 依赖

路径：`Edu_AI/api/Edu_AI/html2ppt/`

当前状态：

- 已同步上游 `Sun-Jia-Jun/ppt-generation-service` 的 `main`
- 当前上游 HEAD：`ce0ccfd1f6f5e4ae918f4ab540171b9937569cc7`
- 当前新增依赖：`ajv ^8.18.0`、`archiver ^7.0.1`
- 原有依赖：`cheerio ^1.0.0`、`express ^4.21.2`

安装：

```bash
npm ci --prefix Edu_AI/api/Edu_AI/html2ppt
npm ci --prefix Edu_AI/api/Edu_AI/html2ppt/dom-to-pptx
```

启动：

```bash
cd Edu_AI/api/Edu_AI/html2ppt
npm start
```

html2ppt env：

```env
PPT_SERVICE_PORT=46080
PPT_DATA_DIR=./data
PPT_WORKER_CONCURRENCY=1
PPT_CHROME_PATH=
PPT_CHROME_ARGS=[]
PPT_CHROME_TIMEOUT_MS=120000
PPT_CHROME_VIRTUAL_TIME_BUDGET_MS=1000
PPT_FFMPEG_PATH=ffmpeg
PPT_CLAUDE_CMD=claude
PPT_CLAUDE_ARGS=["-p","--output-format","text","--permission-mode","bypassPermissions"]
PPT_DEFAULT_THEME_ID=heu_academic_elegant
```

模板文件：`Edu_AI/api/Edu_AI/html2ppt/.env.example`

`PPT_CHROME_PATH` 留空时，服务会尝试系统常见的 Chrome、Edge、Chromium 路径。`PPT_FFMPEG_PATH` 默认使用 PATH 中的 `ffmpeg`。

## 9. AI Lecturer 依赖

推荐使用：

```bash
python -m pip install -r Edu_AI/api/Edu_AI/AI_Lecturer/requirements-offline-py312.txt
```

不要把 `AI_Lecturer/requirements.txt` 直接装进主后端环境。这个原始文件里存在多组重复/冲突 pin，例如多个 `aiohttp`、`Flask`、`numpy`、`opencv`、`Pillow`、`scipy`、`torch`、`transformers` 版本。当前项目已整理出 `requirements-offline-py312.txt` 作为 Python 3.12 的稳定安装入口。

LiveTalking GPU 栈建议单独环境：

```bash
conda create -n livetalking python=3.10
conda activate livetalking
pip install -r Edu_AI/api/Edu_AI/AI_Lecturer/LiveTalking-main/requirements.txt
```

如果机器没有 CUDA/GPU，不建议安装 LiveTalking 完整 requirements。

外部模型/权重不适合放入 Git，需要手动准备：

- Wav2Lip checkpoint
- LiveTalking avatar assets
- 需要的本地模型权重或缓存
- `models/`、`checkpoints/`、`assets/` 等大文件目录

## 10. RAG standalone

主后端已经包含当前应用需要的 RAG 依赖。`rag_v2/rag-main` 是独立实验工程，只有需要单独跑它时再安装：

```bash
python -m pip install -r Edu_AI/api/Edu_AI/rag_v2/rag-main/requirements.txt
```

或：

```bash
cd Edu_AI/api/Edu_AI/rag_v2/rag-main
python -m pip install -e .
```

注意：该模块会引入 `docling`、`streamlit`、更高版本的 `chromadb` 等重依赖，所以没有放入默认一键安装。

## 11. Env 文件初始化

安装脚本会在文件不存在时复制：

| Example | 本地文件 |
| --- | --- |
| `Edu_AI/.env.example` | `Edu_AI/.env` |
| `Edu_AI/api/Edu_AI/.env.example` | `Edu_AI/api/Edu_AI/.env` |
| `Edu_AI/api/Edu_AI/html2ppt/.env.example` | `Edu_AI/api/Edu_AI/html2ppt/.env` |
| `EduAgent/config.toml.example` | `EduAgent/config.toml` |

手动复制命令：

Windows：

```powershell
Copy-Item Edu_AI\.env.example Edu_AI\.env
Copy-Item Edu_AI\api\Edu_AI\.env.example Edu_AI\api\Edu_AI\.env
Copy-Item Edu_AI\api\Edu_AI\html2ppt\.env.example Edu_AI\api\Edu_AI\html2ppt\.env
Copy-Item EduAgent\config.toml.example EduAgent\config.toml
```

Linux/macOS：

```bash
cp Edu_AI/.env.example Edu_AI/.env
cp Edu_AI/api/Edu_AI/.env.example Edu_AI/api/Edu_AI/.env
cp Edu_AI/api/Edu_AI/html2ppt/.env.example Edu_AI/api/Edu_AI/html2ppt/.env
cp EduAgent/config.toml.example EduAgent/config.toml
```

`.env`、`.env.*`、`config.toml` 应只保留在本机；不要提交真实密钥。

## 12. 启动顺序

1. 启动 html2ppt：

```bash
cd Edu_AI/api/Edu_AI/html2ppt
npm start
```

2. 启动后端：

```bash
cd Edu_AI/api/Edu_AI
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

3. 启动前端：

```bash
cd Edu_AI
npm run dev
```

访问：

```text
http://127.0.0.1:5173
http://127.0.0.1:8000/docs
http://127.0.0.1:46080/health
```

## 13. 验证命令

安装后建议至少跑：

```bash
python -m pip check
npm run build --prefix Edu_AI
npm test --prefix Edu_AI/api/Edu_AI/html2ppt
```

可选：

```bash
npm test --prefix Edu_AI/api/Edu_AI/html2ppt/dom-to-pptx
```

当前已知情况：

- `html2ppt` 完整测试通过：`101 pass / 0 fail`
- `dom-to-pptx` 安装成功，但 `npm audit` 报告 `3 vulnerabilities`：`1 moderate`、`2 high`
- Windows PowerShell 读取 UTF-8 中文时可能因为控制台编码显示乱码，但文件本身按 UTF-8 保存

## 14. 避免冲突的原则

- 默认只安装主前端、主后端、html2ppt、dom-to-pptx。
- 不把根目录 `package.json` 装进默认流程，避免 Ant Design 6 与主前端 Ant Design 5 混淆。
- 不把 `AI_Lecturer/requirements.txt` 装进主后端环境，使用 `requirements-offline-py312.txt`。
- LiveTalking/CUDA/onnxruntime-gpu 使用独立环境。
- 大模型权重、checkpoint、缓存和真实密钥不进入 Git。
- 在新设备上优先使用 lockfile：`npm ci`，不要用 `npm install` 随意漂移版本。
