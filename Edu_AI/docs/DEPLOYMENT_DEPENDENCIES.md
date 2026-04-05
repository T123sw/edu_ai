# Edu-AI 部署依赖说明

本文档用于统一 `environment.yml`、`requirements.txt`、`requirements_api.txt` 的职责，避免本地开发与服务器部署时出现依赖漂移。

## 文件分工

- `api/Edu_AI/requirements.txt`
  - 后端基础运行依赖
  - 覆盖主 API、认证、RAG、课程、聊天主链路
- `api/Edu_AI/requirements_api.txt`
  - 完整后端部署依赖
  - 在基础依赖上补充视频入库相关能力
- `environment.yml`
  - 本地开发环境
  - 负责安装 `Python 3.12`、`Node.js 20`，并复用 `requirements_api.txt`

## 推荐安装方式

### 服务器部署

```bash
cd Edu_AI/api/Edu_AI
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements_api.txt
```

### 本地开发

```bash
cd Edu_AI
conda env create -f environment.yml
conda activate edu-ai
npm install
```

## 系统级依赖

以下不是 Python 包，需要在服务器操作系统中单独安装：

- `ffmpeg`
- `ffprobe`

如果不启用视频入库与转写功能，后端核心接口通常不依赖这两个系统命令。

## 环境建议

- Python: `3.12`
- Node.js: `20.x`
- 部署前端时执行 `npm run build`
- 后端建议使用 `uvicorn` 配合 `systemd` 或 `supervisor`
- 生产环境请显式设置 `JWT_SECRET_KEY` 与模型/Embedding 相关环境变量

## 说明

- 当前仓库存在两套前端目录，推荐以仓库根目录下的 `package.json` 和 `src/` 作为主前端工程。
- 前端服务默认端口在个别模块中存在 `8000/8001` 混用，生产环境建议统一通过 `VITE_API_BASE_URL` 指向同一个反向代理地址。
