# AI Lecturer: 智能学术数字人讲师系统

基于双引擎架构 (FastAPI + WebRTC) 的全栈数字人授课与视频生成模块。本项目旨在将结构化文本（如 Markdown 课件）自动转化为包含 AI 讲稿、语音和数字人形象的互动授课视频。支持“在线实时交互”与“离线高清渲染”两种模式。


## 1. 核心架构与目录树

系统采用“业务控制流”与“底层媒体流”物理分离的设计范式：

AI_Lecturer_Project/
├── start_unified.py          # [系统入口] 多进程调度脚本
├── unified_gateway.py        # [业务网关] FastAPI 控制核心 (8008端口)
├── offline_video_maker.py    # [离线管线] 离线音视频合成工作流
│
├── assets/                   # [静态资源] 存放底层视频素材与 PPT 演示图
├── temp_export/              # [动态产物] 运行时生成的音频、视频切片及成品
├── Wav2Lip_Offline/          # [离线引擎] 核心深度学习唇形同步模型库
│
└── LiveTalking-main/         # [在线引擎] 基于 WebRTC 的实时数字人服务 (8010端口)
    │   ... (引擎底层代码)
    ├── client.js             # [前端 SDK] 必须寄存在引擎目录下，避免 404 与跨域
    └── webrtcapi.html        # [前端 UI] 必须寄存在引擎目录下，通过 8010 端口访问()

---

## 2. 核心文件详解与配置项

在进行二次开发或部署前，请重点关注以下核心文件的配置项与业务逻辑。

### 2.1 `unified_gateway.py` (在线业务大脑)
该文件是整个系统的中枢神经，基于 FastAPI 构建。负责接收前端指令、调用 LLM 生成讲稿、管理并发任务以及路由分发。

* **核心配置项**：
    * `QWEN_API_KEY`: 阿里云大模型 API 密钥。部署前需替换为真实有效的 Key。
    * `LIVETALKING_URL`: 在线引擎的内部调用地址。默认为 `http://127.0.0.1:8010/human`。
    * `CORS Middleware`: 跨域配置。默认允许所有来源 (`allow_origins=["*"]`)。
* **模块职责**：
    * **内存数据库**：维护 `COURSE_DB` (在线课程大纲) 和 `OFFLINE_TASK_DB` (离线任务状态)。重启进程会清空此数据。
    * **打断机制控制**：提供 `/stop_speaking` 和 `/interrupt_and_ask` 接口，实现秒级的音频阻断与大模型临场作答调度。

### 2.2 `offline_video_maker.py` (离线渲染管线)
该文件封装了从“文字”到“成品视频”的自动化流水线，整合了 LLM、Edge-TTS、Wav2Lip 与 FFmpeg。

* **核心配置项 (需严格检查)**：
    * `--wav2lip_batch_size`: **显存调优关键参数**。默认建议设置为 `16` 或 `32`。若设置过高（如 128），在普通显卡上将直接触发 `CUDA Out of Memory` 或内存溢出崩溃。
    * `FFMPEG_EXE`: 默认调用系统环境变量中的 `ffmpeg`。需确保宿主机已正确安装并配置 FFmpeg。
* **管线流程**：
    1.  `generate_script_from_llm`: 调用大模型生成当前页的单句讲稿。
    2.  `text_to_speech`: 调用微软 Edge-TTS 接口生成 `.wav` 音频。包含 5 次防网络阻断的重试机制。
    3.  `render_wav2lip_offline`: 驱动底层 Wav2Lip 模型，将音频与面部视频进行逐帧唇形对齐，生成带有绿色/纯色背景的数字人切片。
    4.  `composite_pip_video`: 使用 FFmpeg 滤镜进行色键抠图（Color Keying），将数字人以“画中画”形式叠加至 PPT 图片右下角。
    5.  `merge_all_videos`: 将所有单页切片无损合并为完整的课程 `MP4` 文件。

### 2.3 `LiveTalking-main` (实时引擎模块)
此为独立的数字人实时驱动底座，对外暴露 8010 端口。
* **通信机制**：前端 `client.js` 采用标准 WebRTC 协议与该端口进行 ICE 候选者交换并建立 P2P 媒体流。业务指令（如发音内容）不走该端口，而是由 8008 网关间接调用。

### 2.4 交互端文件 (`webrtcapi.html` & `client.js`)
* **环境变更注意**：文件内的 `API_BASE` (默认 `http://127.0.0.1:8008/api/v1/online`) 与 WebRTC 连接地址。**若跨局域网联调，必须将所有的 `127.0.0.1` 替换为后端宿主机的真实 IPv4 地址**，否则将面临连接拒绝 (Connection Refused)。

---

## 3. 核心 API 接口清单 (8008 端口)

系统提供完全解耦的原子化 REST API。详情可运行项目后访问 `http://127.0.0.1:8008/docs` 获取交互式文档。

| 模块 | 路由路径 | Method | 功能描述 |
| :--- | :--- | :---: | :--- |
| **在线交互** | `/api/v1/online/create_course` | POST | 解析 Markdown 讲义，在内存中初始化课程大纲记录 |
| **在线交互** | `/api/v1/online/get_course/{id}` | GET | 获取指定课程的大纲数据结构 |
| **在线交互** | `/api/v1/online/generate_script` | POST | 请求 LLM 针对特定 PPT 页面生成口语化分段讲稿 |
| **在线交互** | `/api/v1/online/speak_sentence` | POST | 发送单句文本指令，驱动底层在线数字人发音 |
| **在线交互** | `/api/v1/online/stop_speaking` | POST | 触发紧急控制流，切断底层正在输出的音频 |
| **在线交互** | `/api/v1/online/interrupt_and_ask` | POST | 提交学生上下文问题，调度大模型生成解答并驱动发音 |
| **离线渲染** | `/api/v1/offline/generate_full_video` | POST | (异步任务) 提交多页 PPT 序列集，触发全自动合成管线 |
| **离线渲染** | `/api/v1/offline/status/{task_id}` | GET | 轮询查询异步离线渲染任务的状态 (`processing` / `success`) |
| **离线渲染** | `/api/v1/offline/download/{filename}` | GET | 下载最终渲染合并成功的完整 MP4 课程文件 |

---

## 4. 开发部署指令

1.  **激活环境**: 确保启动具有 PyTorch、FastAPI及 Wav2Lip 依赖的 Python 环境。
2.  **启动双引擎服务**:
    ```bash
    python start_unified.py
    ```
3.  **产物清理策略**: 
    在开发与长期运行中，`temp_export/` 目录下会积压大量的 `_p0.wav`, `_p0.mp4` 等临时切片文件。建议在 `merge_all_videos` 成功后，由后端逻辑自动清除这些过程副产物，仅保留最终合并的 `task_id.mp4` 文件。
```

## 5. 在线视频流调用与前端集成指南

1. 视频流调用原理
系统采用 WebRTC (Real-Time Communication) 协议实现低延迟视频传输。视频流由运行在 8010 端口的渲染引擎直接驱动，不经过 8008 业务网关。

信令端口：8010 (用于 WebRTC 握手：Offer/Answer)

业务端口：8008 (用于发送 speak_sentence 等控制指令)

调用逻辑：前端通过 client.js 与 8010 建立 P2P 连接，建立成功后，引擎会将渲染画面挂载到页面的 <video> 标签上。

2. 测试前端说明 (webrtcapi.html)
文件 webrtcapi.html 是本项目配套的标准测试前端。

定位：主要用于后端功能验证、接口联调及实验室环境下的原型演示。

使用方式：必须通过 http://<服务器IP>:8010/webrtcapi.html 访问。(http://127.0.0.1:8010/webrtcapi.html)我测试时用的

集成参考：若需开发正式的 UI 界面，请参考该文件中的 startLesson() 逻辑以及 client.js 的信令交换过程。

3. 开发者集成步骤 
如果你需要在自己的前端框架（如 Vue/React）中接入数字人视频流，请遵循以下步骤：

引入 SDK：将 client.js 引入你的项目。

配置地址：修改 client.js 中的请求路径，确保指向正确的服务器 IP 和 8010 端口。

开启跨域：确保后端 8010 引擎已开启 CORS 允许策略（见后端配置章节）。

初始化连接：在页面挂载后调用 start() 函数，此时数字人画面将自动填充至指定的 video 容器。