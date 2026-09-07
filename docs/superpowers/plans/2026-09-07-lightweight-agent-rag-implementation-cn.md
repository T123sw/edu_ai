# 轻量 Agent RAG 实施计划

日期：2026-09-07
状态：后端实现及定向测试完成，产品验收待执行；未勾选项仍需补充证据。

依据：[功能规划](../specs/2026-09-07-lightweight-agent-rag-design-cn.md) · [验收标准](../acceptance/2026-09-07-lightweight-agent-rag-acceptance-cn.md)

## 1. 实施原则

先实现共用选择器和编排，再接入各入口，最后验证产品链路。保留现有全文来源模式和片段检索算法。无需重建索引或迁移文档数据。开始前查看 git status，保留已有未提交修改。

## 2. 工作分解

### P1：确认入口与固定契约

- [x] 沿 query、rag_query_stream、rag_search_tool、fetch_course_rag_snippets、search_many 检查运行时调用链。
- [x] 搜索 hybrid_search、enhanced_hybrid_search_with_hyde、retrieve_documents 及全文读取调用，记录哪些是产品 RAG 入口、哪些是评估或全文模式。
- [ ] 确认各入口的 owner、course_id、include_in_search、文档状态、显式选择传递与校验位置，修复接入路径上的缺失校验。
- [x] 固定候选记录、选择输出、trace 字段和公开标识映射；按规划落实降级表。
- [x] 确认已有 LLM 调用设施支持结构化解析、实际超时和可注入测试替身；超时须作用于实际请求。

产物：入口矩阵和已固定契约；不得仅覆盖非流式问答。

### P2：实现文档名选择器

拟新增：`backend/src/modules/rag_v2/document_selector.py`。
配置位置：`backend/src/modules/rag_v2/rag_main/core/config.py`；如支持环境变量，同步根目录 `.env.example`。

- [x] 实现候选编号、名称规范化、稳定词项预筛选及数量/字符预算。
- [x] 实现单次模型选择、结构校验、编号白名单、去重、上限和各类降级原因。
- [x] 实现零候选和单候选快捷路径。
- [x] 为同名文档、中文问题、注入式文件名、无效 JSON、非法编号、超时和超大候选集合编写行为测试。

完成条件：所有最终文档均来自原始允许范围；正常选择最多 5 个；最多一次模型调用。

### P3：实现共用两阶段检索编排

主要修改：`backend/src/modules/rag_v2/rag_main/system.py`。

- [x] 增加共用编排，接收业务已校验候选，调用选择器后构造 index_key/source_key 过滤集合。
- [x] 空范围直接返回，禁止经 `allowed_sources or None` 变成全库检索。
- [x] 普通和增强检索都在调用向量/关键词检索前传入最终过滤集合。
- [x] 检索后再次约束来源，防止别名或分支处理造成范围扩大。
- [x] 返回片段及 trace；保留 retrieve_documents 的底层行为和现有重排、多模态出处。
- [x] 测试选择发生于检索前、正文范围、空结果不重试及降级仍受原范围约束。

完成条件：同一套选择逻辑可以服务问答和资源生成，且不依赖最终答案生成。

### P4：接入非流式与流式问答

主要修改：`rag_main/system.py`、`rag_main/api.py`；按需修改 `app/chat/tools/agent_tools.py` 与 `app/integrations/rag_client.py`。

- [x] query 在问题重写和候选授权完成后调用共用编排。
- [x] rag_query_stream 替换独立检索分支，保证普通和增强路径均接入。
- [ ] 检查聊天 Agent 的 use_rag/allow_rag 与 selected_doc_ids、课程别名传递，确保一次检索仅选择一次。
- [x] 保持 answer、sources、流式事件和媒体引用兼容；内部 trace 不泄露物理路径。
- [ ] 测试关闭 RAG 零调用、多轮问题、显式选择、空课程、跨用户和流式来源一致性。

### P5：接入资源生成

主要修改：`app/services/classroom_service.py`、`app/services/generation_task_handlers.py`；按需调整 `generation_source_resolver.py` 的内部元数据传递。

- [x] fetch_course_rag_snippets 与 search_many 使用共用编排，传入经课程与参与状态校验的候选。
- [x] 生成查询包含具体主题与要求，避免仅以 resource_type 作为模型选择依据。
- [ ] 验证 course_auto 的报告、测验、课堂等实际支持的资源类型；将最终受支持入口清单记录到验收结果。
- [x] 保留 selected_documents → read_many 的全文契约与 none 的零检索行为。
- [x] 检查已解析来源注入路径，避免 classroom_service 对同一次资源生成重复检索。
- [x] 测试最终生成器收到的上下文仅含选中文档片段；降级行为符合各生成器原有错误策略。

### P6：回归与真实验收

建议新增行为测试文件（实施时创建）：

- `backend/src/tests/chat/test_rag_document_selector.py`
- `backend/src/tests/chat/test_rag_two_stage_retrieval.py`
- `backend/src/tests/chat/test_rag_two_stage_stream.py`
- `backend/src/tests/services/test_generation_two_stage_rag.py`

- [ ] 运行上述测试，再运行现有文档解析、来源匹配、用户隔离、生命周期和生成来源相关测试。
- [ ] 在项目配置好的 Python 环境中，从 backend/src 执行以下定向测试命令；记录实际解释器、命令和结果。

```bash
python -m pytest tests/chat/test_rag_document_selector.py tests/chat/test_rag_two_stage_retrieval.py tests/chat/test_rag_two_stage_stream.py tests/services/test_generation_two_stage_rag.py -q
python -m pytest tests/chat/test_rag_v2_document_resolver.py tests/chat/test_rag_v2_system_source_matching.py tests/chat/test_rag_v2_system_public_owner_access.py tests/test_rag_document_lifecycle.py -q
```

以上第一组文件尚未创建，命令是实施后的检查要求，不是当前通过记录。生成相关回归文件以 P1 核实后的实际路径补充。

- [ ] 完成验收文档全部必测场景，保存筛选范围、底层检索参数、最终来源及产品结果。
- [ ] 对同一批固定问题比较原范围检索与两阶段检索，记录候选缩减、相关片段命中和选择耗时，不预设性能提升。
- [ ] 仅在修改前端协议或页面时运行对应前端测试和构建；纯后端改动仍需通过浏览器验证问答及资源生成入口。
- [ ] 更新验收结果、已知问题和最终调用链，全部必要证据具备后再标记完成。

## 3. 发布与回退

增加统一配置开关控制文档选择阶段；关闭后恢复经过权限校验的原范围片段检索。开关不得绕过权限、参与状态或显式选择限制，也不应改变全文模式。先在验收环境开启，通过后随正常版本流程启用。无需索引迁移；模型异常按规划自动降级。

## 4. 交付物

选择器、共用编排、所有有效 RAG 入口适配、配置说明、行为测试和填实的验收记录。文档编写完成与功能验收完成分别记录，不提前勾选实施任务。

## 5. 本次实施记录

- 新增四个计划内测试文件，32 项定向测试通过；扩大回归 143 通过、3 失败。3 项失败均在 HEAD 基线复现，证据见验收文档。
- 使用 `/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python`；该环境原来缺少测试运行器，本次安装 pytest、pytest-asyncio。
- 新增 `backend/src/scripts/evaluate_rag_document_selection.py`，使用合成文件名执行真实模型冒烟验证，不打开生产文档索引。最终三个案例全部通过。
- 浏览器勾选问答、各资源成品与课堂播放、五主题三轮对照测量尚未执行；本次未重启或部署线上服务。
- 因存在待执行验收，不将 P6 或整体功能标为已签收。
