#!/bin/bash
# Edu-AI 本地 AI 服务健康巡检（2026-10-17）
echo "===== systemd 服务状态 ====="
for s in postgresql edu-ai-backend nginx edu-ai-tts edu-ai-embedding edu-ai-mineru; do
  printf "  %-24s %s\n" "$s" "$(systemctl is-active $s 2>/dev/null)"
done

echo
echo "===== 本地 TTS (8188) ====="
curl -s -m 10 http://127.0.0.1:8188/health || echo "  ❌ 无响应"
echo
curl -s -m 10 http://127.0.0.1:8188/stats | head -c 300
echo

echo
echo "===== 本地 Embedding (8189) ====="
curl -s -m 10 http://127.0.0.1:8189/health || echo "  ❌ 无响应"
echo

echo
echo "===== 本地 MinerU (8190) ====="
curl -s -m 15 http://127.0.0.1:8190/v1/health || echo "  ❌ 无响应"
echo

echo
echo "===== 后端 (8001) ====="
curl -s -o /dev/null -m 10 -w "  /backend/docs HTTP %{http_code}\n" http://127.0.0.1/backend/docs

echo
echo "===== GPU ====="
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader

echo
echo "===== 关键配置 ====="
grep -E '^(TTS_LOCAL_ONLY|TTS_API_BASE|EMBEDDING_API_BASE|EMBEDDING_MODEL|VECTOR_DB_PATH|RAG_ENABLE_IMAGE_EMBEDDING|PDF_PARSER_PROVIDER|PDF_MINERU_LOCAL_BASE_URL)=' /home/zxqs_ep/Edu_AI/.env