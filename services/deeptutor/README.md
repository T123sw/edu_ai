# DeepTutor 内部出题服务

2026-10-20：0016 已于 11:57:13 UTC 上线，同时激活 0015 的结构校验出题流程。修复公共图题干补读遗漏后续题及重复起始行导致独立题合并的问题；159 项服务回归通过，用户原卷隔离抽取 45/45，原失败任务正式重试 45/45 并通过整卷结构检查，试卷接口 200。见[本轮验证](../../docs/acceptance/2026-10-20-exam-shared-context/verification.json)。

2026-10-18：0014 于 06:30:30 UTC 上线，157 项服务回归、85 项隔离后端回归通过。新增三份完整 PDF 的多轮正式测试，Kentucky 0013 及最终版两次全新上传均完成 4 大题/17 子题出卷与预览；Princeton 0013 重试后 8/9、上海 0011 重试后 44/45，仍有复杂题质量与审核问题。完整重复运行结果及版本边界见[多 PDF 验收](../../docs/acceptance/2026-10-18-exam-multi-pdf/README.md)。

本目录实现[迁移计划](../../docs/architecture/2026-10-16-deeptutor-migration-plan-cn.md) M1–M3 主体：保留完整 DeepTutor 源码、固定补丁和完整默认 Python 依赖，接入 Edu_AI 模型快照、持久任务、授权资料和试卷蓝图。2026-10-17 已安装并启动用户级常驻服务，考试上传、生成历史、失败重试和试卷预览页面已完成隔离验证。正式主后端已于 13:40:48 UTC 重启，新接口已加载，考试页面于 13:41:48 UTC 发布；正式网站真题复测已完成：首轮存储失败后，一次页面重试恢复全部 32 题；随后事件尾部及手机预览/数字选项缺陷已修复并发布。本轮继续修复事件写入和答案核验，最新桥接补丁 0009 已于 18:28:51 UTC 上线，109 项服务回归通过；本轮正式真卷经一次增量重试后 32/32，完整预览通过。整卷使用 0008，0009 编号兼容另行验证；详细版本边界见[计算证据与内容修复](../../docs/acceptance/2026-10-17-exam-evidence-fix/README.md)。此前性能变更见[性能与质量修复](../../docs/acceptance/2026-10-17-exam-quality-performance/README.md)。前一轮遗留问题详见[重启复测](../../docs/acceptance/2026-10-17-exam-restart-retest/README.md)。计时作答及评分未实现，`/health` 的 `exam_ready` 仍为 false。见[本轮修复与验收](../../docs/acceptance/2026-10-17-exam-e2e-fixes/README.md)。

## 源码与安装

使用 Linux / Python 3.12。`requirements.lock.txt` 固定本次完整默认安装的 Python 包；GraphRAG、Manim 等上游可选扩展按需要另行验证。前端完整保留，但本内部服务不运行上游 Next.js 页面。

```bash
python3.12 services/deeptutor/scripts/bootstrap.py
```

脚本按 `upstream.lock.json` 拉取完整提交到 `.upstream/DeepTutor`，校验并应用补丁，在本目录 `.venv` 安装锁定依赖和两个 editable 项目，最后执行 `pip check`。可单独运行 `scripts/prepare_upstream.py` 校验源码。重跑不覆盖未知修改，网络中断可重试。本目录另保留上游原样的 [LICENSE](UPSTREAM_LICENSE) 与[第三方通知](UPSTREAM_THIRD_PARTY_NOTICES.md)；分发时随源码及依赖保留对应通知。

项目代码不携带生成数据和密钥；`.upstream`、`.venv`、`.runtime` 被本目录忽略规则排除。不要把这些目录当作需要提交的业务文件。

## 启动

通过进程管理器安全提供 `EDU_DEEPTUTOR_TOKEN`（至少 32 字符），并设置独立持久目录 `DEEPTUTOR_HOME`。默认运行目录为本目录 `.runtime`。Edu_AI 后端配置相同 token 和 `EDU_DEEPTUTOR_URL`（默认 `http://127.0.0.1:8026`）；token 不发送给浏览器。服务启动保留上游默认 main/agents 设置，不创建共享模型凭据。当前验证为单进程运行；多进程协调需要上游 Redis 配置与专项验收。

```bash
cd services/deeptutor
.venv/bin/python -m uvicorn edu_deeptutor.api:create_app --factory --host 127.0.0.1 --port 8026
```

启动检查源码提交、补丁内容和导入位置，拒绝未审查版本。仅监听内部网络；不为浏览器提供服务 token，不挂载上游管理端或公共 WebSocket。

`EDU_DEEPTUTOR_TOOLS` 是允许请求显式选择的工具名称，逗号分隔，默认空。`EDU_DEEPTUTOR_BUILTIN_TOOLS` 控制自动挂载的内置工具，默认 `read_source`；适配器把此范围传入原工具组装逻辑。其他工具实现完整保留，按部署配置启用并验证。本阶段业务 API 不接受任意知识库名称、工具名或服务器路径。这些配置不替代执行沙箱或网络隔离。

## 内部协议

除 `/health` 外，均要求 `Authorization: Bearer <service-token>` 和 `X-Edu-Owner: <percent-encoded UTF-8 owner>`。owner 必须来自 Edu_AI 已认证的用户，不能从浏览器 body 直接采用。服务将 owner 映射到独立的非管理员工作区。

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| GET | `/health` | 固定版本及桥接状态，不宣称模型或考试已可用 |
| POST | `/internal/generations` | 启动 `deep_question`，返回 session_id、turn_id 和状态 |
| GET | `/internal/turns/{turn_id}` | 当前用户可见的任务状态，不返回原始错误和答案 |
| GET | `/internal/turns/{turn_id}/events?after_seq=0` | 默认只输出安全进度，NDJSON 格式，可带游标回放 |
| GET | 同上加 `view=internal` | 内部完整事件，含题目/答案/工具记录，仅供后端存储与组卷 |
| POST | `/internal/turns/{turn_id}/cancel` | 向原运行层请求取消 |

提交结构示例：

```json
{
  "request_id": "6ff47957-a6d7-4672-a67d-36c67e71ae2f",
  "requirement": "根据排序资料生成练习，快速排序使用 Lomuto 划分",
  "mode": "custom",
  "num_questions": 15,
  "question_types": ["choice", "fill_in_blank"],
  "per_type_counts": {"choice": 10, "fill_in_blank": 5},
  "language": "zh"
}
```

可选 `model_selection` 为上游 `{profile_id, model_id}` 引用，不是密钥。业务适配使用互斥的 `runtime_model`，由后端解密已冻结的模型配置后在受信链路上传递；服务通过请求上下文安装配置，不把密钥写入上游请求、会话或事件。当前适配 OpenAI 兼容协议，保留 Edu_AI 既有 DeepSeek/Qwen 思考开关策略。

可选附件仅接受文件名、MIME、类型和 base64 字节，不接受 URL 或服务端任意路径。M2 可传 `parsed_sources`，包含完整正文、布局、图片、原文件 hash 与显式 `context/template` 角色；模板通过服务器创建的解析目录进入原抽题器。mimic 要求一份 PDF 附件或一份已解析模板。已接入原题蓝图、完整文档窗口、变长选项/多选/多空/子题和逐题图像传递；扫描真题抽取已实测；自动角色识别和多卷策略尚未完成。试卷内容不会经过前端进度投影返回。

请求编号代表一次提交。网络重试复用编号；包括模型在内的输入改变时返回冲突。失败 turn 不在同一编号下重新生成；显式任务重试创建新记录，保留原结果。跨系统任务映射、批量事件与游标已持久化；显式任务重试携带仅供后端设置的 `checkpoint_id`，在同一 owner、输入、模型和补丁版本下复用已通过检查的逐题结果；新建请求不复用旧题。仿卷按生成前冻结的蓝图检查顺序、题型、选项、多空和子题，另做模型语义核对与有限修复；模型核对仍可能误判，不能直接作为考试发布。

业务入口为 `POST /api/exam-generations` 和 `GET /api/exam-generations/{id}`，身份来自现有登录认证。资料先通过考试专用 `POST /api/exam-generations/documents` 上传（multipart 字段 `file`，单文件最大 30 MB），返回 `examdoc_` 前缀的 `document_id`；再将它放入生成请求的 `sources`。上传仅保存原文件，生成任务启动后通过 MinerU 解析 PDF 等支持格式，纯文本直接读取；不创建知识库、不提交索引、不调用 Embedding。提交时冻结文件 hash，执行时重新授权并核对内容；取消和重试复用任务中心。历史个人资料 ID 保持只读兼容。原始结果存于私有 `exam_generation_v1` 记录，事件和高频游标分别保存在独立 namespace；结果与游标单条 SQL 一致读取。生成状态接口只返回任务状态。考试专用上传已于 09:36:38 UTC 重启后在线，新页面和历史/预览接口待本轮正式发布；见[无 RAG 上传验收](../../docs/acceptance/2026-10-17-exam-upload-no-rag/README.md)。

## 验证

```bash
DEEPTUTOR_HOME=/tmp/edu-deeptutor-tests .venv/bin/python -m pytest tests -q
```

服务测试覆盖鉴权、真实 SDK 工作区隔离、进度答案隔离、事件游标、取消、源码准备可重复性及首批补丁。生成模型边界使用替身，不把这些结果当作真实出题质量。

Edu_AI 客户端位于 `backend/src/app/integrations/deeptutor`，任务适配位于 `backend/src/app/exam_generation`。`progress()` 为展示投影，`internal_events()` 含答案，仅供业务后端。后端回归请使用后端 Python 执行 `scripts/verify_m2_backend.py`，它会在加载项目配置后强制隔离所有持久存储；不要直接沿用部署环境运行旧回归。

真实模型验证脚本 `scripts/verify_m2_generation.py --output <证据目录>` 会调用已配置的外部模型及 MinerU。`--native-pdf-validation` 仅针对合成文本 PDF 验证后续链路，不代表 MinerU/OCR 通过，也不为生产增加降级。进程崩溃检查使用 `scripts/verify_m2_restart.py`，模型边界为受控 HTTP 替身。

验收记录：[M1](../../docs/acceptance/2026-10-16-deeptutor-migration-m1/README.md)、[M2](../../docs/acceptance/2026-10-16-deeptutor-migration-m2/README.md)、[M3](../../docs/acceptance/2026-10-17-deeptutor-migration-m3/README.md)。


M3 的 `ExamBlueprint` 使用 `version=1` 的内部 JSON 契约。每题保留文档 ID、原文件 hash、解析正文 hash、原编号、顺序、分区、原文行范围、页码、考点、参考内容、选项键、空位数量、图片和递归子题。稳定 ID 由来源正文 hash、父题和顺序确定。蓝图在生成第一题前发为私有事件并单独持久化，终态结果不能修改它。

长文按完整行组成重叠窗口，所有原文均进入抽取；跨窗口未完成题另读完整范围，未解决的残题或无效行号导致明确失败。缺失行号最多修复一次。这个核对不能证明模型从未漏识别一整道题，因此仍需真实长卷样本验收。

2026-10-20 起，考试仿卷在抽取题型与来源蓝图后直接交给模型生成，只进行本地结构检查：题型、题数、选项键、答案字段、填空数量和子题身份/层级。结构错误最多修复两次；不再调用独立解题、计算证据核验、语义/新颖度/答案正确性审查，也不注入预计算的树题实例。新结果使用 `validation_mode=structure_only` 与 `structure_passed`，不将结构通过称为内容审阅通过；历史已通过结果保持兼容。

出题进度按实际发出的题目位置更新“已处理 X/Y 题”，百分比在出题阶段由 40% 推进至 95%，保存完成后为 100%；失败题也计入已处理数量，不能把该数量理解为正确答案数量。逐题位置与事件游标一并保存，断线接续恢复进度，模型推理片段不影响计数。

扩展真实验证：`--paper-text <合成试卷文本> --retry-failed` 可测试多页试卷及一次显式任务重试；仍在临时数据库和独立服务中运行。

## 常驻部署与页面启用

```bash
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python services/deeptutor/scripts/install_user_service.py
systemctl --user status edu-ai-deeptutor
```

安装脚本沿用或生成内部令牌，将后端 `.env` 与服务私有环境文件对齐，文件权限为 0600；不会打印令牌。用户服务监听 127.0.0.1:8026。本机已开启 linger，服务随用户管理器持续运行。主后端需要重启才能加载配置；管理员重启后运行 `python scripts/publish-exam.py`，脚本会校验接口、桥接健康、源码和构建哈希及上一版前端入口，再备份并发布。

新增 `GET /api/exam-generations` 返回当前用户历史；`GET /api/exam-generations/{generation_id}/paper` 只对完整结果返回题干、选项与子题，不返回答案、解析或模型元数据。考试新任务与显式重试均为 30 分钟执行上限。一次生成不保证全题通过；失败任务保留已通过题目的检查点供显式重试。
