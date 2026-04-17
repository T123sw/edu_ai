import os
import sys
import time
import shutil
import subprocess
from openai import OpenAI

# ==========================================
# 全局配置参数
# ==========================================
QWEN_API_KEY = "sk-584341a48ac641668f188a42be9fa2ec"  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WAV2LIP_DIR = os.path.join(BASE_DIR, "Wav2Lip_Offline") 
FFMPEG_EXE = "ffmpeg"  
BASE_AVATAR_VIDEO = os.path.join(BASE_DIR, "assets", "avatar_white.mp4") 
TEMP_DIR = os.path.join(BASE_DIR, "temp_export")

os.makedirs(TEMP_DIR, exist_ok=True)

# ==========================================
# 核心业务逻辑
# ==========================================

def generate_script_from_llm(course_title, slide_prompt):
    """
    调用大语言模型生成当前幻灯片的讲稿。
    
    Args:
        course_title (str): 课程标题。
        slide_prompt (str): 本页的核心大纲提示词。
        
    Returns:
        str: 生成的文本讲稿。
    """
    print(f"[LLM] 开始生成讲稿，输入提示词: {slide_prompt[:15]}...")
    client = OpenAI(
        api_key=QWEN_API_KEY, 
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", 
        timeout=60.0
    )
    
    system_prompt = (
        f"你是一位学术严谨的大学教授。正在讲授《{course_title}》。\n"
        "【输出格式】：5-10句话。每句15-25字，必须以句号或问号结尾。严禁Markdown排版。\n"
        "【严禁使用公式代码】：避免使用任何 LaTeX、Markdown、HTML 标签或数学符号,如果有需要，转化为自然的中文口语读法。"
    )
    
    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【本页核心点】：{slide_prompt}\n请输出讲稿："}
            ],
            temperature=0.7
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM Error] 生成失败: {e}")
        return "不好意思，这部分内容的讲稿生成出错了。"


def text_to_speech(text, output_audio_path):
    """
    将文本转换为语音文件，包含防阻断重试机制。
    
    Args:
        text (str): 需要转换的文本。
        output_audio_path (str): 输出音频文件的绝对路径。
    """
    print("[TTS] 开始调用 Edge-TTS 生成音频...")
    cmd = [
        sys.executable, "-m", "edge_tts", 
        "--text", text, 
        "--write-media", output_audio_path, 
        "--voice", "zh-CN-XiaoxiaoNeural"
    ]
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("[TTS] 音频生成成功。")
                return output_audio_path
            else:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, output=result.stdout, stderr=result.stderr
                )
        except Exception as e:
            print(f"[TTS Warning] 连接异常，准备重试 ({attempt + 1}/{max_retries})...")
            time.sleep(3) 
            
    error_msg = "[TTS Error] 达到最大重试次数，Edge-TTS 网络连接彻底失败。"
    print(error_msg)
    raise RuntimeError(error_msg) # 抛出运行时异常，让外层的 FastAPI 捕获，从而更新任务状态为 failed


def render_wav2lip_offline(audio_path, output_video_path):
    """
    调用 Wav2Lip 底层模型进行唇形同步渲染。
    
    Args:
        audio_path (str): 输入音频路径。
        output_video_path (str): 输出视频路径。
    """
    print("[Wav2Lip] 开始执行视频唇形同步渲染...")
    cmd = [
        sys.executable, "inference.py", 
        "--checkpoint_path", "checkpoints/wav2lip.pth", 
        "--face", os.path.abspath(BASE_AVATAR_VIDEO), 
        "--audio", os.path.abspath(audio_path), 
        "--outfile", os.path.abspath(output_video_path),
        "--face_det_batch_size", "4", 
        "--wav2lip_batch_size", "128"
    ]
    subprocess.run(cmd, cwd=WAV2LIP_DIR, check=True)
    return output_video_path


def composite_pip_video(ppt_image_path, avatar_video_path, output_mp4_path):
    """
    将数字人视频作为画中画层叠至幻灯片图像上，并执行背景色键抠除。
    
    Args:
        ppt_image_path (str): 背景幻灯片图像路径。
        avatar_video_path (str): 带有纯色背景的数字人视频路径。
        output_mp4_path (str): 合成后视频的输出路径。
    """
    print("[FFmpeg] 开始执行视频层叠与色键混合...")
    
    # 滤镜参数说明：
    # 1. 确保背景图像长宽为偶数，兼容 H.264 编码规范。
    # 2. 对数字人视频应用 colorkey 滤镜移除纯白背景 (0xFFFFFF)，并进行等比缩放。
    # 3. 将数字人覆盖至背景右下角，视频长度由最短流 (shortest=1) 决定。
    filter_complex = (
        "[0:v]scale=trunc(iw/2)*2:trunc(ih/2)*2[bg];"
        "[1:v]colorkey=0xFFFFFF:0.1:0.1,scale=320:-2[transparent_avatar];"
        "[bg][transparent_avatar]overlay=W-w-20:H-h-20:shortest=1"
    )
    
    cmd = [
        FFMPEG_EXE, '-y',
        '-loop', '1', '-i', os.path.abspath(ppt_image_path),   
        '-i', os.path.abspath(avatar_video_path),                                   
        '-filter_complex', filter_complex,
        '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p',
        os.path.abspath(output_mp4_path)
    ]
    subprocess.run(cmd, check=True)
    return output_mp4_path


def merge_all_videos(video_list, final_output_path):
    """
    拼接所有分段视频为一个完整的输出文件。
    
    Args:
        video_list (list): 视频路径列表。
        final_output_path (str): 最终合成的视频路径。
    """
    print(f"[FFmpeg] 正在合并 {len(video_list)} 个分段视频...")
    list_file_path = os.path.join(TEMP_DIR, "merge_list.txt")
    
    with open(list_file_path, 'w', encoding='utf-8') as f:
        for vid in video_list:
            safe_path = os.path.abspath(vid).replace('\\', '/')
            f.write(f"file '{safe_path}'\n")
            
    cmd = [
        FFMPEG_EXE, '-y', '-f', 'concat', '-safe', '0', 
        '-i', list_file_path, '-c', 'copy', 
        os.path.abspath(final_output_path)
    ]
    subprocess.run(cmd, check=True)
    print(f"[System] 合并完成。输出文件: {os.path.abspath(final_output_path)}")


def build_course_video(course_title, pages_data, final_output_filename):
    """
    项目主控流程。遍历课件数据并按序调用各子模块。
    """
    print("=" * 50)
    print(f"初始化项目: 《{course_title}》")
    print("=" * 50)
    
    final_segments = []
    for i, page in enumerate(pages_data):
        print(f"\n--- 处理进度: 第 {i+1}/{len(pages_data)} 页 ---")
        ppt_img = page['ppt_image']
        prompt = page['outline_prompt']
        
        if not os.path.exists(ppt_img):
            print(f"[Warning] 图像资源缺失，跳过此页: {ppt_img}")
            continue
            
        temp_audio = os.path.join(TEMP_DIR, f"audio_p{i}.wav")
        temp_avatar = os.path.join(TEMP_DIR, f"avatar_p{i}.mp4")
        temp_page_video = os.path.join(TEMP_DIR, f"final_p{i}.mp4")
        
        # 核心管线执行
        script = generate_script_from_llm(course_title, prompt)
        text_to_speech(script, temp_audio)
        render_wav2lip_offline(temp_audio, temp_avatar)
        composite_pip_video(ppt_img, temp_avatar, temp_page_video)
        
        final_segments.append(temp_page_video)
        
    if final_segments:
        merge_all_videos(final_segments, final_output_filename)


if __name__ == "__main__":
    # 测试用例定义
    test_course_title = "计算机网络基础"
    test_pages_data = [
        {
            "ppt_image": os.path.join(BASE_DIR, "assets", "slide1.png"), 
            "outline_prompt": "第一页大纲：介绍TCP/IP模型，强调它是互联网的基石，分为四层结构。"
        },
        {
            "ppt_image": os.path.join(BASE_DIR, "assets", "slide2.png"), 
            "outline_prompt": "第二页大纲：详细讲解三次握手。要点：说明建立连接的可靠性，用打电话的例子类比。"
        }
    ]
    build_course_video(test_course_title, test_pages_data, "ai_lecturer.mp4")