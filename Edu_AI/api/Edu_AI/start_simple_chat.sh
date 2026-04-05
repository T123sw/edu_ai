#!/bin/bash

echo "========================================"
echo "启动简化对话后端服务"
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "[1/2] 检查 Python 环境..."
python3 --version
if [ $? -ne 0 ]; then
    echo "[错误] 未找到 Python，请先安装 Python 3.12+"
    exit 1
fi

echo ""
echo "[2/2] 启动简化对话服务..."
echo "API服务将运行在: http://localhost:8000"
echo "按Ctrl+C 停止服务"
echo ""

python3 -m uvicorn app.simple_chat:app --host 0.0.0.0 --port 8000 --reload

