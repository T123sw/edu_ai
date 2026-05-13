# 视频入库优化方案

## 问题分析

当前视频入库失败的原因：
1. **文件过大**：94MB 视频 Base64 编码后约 125MB，传输和处理耗时长
2. **超时不足**：原 60 秒超时对大文件不够
3. **API 限制**：gemini-embedding-preview 对输入大小可能有限制
4. **内存占用**：一次性加载整个视频到内存

## 已实施方案（方案1）

### 改进内容
- ✅ 文件大小检查：默认限制 50MB（可通过 `VIDEO_MAX_SIZE_MB` 环境变量调整）
- ✅ 动态超时：基础 120 秒 + 每 10MB 增加 30 秒
- ✅ 友好错误提示：超大文件会提示使用 ffmpeg 压缩

### 环境变量配置
```bash
# .env 文件
VIDEO_MAX_SIZE_MB=50              # 视频文件大小限制（MB）
VIDEO_EMBEDDING_TIMEOUT=120       # 基础超时时间（秒）
```

### 视频压缩命令
```bash
# 压缩到约 500kbps 码率
ffmpeg -i input.mp4 -vcodec h264 -acodec aac -b:v 500k output.mp4

# 压缩到指定大小（如 30MB）
ffmpeg -i input.mp4 -fs 30M output.mp4
```

## 进阶方案（可选）

### 方案2：视频抽帧 + 多帧融合
将视频拆分为关键帧，对每帧单独 embedding，然后融合向量：

**优点**：
- 突破单次请求大小限制
- 更好捕捉视频时序信息
- 可并行处理提升速度

**实现思路**：
```python
# 使用 opencv 抽取关键帧
import cv2
cap = cv2.VideoCapture(video_path)
frames = []
while len(frames) < 10:  # 抽取 10 帧
    ret, frame = cap.read()
    if not ret: break
    frames.append(frame)

# 对每帧 embedding 后平均池化
embeddings = [get_embedding(frame) for frame in frames]
final_embedding = np.mean(embeddings, axis=0)
```

### 方案3：视频转文字 + 文本 embedding
使用 Whisper 提取音频转文字，结合视频描述生成文本向量：

**优点**：
- 文本 embedding 更稳定
- 可捕捉语义信息
- 文件小、速度快

**实现思路**：
```python
# 提取音频
ffmpeg -i video.mp4 -vn -acodec pcm_s16le audio.wav

# Whisper 转文字
import whisper
model = whisper.load_model("base")
result = model.transcribe("audio.wav")
text = result["text"]

# 文本 embedding
embedding = get_text_embedding(text)
```

## 推荐使用策略

1. **短视频（< 50MB）**：直接使用当前方案
2. **中等视频（50-200MB）**：先压缩再上传
3. **长视频（> 200MB）**：使用方案2（抽帧）或方案3（转文字）

## 测试建议

```bash
# 测试小视频（应该成功）
curl -X POST "http://localhost:8000/api/rag/import_video" \
  -F "file=@small_video.mp4"

# 测试大视频（会提示压缩）
curl -X POST "http://localhost:8000/api/rag/import_video" \
  -F "file=@large_video.mp4"
```
