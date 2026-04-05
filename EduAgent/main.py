from fastapi import FastAPI, UploadFile, File
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel

from starlette.responses import FileResponse

from define import *
from deepsearch import deepsearch_large_llm
from fastapi.responses import JSONResponse
import uvicorn
import uuid
import shutil
from chunks import *
from fastapi.middleware.cors import CORSMiddleware

# 导入新服务模块
from services.crawler_service import get_crawler_service
from services.content_cleaner import ContentCleaner
from services.storage_service import get_storage_service


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,   # 没用 cookie 就 False
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}



@app.post("/agent/deepsearch")
def deepsearch(query: str):

    output = deepsearch_large_llm(query)
    if output is None:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "DeepSearch failed",
            },
        )

    return {
        "ok": True,
        "query": query,
        "results": output['links'],
    }


@app.post("/file/upload")
async def upload_files(file: UploadFile = File(...), ):
    # 取后缀
    suffix = Path(file.filename).suffix.lower()
    root_name = Path(file.filename).stem

    file_name = f'{root_name}{suffix}'
    if suffix == '.ppt' or suffix == '.pptx':
        file_dir = PPT_DIR / file_name
    elif suffix == '.pdf':
        file_dir = PDF_DIR / file_name
    else:
        file_dir = DOC_DIR / file_name

    with file_dir.open('wb') as f:
        shutil.copyfileobj(file.file, f)

    return {
        'ok': True,
        'file': file_name,
    }




@app.post("/agent/summary")
def summary(file_name: str):

    chunk_list = build_chunks(file_name)
    _summary = ''
    if file_name.endswith('.ppt') or file_name.endswith('.pptx'):
        _summary = summarize_ppt(chunk_list, file_name)
    elif file_name.endswith('.pdf'):
        _summary = summarize_pdf(chunk_list, file_name)
    else:
        _summary = summarize_doc(chunk_list, file_name)

    return {
        "ok": True,
        "file": file_name,
        "summary": _summary,
    }

@app.get("/file/get_file_list")
def get_files():

    file_list = []
    file_list += [x.name for x in PPT_DIR.iterdir() if x.is_file()]
    file_list += [x.name for x in PDF_DIR.iterdir() if x.is_file()]
    file_list += [x.name for x in DOC_DIR.iterdir() if x.is_file()]

    resp_list = []

    for file in file_list:
        resp_list.append({
            "file_name": file,
            'access_method':f'file/get_file/{file}'
        })

    return {
        "ok": True,
        "file_list": resp_list,
    }
@app.get("/file/get_file/{file_name}")
async def get_file(file_name: str):

    if file_name.endswith('.ppt') or file_name.endswith('.pptx'):
        file_dir = PPT_DIR / file_name
        return FileResponse(file_dir, media_type='application/octet-stream')
    elif file_name.endswith('.pdf'):
        file_dir = PDF_DIR / file_name
        return FileResponse(file_dir, media_type='application/octet-stream')
    else:
        file_dir = DOC_DIR / file_name
        return FileResponse(file_dir, media_type='application/octet-stream')


# ==================== 深度搜索 + 爬虫集成 API ====================

class DeepSearchAndCrawlRequest(BaseModel):
    """深度搜索并爬取请求"""
    query: str
    max_urls: Optional[int] = 10  # 最多爬取的URL数量
    crawl_timeout: Optional[int] = 30  # 单个URL爬取超时（秒）
    api_timeout: Optional[int] = 1800  # API总超时（秒，默认30分钟）


@app.post("/agent/deepsearch-and-crawl")
async def deepsearch_and_crawl(request: DeepSearchAndCrawlRequest):
    """
    深度搜索并爬取URL内容
    
    流程：
    1. 使用深度搜索获取相关URL
    2. 使用爬虫模块爬取URL内容
    3. 清洗和格式化内容
    4. 保存结果并返回
    
    注意：此操作可能需要较长时间（5-10分钟），请耐心等待
    """
    import time
    start_time = time.time()
    
    try:
        print(f"[API] 开始处理请求: query={request.query}, max_urls={request.max_urls}")
        # 步骤1: 深度搜索获取URL
        print(f"[API] 步骤1/4: 开始深度搜索...")
        search_start = time.time()
        search_result = deepsearch_large_llm(request.query)
        search_time = time.time() - search_start
        print(f"[API] 深度搜索完成，耗时: {search_time:.2f}秒")
        
        if not search_result or not search_result.get('links'):
            return JSONResponse(
                status_code=200,
                content={
                    "ok": False,
                    "message": "深度搜索未找到相关链接",
                    "query": request.query
                }
            )
        
        urls = search_result['links']
        
        # 限制URL数量
        if request.max_urls:
            urls = urls[:request.max_urls]
        
        # 步骤2: 爬取URL内容
        print(f"[API] 步骤2/4: 开始爬取 {len(urls)} 个URL...")
        crawl_start = time.time()
        crawler_service = get_crawler_service()
        crawl_batch = crawler_service.crawl_urls(
            urls=urls,
            query=request.query,
            max_urls=request.max_urls,
            timeout_per_url=request.crawl_timeout
        )
        crawl_time = time.time() - crawl_start
        print(f"[API] 爬取完成，耗时: {crawl_time:.2f}秒，成功: {crawl_batch.success_count}, 失败: {crawl_batch.failed_count}")
        
        # 步骤3: 清洗内容
        print(f"[API] 步骤3/4: 开始清洗内容...")
        clean_start = time.time()
        content_cleaner = ContentCleaner()
        cleaned_results = []
        
        for result in crawl_batch.results:
            if result.status == "success" and result.file_path:
                if result.content_type == "pdf":
                    # 清洗PDF内容
                    cleaned = content_cleaner.clean_pdf_content(result.file_path)
                else:
                    # 清洗文本内容
                    cleaned = content_cleaner.clean_text_content(
                        result.content or "",
                        result.file_path
                    )
                
                # 更新结果
                if "cleaned_content" in cleaned:
                    result.content = cleaned.get("cleaned_content", "")
                    result.metadata.update(cleaned.get("metadata", {}))
            
            cleaned_results.append({
                "url": result.url,
                "title": result.title,
                "content": result.content[:2000] if result.content else None,  # 限制返回长度
                "content_type": result.content_type,
                "status": result.status,
                "error_message": result.error_message,
                "metadata": result.metadata,
                "file_path": result.file_path
            })
        
        clean_time = time.time() - clean_start
        print(f"[API] 内容清洗完成，耗时: {clean_time:.2f}秒")
        
        # 步骤4: 保存结果
        print(f"[API] 步骤4/4: 保存结果...")
        storage_service = get_storage_service()
        batch_id = storage_service.save_crawl_batch(crawl_batch)
        
        total_time = time.time() - start_time
        print(f"[API] 全部完成! 总耗时: {total_time:.2f}秒")
        
        # 返回格式与前端期望一致
        return {
            "ok": True,
            "query": request.query,
            "batch_id": batch_id,
            "total_urls": crawl_batch.total_urls,
            "success_count": crawl_batch.success_count,
            "failed_count": crawl_batch.failed_count,
            "links": urls,  # 搜索到的链接列表
            "created_at": crawl_batch.created_at.isoformat() if hasattr(crawl_batch.created_at, 'isoformat') else None,
            # 同时返回详细结果（可选，前端可以选择使用）
            "results": cleaned_results
        }
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": f"处理失败: {str(e)}",
                "query": request.query
            }
        )


@app.get("/agent/crawl-results/{batch_id}")
async def get_crawl_results(batch_id: str):
    """获取爬取结果"""
    storage_service = get_storage_service()
    batch_result = storage_service.load_crawl_batch(batch_id)
    
    if not batch_result:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "message": "批次不存在"
            }
        )
    
    return {
        "ok": True,
        "batch_id": batch_id,
        "query": batch_result.query,
        "total_urls": batch_result.total_urls,
        "success_count": batch_result.success_count,
        "failed_count": batch_result.failed_count,
        "created_at": batch_result.created_at.isoformat(),
        "results": [
            {
                "url": r.url,
                "title": r.title,
                "content": r.content[:2000] if r.content else None,
                "content_type": r.content_type,
                "status": r.status,
                "error_message": r.error_message,
                "metadata": r.metadata,
                "file_path": r.file_path
            }
            for r in batch_result.results
        ]
    }


@app.get("/agent/crawl-history")
async def get_crawl_history(limit: int = 20):
    """获取爬取历史"""
    storage_service = get_storage_service()
    batches = storage_service.list_batches(limit=limit)
    
    return {
        "ok": True,
        "batches": batches
    }






if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8848)