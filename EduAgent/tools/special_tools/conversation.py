import base64
import mimetypes
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool


from src.llms import get_llm_by_type


@tool
def talk_to_ocean_expert(chat: str) -> str:
    """
    跟海洋领域的专家进行有历史记忆的交谈（通过本机 SSH 隧道转发到远端开源模型）
    依赖：requests, langchain_core.messages (SystemMessage/HumanMessage/AIMessage)
    """
    import requests
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    # ---- 配置：本机端口转发后的 OpenAI-style API ----
    REMOTE_MODEL_API_BASE = "http://127.0.0.1:8001/v1"
    LLM_MODEL = "Qwen3-8B-ocean-1"

    # ---- 维护全局历史 ----
    global ocean_history
    if "ocean_history" not in globals() or ocean_history is None:
        ocean_history = [SystemMessage(content="你是一名海洋与水声领域的学者，你会充分回答用户的问题")]

    ocean_history.append(HumanMessage(content=chat, name="o_agent"))

    # ---- LangChain messages -> OpenAI messages ----
    def _to_openai_msgs(hist):
        out = []
        for m in hist:
            if isinstance(m, SystemMessage):
                role = "system"
            elif isinstance(m, HumanMessage):
                role = "user"
            elif isinstance(m, AIMessage):
                role = "assistant"
            else:
                role = "user"
            out.append({"role": role, "content": str(getattr(m, "content", ""))})
        return out

    url = f"{REMOTE_MODEL_API_BASE}/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "messages": _to_openai_msgs(ocean_history),
        "temperature": 0.5,
        "stream": False,
    }

    # 如果你服务端有 token，就打开下面两行
    headers = {"Content-Type": "application/json"}
    # headers["Authorization"] = "Bearer YOUR_TOKEN"

    r = requests.post(url, json=payload, headers=headers, timeout=180)
    r.raise_for_status()
    j = r.json()

    resp_text = j["choices"][0]["message"]["content"]

    # ---- 写回历史，形成“有记忆”的专家 ----
    ocean_history.append(AIMessage(content=resp_text))

    return "expert:" + resp_text



def _file_to_data_url(file_path: Path) -> str:
    """把本地图片转成 data URL，便于 OpenAI-style multimodal 输入。"""
    mime, _ = mimetypes.guess_type(str(file_path))
    if mime is None:
        # 兜底：常见图片
        mime = "image/png"
    b64 = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

@tool
def explain_image_file(file_name: str) -> str:
    """
    使用多模态模型来对图像进行深刻的解释。
    :param file_name: 图像文件的名字（包含后缀）
    :return: 文字解释
    """
    # 1) 定位文件
    uploads_dir = Path(__file__).parent.parent.parent.parent / "uploads"
    file_path = uploads_dir / file_name

    if not file_path.exists():
        return f"ERROR: file not found: {file_path}"
    if not file_path.is_file():
        return f"ERROR: not a file: {file_path}"

    # 2) 转成 data url（无需公网）
    try:
        data_url = _file_to_data_url(file_path)
    except Exception as e:
        return f"ERROR: failed to read/encode image: {repr(e)}"

    # 3) 构造多模态消息（OpenAI-compatible 格式）
    system = SystemMessage(content=(
        "你是严谨的视觉分析助手。请对图片做“尽可能细致、可复现”的描述。\n"
        "要求：\n"
        "1) 先给一句总体概述；\n"
        "2) 再按条列出主要对象/区域（位置、外观、数量、关系）；\n"
        "3) 如果有文字/表格/代码/公式，尽量逐字转写；\n"
        "4) 不要编造看不到的细节；不确定要明确标注“不确定/可能”。"
    ))

    user = HumanMessage(content=[
        {"type": "text", "text": "请详细解释这张图片。"},
        {"type": "image_url", "image_url": {"url": data_url}},
    ])

    # 4) 调用 qwen-vl-max（LangChain ChatModel）
    # 你 get_llm_by_type 的签名我按你现有用法：get_llm_by_type(vendor, model, temperature)
    # 如果你封装支持 max_tokens/model_kwargs，建议加上，避免输出被截断
    vlm = get_llm_by_type("qwen", "qwen-vl-max", temperature=0.2)

    try:
        resp = vlm.invoke([system, user])
    except Exception as e:
        return f"ERROR: vlm invoke failed: {repr(e)}"

    # 5) 兼容不同返回类型
    # LangChain 的 AIMessage 一般在 resp.content
    content = getattr(resp, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    return f"ERROR: empty response, raw={resp!r}"


@tool
def explain_audio_file(file_name: str) -> str:
    """
    使用音频多模态模型来解释音频文件（内容、事件、说话人、情绪、背景声等）
    输入：uploads 目录下音频文件名（.wav/.mp3/.m4a 等）
    输出：对音频的详细描述与分析
    """
    uploads_dir = Path(__file__).parent.parent.parent.parent / "uploads"
    file_path = uploads_dir / file_name

    if not file_path.exists():
        return f"ERROR: file not found: {file_path}"
    if not file_path.is_file():
        return f"ERROR: not a file: {file_path}"

    # wav/mp3/m4a 等通常都能识别；识别不到就按 audio/wav 兜底
    try:
        data_url = _file_to_data_url(file_path, default_mime="audio/wav")
    except Exception as e:
        return f"ERROR: failed to read/encode audio: {repr(e)}"

    system = SystemMessage(content=(
        "你是严谨的音频分析助手。请对音频做“尽可能细致、可复现”的解释。\n"
        "要求：\n"
        "1) 先给一句总体概述（这段音频大致是什么）；\n"
        "2) 列出主要声音事件（按时间顺序，描述发生了什么、可能来源）；\n"
        "3) 若有人声：尽量转写关键内容（不确定就标注不确定），并描述语气/情绪；\n"
        "4) 描述背景声/噪声/环境（室内室外、交通、人群、机器等）；\n"
        "5) 不要编造听不到的细节；不确定要明确写“不确定/可能”。"
    ))

    user = HumanMessage(content=[
        {"type": "text", "text": "请详细解释这段音频。"},
        {"type": "audio_url", "audio_url": {"url": data_url}},
    ])

    # 选音频模型：按你封装约定来
    # 常见写法：qwen2-audio-instruct / qwen2-audio-7b-instruct 等
    audio_llm = get_llm_by_type("qwen", "qwen2-audio-instruct", temperature=0.2)

    try:
        resp = audio_llm.invoke([system, user])
    except Exception as e:
        return f"ERROR: audio llm invoke failed: {repr(e)}"

    content = getattr(resp, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    return f"ERROR: empty response, raw={resp!r}"





