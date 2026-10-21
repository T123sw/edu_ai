# 考试上传移除知识库索引

2026-10-17。按用户要求，考试上传改用独立资料存储；上传不建立知识库、不提交索引、不调用 Embedding。生成任务读取原文件并通过配置的 MinerU 解析，之后保留原有 DeepTutor 分析/出题逻辑。纯文本资料直接读取。

## 接口与调用顺序

1. 已登录用户向 `POST /api/exam-generations/documents` 提交 multipart 字段 `file`；单文件不超过 30 MB。返回 201，包含 `document_id`、`filename`、`size_bytes`、`source_hash`、`status=uploaded`。此时只保存文件，尚未解析。
2. 调用原 `POST /api/exam-generations`，在 `sources` 中传入该 `document_id` 和对应 `role`；PDF 仿卷使用 `template`。其他生成字段沿用既有契约。
3. 持久任务启动时，默认 `GenerationSources` 读取上传文件、核对 hash，然后调用 MinerU；解析正文、版面和图片进入后续出题流程。

新文件存于 `Config.STORAGE_ROOT/exam_uploads/<owner_hash>/<document_id>`，按用户隔离。生成任务仍支持旧个人资料 ID 的授权读取，不会因为读取再触发入库。原个人知识库上传接口继续承担其原有功能，考试页面接入时必须使用上述新接口。

## 验证

- 隔离后端回归：60 passed，1 warning，16.17 秒。覆盖上传、默认资料读取、用户隔离、篡改、格式、大小和认证，并阻断知识库创建及索引入口。命令：`/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python services/deeptutor/scripts/verify_m2_backend.py tests/exam_generation tests/test_mineru_local.py`。见 [regression.log](regression.log)。
- 真实 PDF：FastAPI TestClient 上传返回 201，默认资料入口调用实际本地 MinerU；4.22 秒得到 2074 字符、17 个版面块。上传阶段无网络调用；解析阶段仅访问本地 MinerU 的提交、轮询、结果端点。知识库入库、Embedding、LLM 调用均为 0。见 [verification.json](verification.json)、[验证脚本](verify_real.py) 和 [日志](real-validation.log)。
- 真实验证读取实际解析配置，使用临时文件存储、合成登录用户；未写入生产业务数据。通过阻断入库方法、requests 网络请求以及非 MinerU 的 httpx 请求检查隐藏调用。本次未重复执行已有出题模型验收。

## 生效边界

当前正式后端 PID 1235977，启动时间 2026-10-17 09:18:40 UTC，早于本次改动。需要管理员执行 `sudo systemctl restart edu-ai-backend` 后，新上传接口才会生效。考试页面仍为占位入口，尚未接入上传和生成；本次完成后端资料链路，不代表完整考试页面已交付。
