# SPEC-16 · 本地 TTS 服务接入协议

> **状态**：设计草案，待实施  
> **目标**：允许 Edu_AI 接入本地部署的 Qwen TTS、VoxCPM、CosyVoice 或其他语音模型，业务代码不感知具体推理框架。  
> **关联规格**：SPEC-02（Speech Action）、SPEC-05（异步任务）、SPEC-06（Provider 配置）、SPEC-12（课堂问答）

## 1. 目标与边界

本协议在 Edu_AI 与本地 TTS 推理服务之间定义一个稳定的 HTTP 边界。模型服务只负责把一段文本转换为一个音频文件；课程权限、任务状态、音频落盘、URL 鉴权和浏览器降级由 Edu_AI 负责。

首版覆盖以下调用场景：

1. AI 课堂生成完成后的逐条讲解配音；
2. AI 课堂实时问答回答配音；
3. 学习资料问答回答配音；
4. 后续音频资源生成复用同一客户端。

首版不定义语音克隆训练、流式分片播放、多人音色编排和数字人唇形同步。模型可以在内部支持这些能力，但不得要求 Edu_AI 业务接口依赖某一模型专有字段。

## 2. 当前基线与需要修正的问题

截至 2026-09-11，Edu_AI 后端实际使用：

```text
provider = edge-tts
endpoint = http://127.0.0.1:8188/v1/audio/speech
voice = zh-CN-XiaoxiaoNeural
speed = 1.0
```

当前实现已经接近 OpenAI `audio/speech` 请求格式，但存在以下分裂：

- Edu_AI 后端使用 `edge-tts`，OpenMAIC sidecar 进程使用 `qwen-tts`；
- 课堂生成会把后端 provider 名称传给 sidecar，sidecar 未配置同名 provider 时会在配音阶段失败；
- 运行时设置页面已经能保存 TTS 的 `base_url/api_key/model/voice`，实际合成代码还没有读取它；
- 运行时设置页面当前强制填写 `api_key`，本机回环地址部署需要允许留空；
- 配置页面提交的课堂音色没有进入最终合成，实际音色仍由后端环境变量决定；
- Edge 直连请求没有传递 `speed`；
- Edge HTTP 异常没有完全进入现有问答降级分支。

本规格采用一个明确的归属：**Edu_AI 后端统一拥有 TTS 调用，OpenMAIC 只生成课堂文本和动作结构**。课堂生成时不再让 sidecar 调用另一套 TTS。这样本地模型只配置一次，也能保证内容审阅完成后再生成与最终文本一致的音频。

## 3. 目标架构

```text
课堂生成 / 课堂问答 / 资源问答
              │
              ▼
       EduAiTtsService
       ├─ 配置解析
       ├─ 文本规范化
       ├─ 超时与错误归一
       └─ 音频格式和大小校验
              │
              ▼
 POST {base_url}/audio/speech
              │
              ▼
  本地 OpenAI-compatible TTS Server
       ├─ Qwen TTS adapter
       ├─ VoxCPM adapter
       ├─ CosyVoice adapter
       └─ 其他模型 adapter
              │
              ▼
       audio/mpeg 或 audio/wav
```

推荐将 `base_url` 配置为带版本的 API 根地址，例如：

```text
http://127.0.0.1:8188/v1
```

Edu_AI 固定在其后追加 `/audio/speech`，最终地址为：

```text
http://127.0.0.1:8188/v1/audio/speech
```

## 4. 必需接口

### 4.1 健康检查

```http
GET /health
```

成功响应：

```json
{
  "status": "ok",
  "service": "local-tts",
  "model_loaded": true,
  "model": "本地实际模型标识",
  "device": "cuda:0",
  "formats": ["mp3", "wav"]
}
```

字段约束：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `status` | string | 是 | 就绪时固定为 `ok` |
| `service` | string | 是 | 固定为 `local-tts` 或部署实例名 |
| `model_loaded` | boolean | 是 | 模型权重是否已经加载并可以推理 |
| `model` | string | 否 | 当前默认模型标识 |
| `device` | string | 否 | 推理设备，仅用于运维诊断 |
| `formats` | string[] | 否 | 服务支持的输出格式 |

服务正在加载模型时返回 HTTP 503：

```json
{
  "error": {
    "code": "model_loading",
    "message": "TTS model is loading",
    "retryable": true,
    "request_id": "req_xxx"
  }
}
```

### 4.2 语音合成

```http
POST /v1/audio/speech
Content-Type: application/json
Authorization: Bearer {api_key}
X-Request-ID: req_xxx
```

本机回环地址部署时允许不配置 `api_key`；跨主机访问必须使用 Bearer Token 或等价的内网鉴权。

请求体：

```json
{
  "model": "本地实际模型标识",
  "input": "需要合成的课堂讲解文本。",
  "voice": "default",
  "response_format": "mp3",
  "speed": 1.0,
  "language": "zh-CN",
  "instructions": "自然、清晰的教师讲解语气"
}
```

字段约束：

| 字段 | 类型 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `model` | string | 是 | 无 | 部署服务公开的模型标识，不固定为某个云端商品名 |
| `input` | string | 是 | 无 | UTF-8 文本，去除首尾空白后长度为 1–1500 字符 |
| `voice` | string | 是 | `default` | 预置说话人或本地注册的音色 ID |
| `response_format` | enum | 否 | `mp3` | `mp3`、`wav`、`ogg` 或 `m4a` |
| `speed` | number | 否 | `1.0` | 取值 0.5–2.0；adapter 负责转换为模型参数 |
| `language` | string | 否 | 自动检测 | 建议使用 BCP 47，如 `zh-CN`、`en-US` |
| `instructions` | string | 否 | 空 | 仅具备指令控制能力的模型使用；不支持时可以忽略 |

`instructions` 不得承载业务正文。普通模型只需要消费 `input/voice/speed`。

#### 成功响应

成功时直接返回音频二进制，不使用 Base64 JSON：

```http
HTTP/1.1 200 OK
Content-Type: audio/mpeg
Content-Length: 183240
X-Request-ID: req_xxx
X-Audio-Format: mp3
X-Audio-Duration-Ms: 6280

<binary audio bytes>
```

MIME 映射：

| `response_format` | `Content-Type` |
| --- | --- |
| `mp3` | `audio/mpeg` |
| `wav` | `audio/wav` |
| `ogg` | `audio/ogg` |
| `m4a` | `audio/mp4` |

Edu_AI 必须校验：

- HTTP 状态为 200；
- 响应体非空且不超过 10 MiB；
- `Content-Type` 与支持格式一致；
- 音频写入使用临时文件和原子替换；
- 文件名由 Edu_AI 生成，不能采用模型返回的路径。

#### 错误响应

所有非 2xx 响应使用统一 JSON：

```json
{
  "error": {
    "code": "queue_full",
    "message": "TTS inference queue is full",
    "retryable": true,
    "request_id": "req_xxx"
  }
}
```

标准状态和错误码：

| HTTP | `code` | 是否重试 | 场景 |
| --- | --- | --- | --- |
| 400 | `invalid_request` | 否 | 缺少字段、空文本或非法参数 |
| 401/403 | `authentication_failed` | 否 | Token 缺失或无效 |
| 404 | `model_not_found` | 否 | 模型不存在 |
| 404 | `voice_not_found` | 否 | 音色不存在 |
| 413 | `input_too_long` | 否 | 文本超过服务限制 |
| 422 | `unsupported_format` | 否 | 不支持请求的音频格式 |
| 429 | `queue_full` | 是 | GPU 推理队列已满；应返回 `Retry-After` |
| 500 | `inference_failed` | 视情况 | 模型推理或音频编码失败 |
| 503 | `model_loading` | 是 | 模型未就绪或 GPU 暂不可用 |
| 504 | `inference_timeout` | 是 | 单次推理超时 |

Edu_AI 对 429、503、504 最多自动重试一次；其他 4xx 不重试。日志记录错误码、耗时、模型、音色和文本长度，不记录完整讲解文本及密钥。

## 5. 推荐发现接口

以下接口不阻塞首版合成，但建议本地服务实现，供配置页面选择模型和音色。

### 5.1 模型列表

```http
GET /v1/models
```

```json
{
  "object": "list",
  "data": [
    {
      "id": "本地模型标识",
      "object": "model",
      "owned_by": "local"
    }
  ]
}
```

### 5.2 音色列表

```http
GET /v1/audio/voices?model={model_id}
```

```json
{
  "object": "list",
  "data": [
    {
      "id": "default",
      "name": "默认教师音色",
      "language": "zh-CN",
      "gender": "female",
      "preview_url": null
    }
  ]
}
```

`gender` 只用于展示，不参与业务判断。`preview_url` 如果存在，必须受鉴权保护或是短期签名 URL。

## 6. Edu_AI 配置契约

目标运行时配置沿用现有 `tts` provider 字段：

```json
{
  "provider_name": "local-qwen-tts",
  "base_url": "http://127.0.0.1:8188/v1",
  "api_key": "",
  "model": "本地实际模型标识",
  "voice": "default",
  "timeout_seconds": 120
}
```

新增的进程级默认项：

```dotenv
TTS_PROVIDER_NAME=local-qwen-tts
TTS_API_BASE=http://127.0.0.1:8188/v1
TTS_API_KEY=
TTS_MODEL=本地实际模型标识
TTS_VOICE=default
TTS_SPEED=1.0
TTS_RESPONSE_FORMAT=mp3
TTS_TIMEOUT_SECONDS=120
TTS_MAX_INPUT_CHARS=1500
```

配置优先级与其他 provider 保持一致：

```text
任务创建时的配置快照 > 用户启用配置 > 系统启用配置 > 环境变量默认值
```

浏览器不能提交 `base_url`、`api_key` 或任意 provider 名称到合成接口。浏览器只表达“是否需要配音”和教学偏好，后端从受控运行时配置解析实际服务。

配置验证执行两个步骤：

1. `GET {origin}/health`，确认 `status=ok` 且 `model_loaded=true`；
2. `POST {base_url}/audio/speech` 合成短句“配置测试”，确认音频非空且 MIME 合法。

其中 `{origin}` 是从 `base_url` 去掉末尾 `/v1` 后得到的服务根地址。

## 7. 调用阶段

### 7.1 AI 课堂生成

目标顺序：

```text
创建 EduJob
  → OpenMAIC 生成 stage/scenes/actions（enableTTS=false）
  → Edu_AI 拉取完整课堂
  → 内容审阅与必要修订
  → step=generating_tts
  → 对最终 speech action 逐条调用本地 TTS
  → 音频落入课程存储并写入 audioId/audioUrl
  → 校验
  → 持久化
  → job=succeeded
```

每条 speech action 输入：

```json
{
  "text": "action.text",
  "audio_id": "tts_s{scene_order}_{action_id}",
  "speed": "action.speed 或配置默认值"
}
```

其中 `audio_id` 只用于 Edu_AI 文件命名，不传给模型服务。成功后 action 更新为：

```json
{
  "id": "speech-1",
  "type": "speech",
  "text": "课堂讲解内容",
  "audioId": "tts_s1_speech-1",
  "audioUrl": "/api/courses/{course_id}/classrooms/{classroom_id}/audio/tts_s1_speech-1.mp3"
}
```

单条配音失败不应使整个课堂生成失败。失败 action 保留文字且不写 `audioUrl`，前端播放时使用浏览器 TTS，再失败则按阅读时长等待。

### 7.2 课堂问答

```text
校验课堂位置
  → LLM 生成 answer_text + transition_text
  → 调用本地 TTS
  → 保存问答 turn
  → 返回文字、tts_status 和 audio_url
```

TTS 文本：

```text
{answer_text}\n{transition_text}
```

成功响应给前端：

```json
{
  "session_id": "session_xxx",
  "turn": {
    "turn_id": "turn_xxx",
    "client_turn_id": "uuid",
    "question": "学生问题",
    "answer_text": "回答正文",
    "transition_text": "回到课堂的衔接语",
    "tts_status": "ready",
    "audio_url": "/api/courses/.../audio/turn_xxx.mp3",
    "created_at": "ISO-8601"
  }
}
```

本地 TTS 不可用时仍返回 HTTP 200 和完整文字：

```json
{
  "tts_status": "failed",
  "audio_url": null
}
```

前端随后使用浏览器 `SpeechSynthesis`。TTS 失败不能把已经生成成功的问答变成 5xx。

### 7.3 学习资料问答

调用时机和失败语义与课堂问答一致。音频 URL 必须绑定课程、资源 ID、资源版本、会话和当前用户；资源版本变化后旧 URL 不得被新版本复用。

## 8. 本地模型 Adapter 要求

每种模型只在本地 TTS 服务内部实现参数转换：

| 通用字段 | Qwen 类模型 | VoxCPM/CosyVoice 类模型 | 其他模型 |
| --- | --- | --- | --- |
| `input` | 合成文本 | 合成文本 | 合成文本 |
| `voice` | speaker/voice ID | 预置说话人 ID | adapter 自行映射 |
| `speed` | 转换为模型支持的 rate/speed | 转换或后处理变速 | 不支持时仅允许 1.0 |
| `language` | language/language_type | lang | 可选 |
| `instructions` | instruct 模型的控制文本 | 支持时映射 | 不支持时忽略 |
| `response_format` | 推理输出后编码 | 推理输出后编码 | 必须返回约定 MIME |

本地服务必须在启动时加载模型，不能每次请求重新加载权重。服务应限制 GPU 并发并提供有界队列；超过容量返回 429，不得无限堆积请求。

如果模型只输出 PCM/WAV，而配置要求 MP3，adapter 可以使用 FFmpeg 编码；无法编码时返回 `unsupported_format`，不能用 WAV 内容冒充 `audio/mpeg`。

## 9. 调用示例

### 9.1 cURL

```bash
curl -X POST 'http://127.0.0.1:8188/v1/audio/speech' \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: req-local-test-001' \
  -d '{
    "model": "本地实际模型标识",
    "input": "数组在内存中采用连续存储结构。",
    "voice": "default",
    "response_format": "mp3",
    "speed": 1.0,
    "language": "zh-CN"
  }' \
  --output local-tts-test.mp3
```

### 9.2 Python 客户端

```python
import httpx

payload = {
    "model": "本地实际模型标识",
    "input": "数组在内存中采用连续存储结构。",
    "voice": "default",
    "response_format": "mp3",
    "speed": 1.0,
    "language": "zh-CN",
}

response = httpx.post(
    "http://127.0.0.1:8188/v1/audio/speech",
    json=payload,
    timeout=120,
)
response.raise_for_status()
assert response.headers["content-type"].startswith("audio/")
assert response.content
open("local-tts-test.mp3", "wb").write(response.content)
```

## 10. 验收条件

1. 配置页能够保存、测试并启用本地 TTS，后续新任务读取同一配置快照；
2. 停止 OpenMAIC 的 TTS provider 不影响本地课堂配音；
3. 停止本地 TTS 服务后，课堂文本仍能生成，问答仍返回文字，前端进入浏览器朗读；
4. Qwen TTS 与另一种本地模型通过相同 `/v1/audio/speech` 协议接入，切换时业务代码零修改；
5. `speed`、`voice`、`response_format` 实际传递并生效；
6. 课堂审阅修改讲解文字后生成的是新音频，不复用旧音频；
7. 音频 URL 需要登录，其他用户和路径穿越请求不能读取；
8. 429/503/504 最多重试一次，任务和问答不会无限等待；
9. 日志不包含 API Key、完整课堂讲稿或音频 Base64；
10. 自动化测试覆盖成功、模型未加载、队列已满、超时、非法 MIME、空音频、超大音频和浏览器降级。

## 11. 建议实施顺序

1. 将当前 `OpenMaicTtsService` 改造成 provider 无关的 OpenAI-compatible HTTP 客户端；
2. 把运行时 `tts` 配置接入实际调用和任务配置快照，并允许本机回环服务不填写 API Key；
3. 课堂生成关闭 sidecar TTS，在 Edu_AI 内容审阅后统一合成；
4. 修正问答异常归一，任何本地 TTS 网络或推理异常都返回 `tts_status=failed`；
5. 扩展本地 8188 服务实现健康检查、模型字段、speed、统一错误码和至少 MP3/WAV 输出；
6. 先接入一个本地 Qwen TTS adapter，再用第二个模型验证协议没有绑定 Qwen 专有字段；
7. 完成课堂、问答、鉴权音频和故障降级端到端测试。
