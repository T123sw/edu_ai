import os
import requests
import time

# 你的 FastAPI 服务地址
API_URL = "http://127.0.0.1:8000/api/rag/import"
# 你之前爬虫存放 Markdown 文件的目录
FOLDER_PATH = ".\data\input\md_chunks_qy\md_chunks"


def batch_upload():
    if not os.path.exists(FOLDER_PATH):
        print(f"文件夹 {FOLDER_PATH} 不存在！")
        return

    md_files = [f for f in os.listdir(FOLDER_PATH) if f.endswith(".md")]
    print(f"[*] 共发现 {len(md_files)} 个 Markdown 文件，准备开始批量入库...")

    success_count = 0
    for filename in md_files:
        file_path = os.path.join(FOLDER_PATH, filename)
        print(f"  -> 正在上传: {filename}...")

        try:
            with open(file_path, "rb") as f:
                # 构造 multipart/form-data 请求
                files = {"file": (filename, f, "text/markdown")}
                response = requests.post(API_URL, files=files)

                if response.status_code == 200:
                    print(f"     [√] 成功! 库中新增 {response.json().get('chunk_count', 0)} 个知识块")
                    success_count += 1
                else:
                    print(f"     [X] 失败! 状态码: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"     [X] 发生异常: {e}")

        # 稍微停顿一下，防止请求过快触发 Gemini 的限流
        time.sleep(1)

    print(f"[*] 批量入库完成！成功上传 {success_count}/{len(md_files)} 个文件。")


if __name__ == "__main__":
    batch_upload()