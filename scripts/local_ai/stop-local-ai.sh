#!/bin/bash
# 停止 Edu-AI 全部本地 AI 服务
echo "停止本地 AI 服务..."
sudo systemctl stop edu-ai-tts
sudo systemctl stop edu-ai-embedding
echo "✅ 已停止（GPU 显存已释放）"
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader