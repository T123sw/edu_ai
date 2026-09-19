# C 模块：文件、检索与证据交接

实现计划：[03-sources](../superpowers/plans/2026-09-19-preparation-chain-optimization/03-sources.md)。C1–C3 代码与模块验证已交付；最终资源生成、课堂视觉接入和 G 的跨窗口闭环尚未验收。

## 版本与范围

- 原仓库 HEAD：`67fc18b85ffbd82406c5ab33703eff8ea627c222`。
- 临时依赖快照：`1c1b9fd06dc52252d6d70bb7bc7189de266e5414`。包含启动时必要的上一轮未提交代码和计划；**不是 G 已确认的共同基线**。原工作区及其暂存区未改动，备份、密钥、数据库、前端构建和音频未收入快照。
- 分支：`feat/preparation-sources-20260919`；工作树：`Edu_AI/.worktrees/preparation-sources-20260919`。
- C1：`868320bb`，解析控制与私有资产引用。
- C2：`f115f629`，任务正文快照、能力与外部尝试记账。
- C3：`8864ee7c`，研究视图、精确回读及有限会话恢复。
- C2 记账补充：`73d6eed3`，每次来源 provider 尝试的实测 elapsed_seconds。
- C 模块变更清单：`git diff --name-only 1c1b9fd0..73d6eed3`。只改 C 所属文件；共享 `context.py`、provider、数据库模型和迁移、端到端脚本未修改。

G 应先核对依赖快照与共同基线，再依序 cherry-pick 三个模块提交、记账补充及本交接文档提交。不要把临时依赖快照当作全部由 C 实现的变更，也不要覆盖原工作区的其他窗口成果。

## 行为及兼容

1. MinerU parse 新增可选 `deadline`（进程内 monotonic 绝对秒）、`canceled`、`on_remote_task`。无参数的旧入口兼容；提交、上传、轮询、下载及返回成功前检查控制，timeout 不超过剩余时间。等待和传输可注入，不需真实等待十五分钟测试。同步在途 HTTP 在响应/timeout 后检查取消；不承诺已提交的远端任务被服务商撤销。
2. 真实准备任务经 `controlled_parse` 传任务 deadline、取消状态、租约/权限校验；控制句柄不进检查点。`parse_tasks` 只保存真实 batch 引用和文档版本。解析未成功不登记 parsed。若远端提交刚成功时任务同时撤销、检查点写入被拒绝，异常仍附 `remote_task`；最终数据库审计持久化可由 F/G 进一步接收，不能绕过租约强写。
3. 解析数据继续保存原始字节哈希和真实字符位置；PDF 校验完整页索引，Office 不生成虚构页码。旧 MinerU 缓存可读；没有 assets 的旧缓存明确 `no_assets`，不会为了图片自动重解析。
4. `SourceSnapshots.get_or_fetch(url, *, read, scope, timeout)` 保存不可变正文、canonical URL、SHA256、时间和 snapshot ID。使用已有任务 SQL 检查点的 `source_snapshots` 字段，**无新增表、无迁移**。任务内固定版本，不做静默 TTL 刷新；显式过期拒绝继续读取但不覆盖旧证据，生命周期随任务检查点。恢复及分页不重新提取正文。缓存作用域包含 owner、preparation、来源策略、config_snapshot 摘要；命中也复核任务和来源授权。
5. 旧 SourceEvidence 新字段默认 null，原 source_id、正文、哈希和引用保持不变；新分页检查旧片段与当前完整正文一致。配置/版本变化导致正文不同则 `SOURCE_VERSION_CONFLICT`，不混接网页版本。引用位置修正仅限相同 snapshot。
6. Tavily 搜索临时错误且 Bocha 已配置时，最多一次回退；认证/权限错误不回退。搜索和正文能力分别呈现 configured/health，未经请求的服务标 unknown。仅配置 Bocha 不授予正文能力，明确 `EXTRACT_NOT_CONFIGURED`。429、超时、连接、5xx 可有限重试；同查询/来源两次失败后必须换来源或 blocker。无正文可以换来源，不能使用摘要。每个搜索/正文 provider 尝试分别走 SQL budget ledger，缓存分页和本地证据回读不产生外部 I/O 计费。
7. `build_research_context_view(state, *, required_ids, max_bytes)` 保留全部原要求、未解决缺口、结论/精确引用、来源定位。省略正文有 `content_omitted`、source_id 和 `read_research_evidence` 工具；qN_M 可回读真实短句，不能以摘要冒充原文。未知 required ID、必要内容超预算均明确失败。字节估计与 provider usage 分开，未测 token 不报为 0。
8. ResearchAgent 和连续 Harness 初始上下文使用 48,000 字节研究视图，原 provider guard 保留。连续会话历史触发 guard 且已保存进展时，最多两次从精确检查点重建会话，不退还调用预算；没有进展或不可压缩的硬要求仍失败。多附件读取额度按实际长度计算，整体模型/动作预算不变。

## 给 A / B / E / G 的接口

| 接收窗口 | 接口与实际消费位置 |
| --- | --- |
| A | brief 的 requirement_id/source_ref/source_quote/schema 未改变；Evidence 新增可选 snapshot_id/snapshot_sha256/canonical_url。node_evidence 的引用仍来自真实 evidence 原文；下游可以继续使用既有 quote/source_hash。 |
| B | `research_context_view.build_research_context_view` 返回 dict，max_bytes 覆盖返回对象的紧凑 UTF-8 JSON；不包含外层 request、附件需求理解及 tool schemas，应继续计入总 context guard。`read_research_evidence` 已挂载研究/计划工具；不能删除它后只保留摘要。`research_stages` 已接有限会话恢复。 |
| E | `DocumentStore.asset_refs(owner, UploadRef)` → `{status: available\|no_assets, assets: [{asset_id, owner_user_id, document_id, version, source_hash, content_sha256, mime_type}]}`；`read_asset(owner, ref, *, asset_id, content_sha256)` 重新验证权限/原文版本后返回私有 data。解析 layout 保留 provider 的真实布局；完整课堂资源授权映射、视觉选取与渲染由 E 接入。 |
| G | 无迁移编号需求。新数据在既有 JSON 检查点/parsed 中；不把 source_snapshots 整体放进 prompt。需要统一脚本纳入十二份长证据、文末目标、qN_M 回读、配置换版本拒绝混读、先修缺口、相反附件指令和取消竞争。下面的真实脚本仅测到 produce，属于路径交接测试。 |

## 参数追踪

| 来源 → 校验 → 消费者 | 可回读证据 |
| --- | --- |
| ExecutionContext.deadline / 真实取消状态 → monotonic 剩余时间 / heartbeat → MinerU 各步骤及 DocumentStore | `test_parse_cancellation` 首次 poll 后停止、零后续下载、无成功缓存；实际 parse_tasks 记录 batch |
| owner/preparation/source_policy/config_snapshot → scope 摘要及 guard → SourceSnapshots | `test_source_snapshots` 同页 0/5000/10000、SQL 重建、外部调用=1、跨用户/配置隔离、过期拒绝 |
| 原始 request/附件引用 → brief 校验 → 研究覆盖/独立审阅 → node_evidence | network / blocker summary 中 brief、coverage、finding 引用；相反附件联网指令不越权 |
| SourceEvidence 原文/offset/snapshot → span_registry → 紧凑视图与 read_research_evidence | `test_research_context_view` 文末目标、required q12_20、哈希版本冲突与有限恢复；没有修改原始 evidence |
| 原文件 owner/document/version/hash → DocumentStore.authorize → asset_refs/read_asset | `test_asset_references_are_owner_version_hash_bound` 跨用户及错误资产哈希拒绝；真实格式结果每份提取 1 个资产 |

## 验证命令与结果

工作目录均为本模块工作树。测试禁用业务 `.env`：

```bash
COURSE_PREPARATION_ENABLED=false PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python - <<'PY'
import dotenv, pytest
dotenv.load_dotenv = lambda *a, **kw: False
files = ['test_document_adapter', 'test_intake', 'test_harness_intake',
         'test_source_policy', 'test_parse_cancellation', 'test_source_snapshots',
         'test_research_context_view', 'test_research_adapters', 'test_research_robustness',
         'test_harness_research', 'test_research_flow', 'test_research_stages',
         'test_research_persistence', 'test_context_memory', 'test_citation_locator']
raise SystemExit(pytest.main([*(f'backend/src/tests/course_preparation/{f}.py' for f in files),
                             'backend/src/tests/test_mineru_cloud_formats.py', '-q', '-ra']))
PY
```

大组回归 **180 passed / 21 skipped / 0 failed**；之后补入配置变化的正文冲突用例，受影响快照测试 **11 passed / 1 skipped / 0 failed**。最后补充来源耗时回执后，快照与适配器回归 **32 passed / 2 skipped / 0 failed**。跳过项为未提供隔离 PostgreSQL，以及仅适用于 PostgreSQL 的行锁竞争。SQLite 权限、取消、SQL 恢复和预算记账实际执行；HTTP 协议取消/故障测试为 MockTransport，不冒充真实供应商故障注入。

真实路径命令（使用现有脚本，显式读取凭据）：

```bash
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python \
  backend/src/scripts/verify_preparation_intake_e2e.py \
  --env-file /home/zxqs_ep/Edu_AI/.env --output-dir /tmp/edu-c-sources-live/network \
  --through path --network-research
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python \
  backend/src/scripts/verify_preparation_intake_e2e.py \
  --env-file /home/zxqs_ep/Edu_AI/.env --output-dir /tmp/edu-c-sources-live/blocker \
  --through path --expect-blocker
```

首轮真实联网路径通过，206.61 秒，2 次搜索、2 次正文提取，4 段有效证据、3 个来源、2 个网页快照；总 ledger 29 calls / 316,324 tokens（含模型多轮输入，费用为既有上界记账，不是供应商账单）。仅上传 blocker 通过，115.73 秒、0 网络调用，10 calls / 84,054 tokens；核心可运行 API 目标明确 partial，未降级成伪代码路径。两轮均记录真实 Harness/Skill 调用；结果保存在 [network-summary.json](artifacts/2026-09-19-preparation-sources/network-summary.json) 与 [blocker-summary.json](artifacts/2026-09-19-preparation-sources/blocker-summary.json)。

在代码提交 `8864ee7c` 再次执行相同两条命令（output-dir 分别加 `-final`），联网路径通过，220.81 秒；expect-blocker 通过，134.96 秒且 0 次网络请求。详见 [network-final-summary.json](artifacts/2026-09-19-preparation-sources/network-final-summary.json) 和 [blocker-final-summary.json](artifacts/2026-09-19-preparation-sources/blocker-final-summary.json)。两次均只验证路径交接。JSON 分别保存 context 字节估计、每次模型 provider 真实 usage（reported_by_provider）和预算总账，没有用字节数代替 token usage。

随后 `73d6eed3` 仅补充工具耗时字段：真实 Tavily 搜索 1 次、3.273368 秒，正文提取 1 次、1.169659 秒，取得 7,860 字符正文；每次各消耗 1 个 SQL calls 预算。见 [meter-results.json](artifacts/2026-09-19-preparation-sources/meter-results.json)。此项使用隔离 SQLite、合成 owner/授权桩和真实 HTTP provider；不是整条路径的第三次复验。解析 HTTP 各次耗时见格式结果，模型与完整阶段耗时见各路径结果；本地纯函数工具未作性能基准。复现命令：`PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python docs/acceptance/artifacts/2026-09-19-preparation-sources/verify_meter.py --env-file <配置路径> --output-dir <新目录>`。

真实格式脚本：`artifacts/2026-09-19-preparation-sources/verify_formats.py --env-file <配置路径> --output-dir <新目录>`，依赖 python-docx/python-pptx/Pillow；本次临时第三方依赖装在 `/tmp/edu-c-live-libs`，未更改应用依赖。运行时 `PYTHONPATH=backend/src:/tmp/edu-c-live-libs`。脚本、合成输入与提取原文均在[格式证据目录](artifacts/2026-09-19-preparation-sources/)。

| 真测格式 | 结果/耗时 | HTTP 调用及内容核对 |
| --- | --- | --- |
| DOCX | 成功，10.232 秒，372 字符 | 7 次：建任务1/上传1/poll4/下载1；四个关键句和表格 12+30→42 保留，图片资产1 |
| 扫描 PDF（两页） | 成功，7.709 秒，309 字符 | 6 次：建任务1/上传1/poll3/下载1；两页覆盖、流程图文字、末页鉴权要求保留，资产1 |
| PPTX（两页） | 成功，7.487 秒，397 字符 | 6 次：建任务1/上传1/poll3/下载1；两页文字、表格、末页鉴权要求保留，资产1 |

逐项原文核对四句都保留。原始字符串断言有一项 false，是 MinerU 将 `INVALID_ARGUMENT` 输出为 Markdown `INVALID\_ARGUMENT`；保留原断言结果和转义说明，没有将它改成“完全逐字一致”。引用必须使用提取原文/服务端 qN_M。未进行课堂播放器视觉检查，未宣称最终用户人工签收。

TXT/MD/Markdown 本地解码/真实字符定位以自动测试验证。DOC/PPT/XLS/XLSX/PNG/JPG/JPEG/JP2/WebP/GIF/BMP/HTML 本轮仅测试路由及协议，不列为本轮真实文件通过；历史测试不替代本轮。损坏 PDF、空解析、缺页和部分解析已有单测；真实服务没有故意制造这些故障。

## 未测与后续

- E 尚需将受权资产接入课堂；G 尚需验收资源实际生成、最终课程、浏览器与统一长资料脚本。当前停止于 produce，不能称课程已交付。
- PostgreSQL 并发锁、真实取消竞态和服务商撤销远端解析尚未实测。
- 十二份长证据、预算紧凑视图和两次会话恢复为确定性测试；未完成十二份真实长文件的完整模型课程闭环。
- 旧 MinerU 缓存没有布局资产时保持可读并返回 no_assets；不做隐式全量重解析。
