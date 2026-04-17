import os
import re
import json
import uuid
import traceback
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List
import requests
from openai import OpenAI

# 导入离线视频生成核心逻辑 (确保 offline_video_maker.py 在同级目录)
from offline_video_maker import build_course_video

# ==========================================
# 系统初始化与跨域配置
# ==========================================
app = FastAPI(
    title="AI Lecturer 网关",
    description="包含【在线实时课堂交互】与【离线整套课件一键生成】的统一后端 API。",
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 全局环境配置
# ==========================================
QWEN_API_KEY = "sk-584341a48ac641668f188a42be9fa2ec"
LIVETALKING_URL = "http://127.0.0.1:8010/human"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 临时数据库
COURSE_DB = {}
OFFLINE_TASK_DB = {}
global_course_counter = 1000

TEMP_DIR = os.path.join(BASE_DIR, "temp_export")
os.makedirs(TEMP_DIR, exist_ok=True)


def split_into_sentences(text: str) -> list:
    """工具函数：将长段落切分为单句，方便逐句播报与打断"""
    parts = re.split(r'([。？！.?!])', text)
    sentences = []
    for i in range(0, len(parts)-1, 2):
        s = (parts[i] + parts[i+1]).strip()
        if len(s) > 1: sentences.append(s)
    if len(parts) % 2 != 0 and len(parts[-1].strip()) > 1:
        sentences.append(parts[-1].strip())
    return sentences

# ==============================================================================
# 🟢 模块 A: 在线实时课堂 (Online Interaction)
# ==============================================================================

class InjectCourseRequest(BaseModel):
    course_name: str = Field(..., description="课程名称")
    raw_document: str = Field(..., description="输入的 content.md 原文")

class ClassRequest(BaseModel):
    course_title: str
    current_slide_content: str
    page_index: int
    total_pages: int

class SpeakRequest(BaseModel):
    text: str
    session_id: int

class StopRequest(BaseModel):
    session_id: int

class InterruptRequest(BaseModel):
    question: str
    slide_context: str = ""        
    interrupted_sentence: str = "" 
    session_id: int


@app.post("/api/v1/online/create_course", tags=["🟢 在线课堂模块"])
async def create_course(request: InjectCourseRequest):
    """【业务入口】输入 MD 文档，大模型自动解析为 PPT 页结构"""
    global global_course_counter
    client = OpenAI(api_key=QWEN_API_KEY, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    system_prompt = "你是一个教案解析引擎。请将输入的讲义大纲按照逻辑段落拆分为PPT页面。必须返回纯JSON数组，格式：[{\"title\": \"页标题\", \"content\": \"内容要点\"}]"
    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": request.raw_document}],
            temperature=0.3
        )
        res_text = completion.choices[0].message.content.strip()
        # 清理可能携带的 Markdown 代码块标签
        if res_text.startswith("```json"): 
            res_text = res_text[7:]
        if res_text.endswith("```"): 
            res_text = res_text[:-3]
            
        outline = json.loads(res_text.strip())
        
        global_course_counter += 1
        course_id = str(global_course_counter)
        COURSE_DB[course_id] = {"course_name": request.course_name, "outline": outline}
        return {"code": 200, "data": {"course_id": course_id, "pages": outline}}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="解析课程失败")
    

@app.get("/api/v1/online/get_course/{course_id}", tags=["🟢 在线课堂模块"])
async def get_course(course_id: str):
    """【获取课件】前端通过此接口拉取已解析的课程大纲，用于驱动后续的自动讲课"""
    if course_id not in COURSE_DB:
        raise HTTPException(status_code=404, detail="课程数据在内存中不存在，请先调用 create_course")
    return {"code": 200, "data": COURSE_DB[course_id]}



@app.post("/api/v1/online/generate_script", tags=["🟢 在线课堂模块"])
async def generate_script(request: ClassRequest):
    """【智能备课】动态生成当前 PPT 页的讲稿口语"""
    client = OpenAI(api_key=QWEN_API_KEY, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    system_prompt = (
        f"你是一位学术严谨的大学教授。正在讲授《{request.course_title}》。\n"
        "【输出格式】：5-10句话。每句15-25字，必须以句号或问号结尾。严禁Markdown排版。"
        "【严禁使用公式代码】：避免使用任何 LaTeX、Markdown标签。将数学符号转化为自然中文口语读法。"   
    )
    if request.page_index == 0: system_prompt += "\n当前为开场，请简要介绍目标。"
    elif request.page_index == request.total_pages - 1: system_prompt += "\n当前为结尾，请概括核心并宣布下课。"

    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"【本页核心点】：{request.current_slide_content}\n请输出讲稿："}],
            temperature=0.7 
        )
        sentences = split_into_sentences(completion.choices[0].message.content)
        return {"code": 200, "data": {"sentences": sentences}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/online/speak_sentence", tags=["🟢 在线课堂模块"])
async def speak_sentence(request: SpeakRequest):
    """【画面驱动】发送文本，让 WebRTC 端的数字人开口说话"""
    try:
        requests.post(LIVETALKING_URL, json={"text": request.text, "type": "echo", "interrupt": False, "sessionid": request.session_id}, timeout=3)
        return {"code": 200, "message": "指令已发送给渲染引擎"}
    except requests.exceptions.RequestException:
        return {"code": 502, "detail": "Render engine unreachable"}

@app.post("/api/v1/online/stop_speaking", tags=["🟢 在线课堂模块"])
async def stop_speaking(request: StopRequest):
    """【打断机制 1】硬中断：立刻让数字人闭嘴"""
    try:
        requests.post(LIVETALKING_URL.replace("/human", "/interrupt_talk"), json={"sessionid": request.session_id}, timeout=2)
        return {"code": 200}
    except requests.exceptions.RequestException:
        return {"code": 502, "detail": "Failed to halt render engine"}

@app.post("/api/v1/online/interrupt_and_ask", tags=["🟢 在线课堂模块"])
async def interrupt_and_ask(request: InterruptRequest):
    """【打断机制 2】处理学生提问，数字人当场语音解答"""
    client = OpenAI(api_key=QWEN_API_KEY, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    system_prompt = (
        "你是一位严谨的大学教授，被学生提问打断。\n"
        f"【上下文】：{request.slide_context}\n"
        f"【被打断语句】：{request.interrupted_sentence}\n"
        "要求：用2-3句严谨学术语言解答。解答后用一句自然的话过渡回刚才的话题。"
    )
    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"学生提问：{request.question}"}],
            temperature=0.6
        )
        answer = completion.choices[0].message.content
        requests.post(LIVETALKING_URL, json={"text": answer, "type": "echo", "interrupt": True, "sessionid": request.session_id}, timeout=5)
        return {"code": 200, "data": {"answer": answer}}
    except Exception:
        return {"code": 500, "detail": "Interactive response failed"}


# ==============================================================================
# 🟠 模块 B: 离线视频一键生成 (Offline Video)
# ==============================================================================

class SlidePage(BaseModel):
    ppt_image_path: str = Field(..., description="该页PPT的图片绝对路径")
    content_text: str = Field(..., description="该页PPT的大纲提示词")

class FullCourseVideoRequest(BaseModel):
    course_title: str = Field(..., description="总课程名称")
    pages: List[SlidePage] = Field(..., description="整套 PPT 的页面列表组合")

def background_full_course_worker(task_id: str, request: FullCourseVideoRequest):
    """后台执行整套课程的渲染与无缝拼接"""
    output_filename = os.path.join(TEMP_DIR, f"{task_id}.mp4")
    try:
        print(f"[Offline] 开始处理整套课程视频任务：{task_id}...")
        
        # 组装适配离线核心引擎的数据结构
        pages_data = [
            {"ppt_image": page.ppt_image_path, "outline_prompt": page.content_text} 
            for page in request.pages
        ]
        
        # 呼叫底层的离线视频流水线 (支持多页合并)
        build_course_video(request.course_title, pages_data, output_filename)
        
        OFFLINE_TASK_DB[task_id] = {
            "status": "success", 
            "video_url": f"/api/v1/offline/download/{task_id}.mp4"
        }
        print(f"[Offline] 任务 {task_id} 完整渲染合并成功！")
    except Exception as e:
        OFFLINE_TASK_DB[task_id] = {"status": "failed", "error": str(e)}
        print(f"[Offline] 任务 {task_id} 渲染失败: {str(e)}")

@app.post("/api/v1/offline/generate_full_video", tags=["🟠 离线渲染一键成片"])
async def generate_full_course_video(request: FullCourseVideoRequest, bg_tasks: BackgroundTasks):
    """
    【一键成片】
    输入一整套 PPT 图片数组和对应大纲，系统将在后台异步渲染，并自动拼接为一个完整的 MP4 教学大片。
    立即返回 task_id 用于轮询进度。
    """
    task_id = f"course_{uuid.uuid4().hex[:8]}"
    OFFLINE_TASK_DB[task_id] = {"status": "processing"}
    
    # 压入后台处理队列
    bg_tasks.add_task(background_full_course_worker, task_id, request)
    
    return {"code": 200, "message": "整套课程视频已加入后台合成队列", "task_id": task_id}

@app.get("/api/v1/offline/status/{task_id}", tags=["🟠 离线渲染一键成片"])
async def get_video_status(task_id: str):
    """【凭号取餐】查询整套课程视频的合成进度与最终下载链接"""
    task_info = OFFLINE_TASK_DB.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task ID 无效或未找到")
    return {"code": 200, "data": task_info}


@app.get("/api/v1/offline/download/{filename}", tags=["🟠 离线渲染一键成片"])
async def download_video(filename: str):
    """【下载通道】将硬盘里的 MP4 文件转化为网络流，触发前端浏览器下载"""
    # 拼凑出文件在 temp_export 文件夹里的真实路径
    video_path = os.path.join(TEMP_DIR, filename)
    
    # 拦截机制：如果文件还没生成、丢失或者名字传错了，报 404 错误
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="视频文件不存在或已丢失")
        
    # 核心动作：把物理文件以视频流的形式顺着网线发出去，filename 参数会告诉浏览器默认的下载文件名
    return FileResponse(
        path=video_path, 
        filename=filename, 
        media_type="video/mp4"
    )


# ==========================================
#  启动命令
# ==========================================
if __name__ == "__main__":
    import uvicorn
    print("\n==================================================")
    print("  AI Lecturer Central Gateway  启动中...")
    print("  监听端口: 8008")
    print("==================================================")
    uvicorn.run(app, host="0.0.0.0", port=8008)