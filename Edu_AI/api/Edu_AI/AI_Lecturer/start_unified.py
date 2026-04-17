import os
import subprocess
import time
import webbrowser

# 动态获取当前根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def start_engines():
    """启动底层渲染引擎和统一网关"""
    print("==================================================")
    print("        AI 讲师系统 - 终极统一启动器")
    print("==================================================")

    # 1. 启动底层渲染引擎 (8010) - 负责在线模块的画面和声音
    print("\n[1/3] 正在唤醒 LiveTalking 底层引擎 (8010端口)...")
    livetalking_dir = os.path.join(BASE_DIR, "LiveTalking-main")
    cmd1 = f'call conda activate nerfstream && cd /d "{livetalking_dir}" && set HF_ENDPOINT=https://hf-mirror.com && python app.py --transport webrtc --model wav2lip --avatar_id my_teacher --tts edgetts --REF_FILE zh-CN-XiaoxiaoNeural'
    subprocess.Popen(f'start "LiveTalking 渲染引擎 (8010)" cmd /k "{cmd1}"', shell=True)

    print("      ⏳ 等待底层引擎加载大模型 (约8秒)...")
    time.sleep(8)

    # 2. 启动统一网关 (调用你刚刚新建的 unified_gateway.py)
    print("\n[2/3] 正在唤醒 Unified Gateway 统一网关...")
    # ⚠️ 注意：这里直接调用 unified_gateway.py
    cmd2 = f'call conda activate nerfstream && cd /d "{BASE_DIR}" && python unified_gateway.py'
    subprocess.Popen(f'start "统一网关 (全栈接口)" cmd /k "{cmd2}"', shell=True)

    print("      ⏳ 等待 API 中枢挂载就绪 (约4秒)...")
    time.sleep(4)

def open_dashboard():
    """直接为你打开接口测试文档页面"""
    print("\n[3/3] 🌐 正在为你打开 API 接口交接文档网页...")
    
    # ⚠️ 注意：如果你之前的 unified_gateway.py 最后一行写的是 port=8008，这里就是 8008。
    # 如果你把它改成了 port=8000，请把下面的链接也改成 8000。
    webbrowser.open("http://127.0.0.1:8008/docs")
    
    print("\n✅ 所有服务均已启动！可以在弹出的网页中测试在线和离线功能了。")
    print("==================================================")

if __name__ == "__main__":
    start_engines()
    open_dashboard()