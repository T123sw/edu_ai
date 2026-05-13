#!/bin/bash
# RAG问答API启动脚本

echo "启动RAG问答API服务..."
echo "确保已安装依赖: pip install -r requirements-media.txt"
echo ""

# 检查是否安装了uvicorn
if ! command -v uvicorn &> /dev/null
then
    echo "未找到uvicorn，使用python直接启动..."
    python -m app.main
else
    echo "使用uvicorn启动服务..."
    # 确保在正确的目录下运行
    cd "$(dirname "$0")"
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-dir core
fi

