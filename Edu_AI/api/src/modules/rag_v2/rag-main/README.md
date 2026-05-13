# Enterprise RAG Backend Service

一个支持多模态解析和检索的企业级 RAG 后端服务。本项目深度集成了本地 GPU 加速的 `MinerU` 引擎，能够完美处理包含复杂排版、数学公式和专业图表的技术文档。

## 🚀 核心特性

- **工业级文档解析**：优先使用 `MinerU` 进行本地 GPU 加速解析，保留原始排版与 LaTeX 公式；内置 `PyMuPDF` 作为优雅降级的容错方案，确保高可用性。
- **混合增强检索**：集成向量检索（BGE-M3）、关键词检索（BM25）以及 HyDE 假设性文档嵌入技术。
- **智能重排融合**：支持 RRF（互易排名融合）算法与 BGE-Reranker 重排模型，显著提升召回结果的精准度。
- **高性能架构**：基于 `FastAPI` 构建，原生支持异步处理与跨域请求（CORS）。
- **多模态存储**：底层采用 `ChromaDB`，支持文本与图片向量的统一管理与溯源。

## 🛠️ 环境安装指南

### 1. 基础依赖
本项目需要 Python 3.10+ 环境。建议使用 `uv` 或 `pip` 管理依赖：
```bash
pip install -r requirements.txt
```

### 2. CUDA 环境配置 (MinerU 必需)
由于 MinerU 依赖 NVIDIA GPU 进行 VLM 推理，请确保你的系统已安装：
- **NVIDIA Driver**: 版本 >= 535
- **CUDA Toolkit**: 版本 >= 11.8 (推荐 12.x)
- **cuDNN**: 对应版本的 cuDNN 库

### 3. MinerU 安装
请参考 [MinerU 官方文档](https://github.com/opendatalab/MinerU) 完成 CLI 工具的安装与环境变量配置。

## ⚙️ 启动方式

1. **配置环境变量**：
   复制 `.env.example` 为 `.env` 并填入你的 API Keys。
   ```bash
   cp .env.example .env
   ```

2. **启动服务**：
   ```bash
   python main.py
   ```
   服务默认运行在 `http://0.0.0.0:8000`。

## 📂 根目录脚本说明

- **`batch_import.py`**：
  用于批量导入纯文本或 PDF 文件到知识库。该脚本会调用 MinerU 进行解析，并自动完成分块、向量化及入库流程。

- **`batch_import_images.py`**：
  专门用于图片数据的批量向量化入库。适用于将已有的插图、截图等视觉资产转化为可检索的向量数据。

---
*Built with FastAPI, MinerU & ChromaDB.*
