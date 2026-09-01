#!/bin/bash
# Edu-AI 环境安装脚本 (Linux/macOS)

set -e  # 遇到错误立即退出

echo "=========================================="
echo "Edu-AI 环境安装脚本"
echo "=========================================="
echo ""

# 检查 Conda 是否安装
if ! command -v conda &> /dev/null; then
    echo "❌ 错误: 未找到 Conda，请先安装 Miniconda 或 Anaconda"
    echo "   下载地址: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo "✅ 检测到 Conda: $(conda --version)"
echo ""

# 检查是否在项目根目录
if [ ! -f "environment.yml" ]; then
    echo "❌ 错误: 未找到 environment.yml，请确保在 Edu_AI 目录下运行此脚本"
    exit 1
fi

# 步骤 1: 创建 Conda 环境
echo "[1/4] 创建 Conda 环境..."
if conda env list | grep -q "^edu-ai "; then
    echo "⚠️  环境 'edu-ai' 已存在，是否覆盖？(y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        conda env remove -n edu-ai -y
        conda env create -f environment.yml
    else
        echo "跳过环境创建，使用现有环境"
    fi
else
    conda env create -f environment.yml
fi

echo "✅ Conda 环境创建完成"
echo ""

# 激活环境
echo "[2/4] 激活环境并验证..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate edu-ai

# 验证 Python
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "✅ Python 版本: $python_version"

# 验证 Node.js
if command -v node &> /dev/null; then
    node_version=$(node --version)
    echo "✅ Node.js 版本: $node_version"
else
    echo "⚠️  警告: Node.js 未找到，将通过 conda 安装"
    conda install nodejs=20 -c conda-forge -y
fi

echo ""

# 步骤 3: 安装后端依赖（如果需要）
echo "[3/4] 检查后端依赖..."
if [ -f "backend/src/requirements-media.txt" ]; then
    echo "安装后端 Python 依赖..."
    cd backend/src
    pip install -r requirements-media.txt
    cd ../..
    echo "✅ 后端依赖安装完成"
else
    echo "⚠️  未找到 requirements_api.txt，跳过后端依赖安装"
fi
echo ""

# 步骤 4: 安装前端依赖
echo "[4/4] 安装前端 Node.js 依赖..."
if [ -f "package.json" ]; then
    npm install
    echo "✅ 前端依赖安装完成"
else
    echo "❌ 错误: 未找到 package.json"
    exit 1
fi

echo ""
echo "=========================================="
echo "🎉 环境安装完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 激活环境: conda activate edu-ai"
echo "2. 配置 .env 文件（参考 ENVIRONMENT.md）"
echo "3. 启动后端: cd backend && uvicorn Edu_AI.app.main:app --host 0.0.0.0 --port 8001 --reload"
echo "4. 启动前端: npm run dev"
echo ""

