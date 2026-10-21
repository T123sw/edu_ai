# 本地模型服务接入核验

核验时间：2026-10-17 08:05–08:07 UTC。

结论：TTS 与文本 Embedding 已接入项目调用路径并通过真实服务调用；MinerU 本地服务与通用解析入口可用，但完整业务适配未完成。模拟考试仍使用云端 MinerU，课程准备的核心 PDF 资料会触发页覆盖校验缺陷。

## 实测结果

| 服务 | 生效地址与调用入口 | 本次结果 |
| --- | --- | --- |
| Qwen3-TTS | `127.0.0.1:8188/v1`；`classroom_narration.narration_audio` → `OpenMaicTtsService` | HTTP 200，生成 56,108 字节 MP3，ffprobe 确认时长 3.504 秒；本次端到端调用约 8.086 秒 |
| Qwen3-Embedding | `127.0.0.1:8189/v1`；RAG 的 `EmbeddingClient.embed_documents` | HTTP 200，两条文本各返回 1024 维有限数值向量，约 0.112 秒；只读查询现有索引为 1024 维、11,249 条 |
| MinerU 4.0.12 | `127.0.0.1:8190`；`DocumentParser` → `get_pdf_parser` → `LocalMinerUProvider` | HTTP 200，两页试卷生成 2,074 字符正文，约 4.456 秒；同时返回缺陷 `PAGE_COVERAGE_UNVERIFIED` |

三个服务与主后端均为 systemd active。后端 `/health` 返回 `knowledge_base_ready=true`、`document_count=11249`。MinerU 的正确健康入口为 `/v1/health`，`/health` 返回 404 不代表服务不可用。

读取系统实际运行配置及全部激活的 TTS/Embedding/PDF 配置：仅发现一个系统级 TTS 激活配置，地址同为本地；Embedding 与 PDF 无激活配置覆盖环境默认值。`TTS_LOCAL_ONLY=true`。后端启动于 05:39 UTC，晚于本地解析适配器与 `.env` 的 02:16 修改时间。

## 已确认的接入缺口

1. **模拟考试仍走云端。** `backend/src/app/exam_generation/snapshots.py:25` 将解析快照的空配置补为云端参数；实际调用 SnapshotCodec 后得到 `https://mineru.net/api/v4`、`vlm`。`sources.py:47` 直接实例化 `MinerUCloudProvider`，没有采用本地 provider 选择逻辑。本次没有再次请求云端，也未把历史 401 当成当前重新测得的结果。
2. **本地解析适配器缺少业务所需元数据。** `backend/src/app/integrations/pdf/mineru_local.py:123` 仅构造正文和少量元数据，未输出 `pageCount`、`pageIndices`、`layout`、`imageMapping`，图片/公式/表格独立字段仍是默认空值。本次虽返回 `pageRange=1-2`，课程准备 DocumentParser 仍实际标记 `PAGE_COVERAGE_UNVERIFIED`；`course_preparation/intake.py:64` 会拒绝带此缺陷的 auto/primary/coverage 核心资料。即便只把考试客户端换成本地，考试的严格页覆盖校验也仍无法通过。
3. **向量维度配置存在遗留值。** resolver 展示的 dimensions 仍为 768，但当前 OpenAI 协议调用不发送此字段；本次实际模型输出及现有索引均为 1024，因此未构成本次维度错误。`RAG_ENABLE_IMAGE_EMBEDDING=0`，本次结论仅覆盖文本向量。

下一步应统一考试与通用解析入口的 provider 选择及快照规则，补齐本地解析产物的页覆盖、版面与图片映射，再验证课程准备与考试的完整 PDF 流程。此轮仅核验，未修改业务实现、配置或重启服务。

## 证据与边界

- [机器结果](verification.json)：生效配置、服务状态、HTTP 目的地址、真实调用输出及考试解析快照；不含密钥。
- [服务端日志](service-requests.log)：本次三个真实 POST 请求均为 200。
- [解析正文](parsed-sample.md)、`audio/` 中的合成音频。
- [核验脚本](verify.py)：从项目根目录通过 `PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python docs/acceptance/2026-10-17-local-model-integration-audit/verify.py` 运行。

核验采用独立 Python 进程读取实际配置，执行项目业务服务/适配器并请求正在运行的本地服务；没有通过已登录浏览器新建课程、上传资料或创建考试任务，也没有在生产索引中写入验证文本。PostgreSQL 连接使用只读事务；向量索引以 SQLite `mode=ro` 查询。仅写入本目录验收产物及本地模型服务自身的正常请求缓存/日志。音频已验证格式和时长，未进行人工听感评估；本次单样本耗时不代表吞吐量或长期性能。
