# -*- coding: utf-8 -*-
"""独立重建 Chroma 索引：旧 3072 维 (Gemini) -> 新 1024 维 (Qwen3-Embedding-0.6B)

旧索引保持不动，新索引写入独立目录，验证通过后再切换 VECTOR_DB_PATH。
"""
import json
import os
import sys
import time
import urllib.request

OLD_PATH = "/home/zxqs_ep/data/edu_ai/staging/vector_db_20260907_linux"
NEW_PATH = "/home/zxqs_ep/data/edu_ai/staging/vector_db_qwen3_1024"
EMB_URL = "http://127.0.0.1:8189/v1/embeddings"
EMB_MODEL = "qwen3-embedding-0.6b"
EMB_BATCH = 32
READ_BATCH = 500

import chromadb

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def embed(texts):
    body = json.dumps({"model": EMB_MODEL, "input": texts}).encode()
    req = urllib.request.Request(EMB_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
    return [x["embedding"] for x in d["data"]]

def main():
    log(f"打开旧索引 {OLD_PATH}")
    old_client = chromadb.PersistentClient(path=OLD_PATH)
    old_col = old_client.get_collection("documents")
    total = old_col.count()
    log(f"旧索引条数: {total}")

    log(f"创建新索引 {NEW_PATH}")
    new_client = chromadb.PersistentClient(path=NEW_PATH)
    try:
        new_client.delete_collection("documents")
        log("已删除同名旧集合（重建）")
    except Exception:
        pass
    new_col = new_client.create_collection("documents", metadata={"hnsw:space": "cosine"})

    done = 0
    t_start = time.time()
    offset = 0
    while offset < total:
        res = old_col.get(limit=READ_BATCH, offset=offset,
                          include=["documents", "metadatas"])
        ids = res["ids"]
        docs = res["documents"]
        metas = res["metadatas"]
        if not ids:
            break

        add_ids, add_docs, add_metas, add_embs = [], [], [], []
        for i in range(0, len(ids), EMB_BATCH):
            sl = slice(i, i + EMB_BATCH)
            chunk_ids = ids[sl]
            chunk_docs = [(d or " ") for d in docs[sl]]
            chunk_metas = metas[sl]
            vecs = embed(chunk_docs)
            add_ids.extend(chunk_ids)
            add_docs.extend(chunk_docs)
            add_metas.extend([m or {} for m in chunk_metas])
            add_embs.extend(vecs)

        new_col.add(ids=add_ids, documents=add_docs, metadatas=add_metas, embeddings=add_embs)
        done += len(ids)
        offset += READ_BATCH
        elapsed = time.time() - t_start
        rate = done / elapsed if elapsed else 0
        eta = (total - done) / rate if rate else 0
        log(f"进度 {done}/{total} ({done*100//total}%)  用时 {elapsed:.0f}s  速率 {rate:.1f}/s  ETA {eta:.0f}s")

    log(f"完成！新索引条数: {new_col.count()}")

if __name__ == "__main__":
    main()