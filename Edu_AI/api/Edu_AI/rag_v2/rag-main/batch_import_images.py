import os
import requests
import time
import mimetypes

# 刚才写好的多模态图片上传接口地址
API_URL = "http://127.0.0.1:8000/api/rag/import_image"
# 你存放待上传图片的文件夹
FOLDER_PATH = "./data/input/input_images/images"


def batch_upload_images():
    if not os.path.exists(FOLDER_PATH):
        print(f"[-] 文件夹 {FOLDER_PATH} 不存在！请先创建并放几张图片进去。")
        return

    # 支持的图片格式
    valid_extensions = (".jpg", ".jpeg", ".png")
    image_files = [f for f in os.listdir(FOLDER_PATH) if f.lower().endswith(valid_extensions)]

    if not image_files:
        print(f"[-] 在 {FOLDER_PATH} 中没有找到图片文件。")
        return

    print(f"[*] 共发现 {len(image_files)} 张图片，准备开始批量多模态入库...")

    success_count = 0
    for filename in image_files:
        file_path = os.path.join(FOLDER_PATH, filename)
        print(f"  -> 正在处理并上传图片: {filename}...")

        try:
            # 猜测图片的 MIME 类型 (image/jpeg 或 image/png)
            mime_type, _ = mimetypes.guess_type(file_path)
            mime_type = mime_type or "image/jpeg"

            with open(file_path, "rb") as f:
                # 构造 multipart/form-data 请求，模拟网页上的“选择文件”上传
                files = {"file": (filename, f, mime_type)}
                response = requests.post(API_URL, files=files)

                if response.status_code == 200:
                    result = response.json()
                    print(f"     [√] 成功! {result.get('message')}")
                    success_count += 1
                else:
                    print(f"     [X] 失败! 状态码: {response.status_code}, 报错: {response.text}")
        except Exception as e:
            print(f"     [X] 发生异常: {e}")

        # ⚠️ 极度重要：由于 Gemini 提取图片向量计算量较大，建议停顿 2-3 秒防限流
        time.sleep(2)

    print(f"[*] 批量图片入库完成！成功上传 {success_count}/{len(image_files)} 张。")


if __name__ == "__main__":
    batch_upload_images()