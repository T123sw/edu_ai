import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
# 假设 api.py 和 system.py 放在一个叫 app 的文件夹里
from api import router as rag_router

app = FastAPI(title="我的工业级 RAG 知识库系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件服务（用于前端访问图片和视频）
storage_path = Path("./storage")
if storage_path.exists():
    app.mount("/storage", StaticFiles(directory="storage"), name="storage")
    print(f"[静态文件] 已挂载 /storage 目录，可通过 http://localhost:8000/storage/images/xxx.jpg 访问")
else:
    print(f"[警告] storage 目录不存在，跳过静态文件挂载")

# 挂载 RAG 路由
app.include_router(rag_router)

@app.get("/")
def read_root():
    return {"message": "RAG 后端服务已成功启动！请访问 /docs 查看接口文档。"}

if __name__ == "__main__":
    # 在 8000 端口启动服务
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)