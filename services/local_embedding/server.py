"""Edu-AI 本地向量服务：Qwen3-Embedding-0.6B（OpenAI 兼容 /v1/embeddings）

路由策略：
  - 文本   -> 本地 Qwen3-Embedding-0.6B（GPU1，MRL 截断到 EMB_DIM，默认 768 与原索引兼容）
  - 图片   -> 原样转发给远程 provider（保持多模态能力不丢失）
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, List, Optional, Tuple, Union

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

MODEL_DIR = os.environ.get("EMB_MODEL_DIR", "/home/zxqs_ep/data/models/Qwen3-Embedding-0.6B")
DEVICE = os.environ.get("EMB_DEVICE", "cuda:1")
HOST = os.environ.get("EMB_HOST", "127.0.0.1")
PORT = int(os.environ.get("EMB_PORT", "8189"))
MODEL_ID = os.environ.get("EMB_MODEL_ID", "qwen3-embedding-0.6b")
BATCH = int(os.environ.get("EMB_BATCH", "16"))
MAX_LEN = int(os.environ.get("EMB_MAX_LEN", "1024"))
# 本地文本向量输出维度（MRL 截断）。768 = 与现有索引兼容；1024 = 原生维度。
EMB_DIM = int(os.environ.get("EMB_DIM", "768"))
# 图片请求转发目标（保持原有远程多模态能力）
REMOTE_BASE = os.environ.get("EMB_REMOTE_BASE", "https://api.relayrouter.ai/v1")
REMOTE_KEY = os.environ.get("EMB_REMOTE_KEY", "")
REMOTE_MODEL = os.environ.get("EMB_REMOTE_MODEL", "gemini-embedding-2-preview")
REMOTE_TIMEOUT = float(os.environ.get("EMB_REMOTE_TIMEOUT", "180"))

_lock = threading.Lock()
_stats = {"requests": 0, "texts": 0, "images_forwarded": 0, "batches": 0, "total_ms": 0}

print("[embed] loading " + MODEL_DIR + " on " + DEVICE + " ...", flush=True)
_t0 = time.time()
from transformers import AutoModel, AutoTokenizer

_tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
if _tokenizer.pad_token is None:
    _tokenizer.pad_token = _tokenizer.eos_token
_tokenizer.padding_side = "right"
_model = AutoModel.from_pretrained(MODEL_DIR, torch_dtype=torch.bfloat16, local_files_only=True)
_model = _model.to(DEVICE).eval()
_LOAD_S = round(time.time() - _t0, 2)
_NATIVE_DIM = int(_model.config.hidden_size)
print("[embed] ready in " + str(_LOAD_S) + "s, native_dim=" + str(_NATIVE_DIM) + ", out_dim=" + str(EMB_DIM), flush=True)

app = FastAPI(title="local-embedding", version="1.1.0")


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: Optional[str] = None
    encoding_format: Optional[str] = "float"
    dimensions: Optional[int] = None
    instruction: Optional[str] = None


def _is_image_input(value: str) -> bool:
    v = value.strip().lower()
    if v.startswith("data:image"):
        return True
    if v.startswith("http"):
        head = v.split("?")[0]
        return any(head.endswith(e) for e in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"))
    return False


def _truncate(vec: np.ndarray, dims: int) -> np.ndarray:
    if dims and 0 < dims < vec.shape[1]:
        vec = vec[:, :dims]
        n = np.linalg.norm(vec, axis=1, keepdims=True)
        n[n == 0] = 1.0
        vec = vec / n
    return vec


@torch.inference_mode()
def _embed_local(texts: List[str], instruction: Optional[str], dims: int) -> np.ndarray:
    if instruction:
        texts = ["Instruct: " + instruction + "\nQuery: " + t for t in texts]
    out = []
    for i in range(0, len(texts), BATCH):
        chunk = texts[i:i + BATCH]
        enc = _tokenizer(chunk, padding=True, truncation=True, max_length=MAX_LEN,
                         return_tensors="pt").to(DEVICE)
        hidden = _model(**enc).last_hidden_state.float().cpu().numpy()
        mask = enc["attention_mask"].cpu().numpy()
        last = mask.sum(axis=1) - 1
        vec = hidden[np.arange(hidden.shape[0]), last]
        norm = np.linalg.norm(vec, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        out.append(vec / norm)
        _stats["batches"] += 1
    return _truncate(np.concatenate(out, axis=0), dims)


def _forward_remote(payload: dict) -> Tuple[int, Any]:
    import httpx
    headers = {"Content-Type": "application/json"}
    if REMOTE_KEY:
        headers["Authorization"] = "Bearer " + REMOTE_KEY
    url = REMOTE_BASE.rstrip("/") + "/embeddings"
    with httpx.Client(timeout=REMOTE_TIMEOUT) as c:
        r = c.post(url, headers=headers, json=payload)
    return r.status_code, r.json()


@app.get("/health")
def health():
    return {"status": "ok", "service": "local-embedding", "model_loaded": True,
            "model": MODEL_ID, "device": DEVICE, "dim": EMB_DIM, "native_dim": _NATIVE_DIM,
            "load_s": _LOAD_S, "unified_dim": EMB_DIM}


@app.get("/stats")
def stats():
    return {"device": DEVICE, "dim": EMB_DIM, "batch": BATCH,
            "remote_base": REMOTE_BASE, **_stats}


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local"}]}


@app.post("/v1/embeddings")
def embeddings(req: EmbeddingRequest):
    texts = [req.input] if isinstance(req.input, str) else list(req.input or [])
    if not texts:
        raise HTTPException(status_code=400, detail="'input' must not be empty")

    dims = req.dimensions or EMB_DIM

    # --- 图片：转发给远程 provider，保持多模态能力 ---
    if any(isinstance(t, str) and _is_image_input(t) for t in texts):
        payload = {"model": req.model or REMOTE_MODEL,
                   "input": [t if isinstance(t, str) else "" for t in texts]}
        try:
            code, body = _forward_remote(payload)
        except Exception as exc:
            return JSONResponse(status_code=502, content={"error": {
                "code": "remote_forward_failed",
                "message": "图片向量转发失败: " + str(exc), "retryable": True}})
        _stats["images_forwarded"] += 1
        return JSONResponse(status_code=code, content=body)

    # --- 文本：本地推理 ---
    texts = [str(t) if t else " " for t in texts]
    t0 = time.perf_counter()
    with _lock:
        emb = _embed_local(texts, req.instruction, dims)
    dur_ms = int((time.perf_counter() - t0) * 1000)

    _stats["requests"] += 1
    _stats["texts"] += len(texts)
    _stats["total_ms"] += dur_ms
    print("[embed] n=" + str(len(texts)) + " dim=" + str(emb.shape[1]) + " " + str(dur_ms) + "ms", flush=True)

    return {"object": "list",
            "data": [{"object": "embedding", "index": i, "embedding": [float(x) for x in v]}
                     for i, v in enumerate(emb)],
            "model": MODEL_ID,
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
            "latency_ms": dur_ms}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")