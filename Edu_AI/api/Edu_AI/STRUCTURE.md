# 后端项目结构说明（精简版）

## 📁 目录结构

```
api/Edu_AI/
├── app/                      # FastAPI 应用层（仅保留 main + 认证路由）
│   ├── __init__.py
│   └── main.py
│
├── core/                     # 核心能力（配置 + 认证/存储）
│   ├── __init__.py
│   ├── auth.py               # JWT 相关逻辑
│   ├── user_storage.py       # 用户信息读写
│   └── config.py             # 统一配置与路径
│
├── new_rag/                  # 新版 RAG（requests 实现）
│   ├── __init__.py
│   ├── api.py                # FastAPI 路由
│   └── system.py             # RAG 核心逻辑
│
├── storage/                  # 向量库 / 临时文件 / 索引
│   ├── vector_db/
│   ├── temp/
│   └── document_index.json
│
├── docs/                     # 使用说明与部署文档
├── requirements_api.txt
├── requirements.txt
└── start_api.bat|sh          # 可选启动脚本
```

## 📝 模块说明

- `app/main.py`：FastAPI 入口，挂载认证与 `new_rag` 路由，同时提供兼容的 `/chat`、`/health` 等简单接口。
- `core/`：只保留当前必须的 `config.py`、`auth.py`、`user_storage.py`，退出所有旧 RAG 相关代码。
- `new_rag/`：包含 `RAGSystem`、嵌入调用、增量导入、问答 API，全量采用 `requests`。
- `storage/`：统一保存向量数据库、临时文件与文档索引，便于备份迁移。

## 🔧 启动方式

```bash
cd D:\Edu_AI\api\Edu_AI
uvicorn app.main:app --reload
```

如需脚本，可使用 `start_api.bat` 或 `start_api.sh`。

## ⚙️ 关键环境变量

```
REMOTE_MODEL_API_BASE   # LLM 服务地址（OpenAI 兼容）
REMOTE_MODEL_API_KEY    # LLM 服务密钥
EMBEDDING_BACKEND       # ollama / openai
EMBEDDING_API_BASE      # 嵌入服务地址（例如 http://localhost:11434）
OLLAMA_BASE_URL         # Ollama 兼容地址
EMBEDDING_MODEL         # 嵌入模型名称
LLM_MODEL               # 回答生成模型名称
```

## ✅ 当前状态

- 旧版 RAG、脚本、备份目录全部移除。
- 依赖列表精简，仅保留 `FastAPI + new_rag` 所需库。
- `.env` 中的嵌入/LLM 配置可直接驱动新系统。
- 前端登录、文档管理、RAG 问答使用统一 API。

