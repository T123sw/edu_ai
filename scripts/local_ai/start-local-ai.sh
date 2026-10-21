#!/bin/bash
# 启动 Edu-AI 全部本地 AI 服务
set -e
echo "启动本地 AI 服务..."
sudo systemctl start edu-ai-tts edu-ai-embedding
sleep 20
echo "等待模型加载完成..."
for i in $(seq 1 30); do
  t=$(curl -s -m 3 http://127.0.0.1:8188/health 2>/dev/null | grep -c model_loaded..true)
  e=$(curl -s -m 3 http://127.0.0.1:8189/health 2>/dev/null | grep -c '"status":"ok"')
  if [ "$t" = "1" ] && [ "$e" = "1" ]; then echo "✅ 全部就绪"; exit 0; fi
  sleep 2
done
echo "⚠️ 部分服务未就绪，请检查日志"