# Edu-AI

总结：

项目环境：conda activate edu_ai  

后端：
cd /home/llm/TTT/Edu_AI_Project/Edu_AI_1/Edu_AI/api/Edu_AI
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

前端：
cd /home/llm/TTT/Edu_AI_Project/Edu_AI_1/Edu_AI
npm run dev

浏览器访问：
http://192.168.1.51

初始密码：
teacher
teacher123

## 服务器启动说明

当前项目已经按单机 Linux 服务器方式跑通，部署结构是：

- 前端静态文件由 `nginx` 提供
- 后端由 `systemd + uvicorn` 提供
- 当前访问地址：`http://192.168.1.51`

项目分为两部分：

- 前端根目录：`Edu_AI/`
- 后端根目录：`Edu_AI/api/Edu_AI/`

## 服务器环境

建议环境：

- Python `3.12`
- Node.js `20.x`
- npm `10.x`
- nginx
- ffmpeg
- Miniconda 或其他可用 Python 环境管理方式
- 如果使用本机 Ollama：
  - `ollama`
  - `qwen3:8b`
  - `nomic-embed-text`

## 前端怎么启动

前端目录：

```bash
cd ~/TTT/Edu_AI_Project/Edu_AI_1/Edu_AI
```

安装依赖：

```bash
npm install
```

服务器构建前端时，使用：

```text
Edu_AI/.env
```

内容至少为：

```env
VITE_API_BASE_URL=http://192.168.1.51
```

然后执行构建：

```bash
npm run build
```

构建结果在：

```text
Edu_AI/dist
```

生产环境里，前端静态文件已复制到：

```text
/var/www/edu-ai
```

## 后端怎么启动

后端目录：

```bash
cd ~/TTT/Edu_AI_Project/Edu_AI_1/Edu_AI/api/Edu_AI
```

安装依赖：

```bash
pip install -r requirements_api.txt
```

手动启动后端时，推荐使用：

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

不要直接使用裸 `uvicorn`，否则很容易命中错误的 Python 环境。

后端运行后可访问：

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

## 后端环境变量

后端环境变量文件位置：

```text
Edu_AI/api/Edu_AI/.env
```

最少配置示例：

```env
JWT_SECRET_KEY=replace-with-a-strong-random-secret
CORS_ALLOW_ORIGINS=http://192.168.1.51

REMOTE_MODEL_API_BASE=http://127.0.0.1:11434/v1
REMOTE_MODEL_API_KEY=dummy-key
LLM_MODEL=qwen3:8b

EMBEDDING_BACKEND=ollama
EMBEDDING_API_BASE=http://127.0.0.1:11434/v1
EMBEDDING_API_KEY=dummy-key
OLLAMA_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL=nomic-embed-text
```

## systemd 启动

当前后端建议交给 `systemd` 管理。

服务文件参考：

- [edu-ai-backend.service](d:/Edu_AI_1/Edu_AI/deploy/systemd/edu-ai-backend.service)

当前服务器实用版 `ExecStart` 形式：

```ini
ExecStart=/home/llm/software/miniconda3/envs/edu_ai/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

常用命令：

```bash
sudo systemctl daemon-reload
sudo systemctl enable edu-ai-backend
sudo systemctl start edu-ai-backend
sudo systemctl restart edu-ai-backend
sudo systemctl status edu-ai-backend
sudo journalctl -u edu-ai-backend -n 80 --no-pager
```

## nginx 启动

当前前端由 `nginx` 托管，反向代理后端接口到 `127.0.0.1:8000`。

配置文件参考：

- [edu-ai.conf](d:/Edu_AI_1/Edu_AI/deploy/nginx/edu-ai.conf)

当前服务器需要注意：

- `root` 不要直接指向 `/home/llm/.../dist`
- 建议使用：

```text
/var/www/edu-ai
```

常用命令：

```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl reload nginx
sudo systemctl status nginx
```

## 浏览器怎么打开

部署完成后，浏览器访问：

- 前端首页：

```text
http://192.168.1.51
```

- 后端健康检查：

```text
http://192.168.1.51/health
```

- 后端 Swagger：

```text
http://192.168.1.51/docs
```

## 推荐启动顺序

服务器上推荐顺序：

1. 确认 Ollama 或模型服务已启动
2. 确认后端 `.env` 已配置
3. 重建前端：

```bash
cd ~/TTT/Edu_AI_Project/Edu_AI_1/Edu_AI
npm run build
```

4. 同步前端静态文件到：

```bash
sudo mkdir -p /var/www/edu-ai
sudo cp -r dist/* /var/www/edu-ai/
sudo chown -R www-data:www-data /var/www/edu-ai
sudo chmod -R 755 /var/www/edu-ai
```

5. 启动后端：

```bash
sudo systemctl restart edu-ai-backend
```

6. 重载 nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

7. 浏览器打开：

```text
http://192.168.1.51
```

## 常见问题

- `No module named 'fastapi'`
  - 启动用的 Python 和安装依赖用的 Python 不一致
- `uvicorn` 能跑但 `systemd` 失败
  - 通常是 8000 端口被手动启动的旧进程占用
- 首页 500
  - 通常是 nginx 没权限读取前端静态目录
- 爬虫模块导入失败
  - 通常是 `EduAgent` / `自动化爬虫` 相关依赖未装全

## 相关文档

- 服务器部署：[DEPLOY_TO_LINUX_SERVER.md](d:/Edu_AI_1/Edu_AI/docs/DEPLOY_TO_LINUX_SERVER.md)
- 依赖整理：[DEPLOYMENT_DEPENDENCIES.md](d:/Edu_AI_1/Edu_AI/docs/DEPLOYMENT_DEPENDENCIES.md)

---

## Edu-AI 教学智能助手（项目总览）

基于 **React + TypeScript + Ant Design + FastAPI + ChromaDB** 的教学智能助手系统，面向“教师备课 + 学生学习 + 教学内容管理”场景，提供 **智能问答、教师工具、文档管理、数据采集、知识库管理** 等一体化能力。

---

## ✨ 核心功能（按前端模块划分）

- **智能问答（`/chat`）**
  - 支持多轮对话与对话历史的**永久存储**，首条提问自动生成对话标题。
  - 集成 **RAG 检索增强**：将检索到的文档片段与对话历史一起作为上下文，提升回答专业度与可解释性。
  - 支持 **多模型选择**，当前默认模型为“**水声大模型**”，后续可扩展其他本地/服务器模型。
  - 检索结果展示时只显示**文档名与页码**，隐藏具体文件路径，便于教学场景直接使用。

- **教师工具（`/teacher-tools`）**
  - **教案生成**：基于课程名称、教学目标/重点/难点、课时长度等信息，由大模型生成结构化教案（教学目标、教学过程、作业等），并支持长期保存与导出 Markdown。
  - **题目生成**：围绕知识点自动生成选择题/填空题/简答题等，内置**严格提示词约束**，保证题型与前端选择一致，并输出答案与解析。
  - **教案管理**：查看、搜索、删除已生成教案记录，支持一键导出为 `.md` 文件。

- **文档管理（`/docs`）**
  - 支持 **最大 100MB PDF 文件** 上传，采用“**两步上传 + 进度轮询**”方案，实现真实的上传与解析进度条。
  - 先上传至后端临时目录，再异步解析并导入向量数据库，前端通过轮询接口展示 0–100% 全流程进度。
  - 支持任务**重传、取消、清空任务列表**，并通过 `localStorage` 持久化上传任务状态，页面切换后仍能看到未完成/失败任务。
  - 已导入文档可控制是否参与 RAG 检索，支持生成**简明扼要的 PDF 总结**。

- **数据采集（`/data-pipeline`）**
  - 提供关键词采集与 URL 采集的配置界面（采集逻辑可按需扩展）。
  - 包含数据爬取、PDF 解析、训练数据生成、训练任务等流程的**可视化监控面板**，为后续自动化微调训练预留入口。

- **知识库（`/knowledge-base`）**
  - 统一管理来自“数据采集模块”和“文档管理模块”的正文内容与 PDF 内容。
  - 提供按来源、标签、关键词的筛选与浏览界面，为 RAG 与教学工具提供底层知识支持。

- **欢迎页 & 全局布局**
  - 欢迎页展示“智能问答、教师工具、文档管理、数据采集、知识库”五大功能卡片，横向排布，可横向滚动。
  - 左侧菜单顺序：**智能问答 → 教师工具 → 文档管理 → 数据采集 → 知识库**，Sider 宽度加宽，整体采用渐变背景 + 卡片式主内容风格。

---

## 🏗️ 技术栈

- **前端**
  - **React 18**
  - **TypeScript 5**
  - **Vite**
  - **Ant Design 5**
  - React Router

- **后端**
  - **Python 3.12+**
  - **FastAPI**
  - **Pydantic**
  - **ChromaDB**（向量数据库）
  - 自研 RAG 系统（`new_rag` 模块）
  - 会话持久化与教案持久化组件

---

## 📁 项目结构概览

```text
Edu_AI/
├── api/
│   └── Edu_AI/
│       ├── app/
│       │   └── main.py              # FastAPI 主入口，汇总认证、RAG、教师工具等接口
│       ├── new_rag/
│       │   ├── system.py            # RAG 核心逻辑，文档导入、向量检索、问答
│       │   └── api.py               # RAG 相关 API（导入、进度查询等）
│       ├── core/
│       │   ├── config.py            # 全局配置与模型注册（包含 “水声大模型”）
│       │   ├── conversation_storage.py  # 对话持久化
│       │   ├── lesson_plan_storage.py   # 教案持久化
│       │   └── __init__.py
│       └── ...                      # 其他后端模块与脚本
├── src/
│   ├── layout/
│   │   ├── MainLayout.tsx           # 主布局（左侧菜单 + 顶部 Header）
│   │   └── MainLayout.css
│   ├── pages/
│   │   ├── WelcomePage.tsx / .css   # 欢迎页
│   │   ├── ChatPage.tsx / .css      # 智能问答
│   │   ├── TeacherToolsPage.tsx/.css# 教师工具（教案/题目/教案管理）
│   │   ├── DocsPage.tsx / .css      # 文档管理（PDF 上传/解析/列表）
│   │   ├── DataPipelinePage.tsx/.css# 数据采集配置与监控
│   │   └── KnowledgeBasePage.tsx    # 知识库浏览
│   ├── services/
│   │   ├── chat.ts                  # 聊天 & 模型列表 API 封装
│   │   ├── rag.ts                   # 文档上传/导入/进度查询 API 封装
│   │   └── teacher.ts               # 教案、题目、教案管理 API 封装
│   └── routes/
│       └── AppRoutes.tsx            # 前端路由定义
├── public/                          # 静态资源
├── README.md                        # 本文件
└── 其他配置文件（`package.json`、`tsconfig.json` 等）
```

> 以上结构为核心目录示意，实际文件请以项目为准。

---

## 🚀 快速开始

### 1. 环境准备

- **Node.js** ≥ 18
- **Python** ≥ 3.12
- 已安装 `git`、`pip`（建议使用虚拟环境）

### 2. 克隆项目

```bash
git clone <your-repo-url>
cd Edu_AI
```

### 3. 安装前端依赖

```bash
npm install
```

### 4. 安装后端依赖

```bash
cd api/Edu_AI
pip install -r requirements.txt
```

### 5. 配置环境变量

在项目根目录创建 `.env`（如果已有则直接修改）：

```env
# 后端 API 基础地址
VITE_API_BASE_URL=http://localhost:8000
```

如需接入外部大模型（OpenAI、通义千问、智谱等），可在后端单独配置对应的环境变量或配置文件（根据你自己的部署方式补充）。

### 6. 启动后端

#### 方式一：使用启动脚本（推荐）

如果你已经配置了启动脚本（如 `start_api.bat` / `start_api.sh`）：

```bash
cd api/Edu_AI
start_api.bat    # Windows
# 或
bash start_api.sh  # Linux / macOS
```

#### 方式二：直接使用 `uvicorn`

```bash
cd api/Edu_AI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动成功后，可访问 `http://localhost:8000/docs` 查看自动生成的 Swagger API 文档。

### 7. 启动前端

在项目根目录：

```bash
npm run dev
```

默认访问地址为 `http://localhost:5173`。

---

## 🔌 主要接口一览（示意）

- **聊天与模型**
  - `POST /chat`：对话接口，支持传入 `model_id`、对话历史等。
  - `GET /models`：获取可用模型列表（含“水声大模型”等）。

- **RAG / 文档导入**
  - `POST /api/rag/upload_temp`：上传文件到临时目录，返回临时路径与任务 ID。
  - `POST /api/rag/import/path`：从临时路径开始导入文档（异步任务）。
  - `GET /api/rag/import/progress`：查询导入任务进度。

- **教师工具**
  - `POST /teacher/lesson_plan`：生成教案。
  - `GET /teacher/lesson_plans`：获取教案列表。
  - `GET /teacher/lesson_plans/{plan_id}`：获取教案详情。
  - `DELETE /teacher/lesson_plans/{plan_id}`：删除教案。
  - `POST /teacher/questions`：生成题目（严格遵守题型与 JSON 结构）。

> 完整接口参数与返回格式请以 `http://localhost:8000/docs` 中的在线文档为准。

---

## 🧑‍🏫 教学场景说明（简要）

- **备课**：教师在“教师工具”中输入课程名称和教学要求，快速生成结构化教案，并进行人工微调与长期保存。
- **出题**：根据知识点与难度，一键生成不同类型习题，并直接查看答案与解析，用于课堂练习或单元测验。
- **知识支撑**：上传课程相关 PDF 或通过数据采集获取正文内容，构建专属知识库，供智能问答与教案/题目生成调用。
- **课堂互动**：学生或教师可以在“智能问答”中就知识点提问，系统基于对话历史 + 检索结果进行回答。 

---

## 📝 配置与扩展

- **模型配置**
  - 在 `api/Edu_AI/core/config.py` 中可以注册多个 LLM 模型，设置默认模型（如“水声大模型”）及对外展示名称。

- **对话与教案存储**
  - `conversation_storage.py`：负责将对话保存到本地 JSON 文件，实现多会话管理与长期存储。
  - `lesson_plan_storage.py`：负责教案的本地 JSON 持久化，用于教案管理与导出。

- **向量数据库**
  - 当前使用 **ChromaDB** 存储文档向量，你可以根据需要替换为 Milvus、PGVector 等其他方案，只需调整 RAG 模块实现。

---

## ⚠️ 注意事项

- **端口占用**：后端默认使用 `8000` 端口，如被占用请手动修改或停止占用进程。
- **大文件上传**：已支持最大 100MB PDF，如网络环境较差，建议在局域网环境下上传。
- **隐私与安全**：在生产环境中使用时，请完善用户权限、CORS 白名单与日志脱敏等配置。

---

## 🤝 贡献与反馈

- 欢迎根据自己学校/课程场景进行二次开发：
  - 增加新的教师工具模块（如作业批改、课堂互动提问等）；
  - 扩展数据采集逻辑与训练流水线；
  - 接入更多大模型或自研模型。
- 如在使用或二次开发过程中有任何问题，欢迎提交 Issue 或 Pull Request。

---

本 README 主要面向**开发者与教学应用方**，帮助你快速理解本项目的整体结构与功能模块，并顺利在本地或服务器环境中跑起来、改起来、用起来。 
