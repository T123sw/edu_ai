# 轻量 Agent RAG 验收文档

日期：2026-09-07
状态：后端定向测试通过，真实模型选择冒烟通过；浏览器产品验收待执行，尚未最终签收。

对应：[功能规划](../specs/2026-09-07-lightweight-agent-rag-design-cn.md) · [实施计划](../plans/2026-09-07-lightweight-agent-rag-implementation-cn.md)

## 1. 验收目标

证明启用 RAG 的问答及采用 RAG 检索的资源生成先按文档名选范围、后在范围内检索正文；权限不扩大、禁用不触发、全文模式不受影响。仅观察答案“像是正确的”不足以通过，必须检查实际检索过滤参数与来源。

## 2. 固定测试资料

建立隔离测试用户 A/B、课程 C1/C2，所有资料包含可辨认的测试标记，不使用真实私人文档。

| 编号 | 归属与名称 | 正文设计 |
| --- | --- | --- |
| D1 | A 可访问，C1，《树与二叉树.pdf》 | 前中后序遍历知识，标记 TREE_A |
| D2 | A 可访问，C1，《排序算法.pdf》 | 排序知识，标记 SORT_A；加入少量“二叉树”干扰词 |
| D3 | A 可访问，C1，《数据库事务.pdf》 | 事务知识，标记 DB_A |
| D4 | A 可访问，C1，《课程资料.pdf》 | 标题笼统但正文包含遍历，标记 GENERIC_A |
| D5 | B 私有，《树与二叉树.pdf》 | 标记 PRIVATE_B |
| D6 | C2 独立课程，《树与二叉树.pdf》 | 标记 COURSE_C2 |
| D7 | A 可访问，C1，但 include_in_search=false | 标记 DISABLED_A |
| D8 | A 可访问，C1，独立 ID，与 D1 同名 | 补充遍历例题，标记 TREE_SECOND |

另设空课程、已删除/不可用文档、101 个以上候选、名称超字符预算、名称含指令的资料。使用独立检索调用替身确定性验证边界，使用真实模型验证语义选择；两类结果分别记录。

## 3. 必测场景

下表为完整通过标准；实际执行范围与证据见第 7 节，未覆盖部分仍待执行。

| ID | 场景与操作 | 通过标准 |
| --- | --- | --- |
| A01 | 问答未启用 RAG | 选择器和片段检索调用均为 0 |
| A02 | 启用 RAG，问二叉树遍历 | 正常选择结果包含 D1；候选多于选中数；底层检索前已限定来源，最终出处不超范围 |
| A03 | 手动仅选 D1、D2 后问遍历 | 模型候选和最终检索范围均不含其他文档 |
| A04 | 使用 C1 上下文检索 | 不含 D5、D6；D7 不参与检索；按实际课程共享权限验证 D1/D8 |
| A05 | 空课程、无效选中文档、全部禁用分别请求 | 无模型及向量库调用，不以 None 放开来源 |
| A06 | D1、D8 同名，替身指定其中之一 | 按 ID 精确选择，不合并身份、不扩大来源 |
| A07 | 多轮“它的中序遍历呢” | 有效问题保留历史所指主题，选择依据不是孤立代词 |
| A08 | 非流式、流式及各自增强检索分支 | 每次选择最多一次；所有分支均传限定来源；事件与引用兼容 |
| A09 | 模型返回非法 JSON、非法 ID、超时、不可用分别测试 | 降级至原始允许范围，原因可区分，不越权、不重试选择 |
| A10 | uncertain、no_match、空选择分别测试 | 使用同一范围内降级策略，不谎称文档筛选成功 |
| A11 | 仅一个候选 | 跳过选择模型，仅检索该文档 |
| A12 | 正常选中文档但片段为空 | 不扩大范围；按现有业务无资料行为处理，不编造出处 |
| A13 | 同时询问遍历与排序 | 真实模型可选 D1/D2 等对应文档；返回片段支持两主题；不超过文档上限 |
| A14 | 候选超过 100 或名称超过预算 | 预筛选稳定，模型输入不超预算，最终选择仍合法；记录是否漏掉目标文档 |
| A15 | 名称含指令、路径或同名干扰 | 不执行名称指令；模型请求不含物理路径；输出标识经白名单校验 |
| A16 | course_auto 生成二叉树主题资源 | 对所有当前受支持资源类型验证共用编排；生成器上下文仅含最终范围片段；无重复检索 |
| A17 | AI 课堂直接补充 RAG 来源 | fetch_course_rag_snippets 经相同选择规则；产物正常生成、打开且来源正确 |
| A18 | selected_documents 全文生成 | 保持原全文上下文，未悄悄改为片段；不新增文档选择调用 |
| A19 | 资源来源 none | 无选择及 RAG 检索调用，生成路径正常 |
| A20 | 缺少具体生成主题 | 不用泛化资源类型误选文档；参数校验或降级可追踪 |
| A21 | 回退开关关闭 | 恢复原允许范围检索，仍遵守所有权限与选择限制 |
| A22 | 已有图片、视频、正文出处 | 引用仍可解析，媒体关联不因选择阶段损坏；无内部路径新增泄露 |
| A23 | 未授权、已删除或不可用资料混入候选输入 | 在进入模型及检索前排除；测试记录候选校验层位置 |

## 4. 证据要求

每个场景记录：执行日期、代码提交/工作区版本、测试方法、输入、配置、候选数、预筛选数、选中文档、实际 allowed_sources、最终来源、是否降级及原因、选择耗时、模型调用次数、结果和证据路径。

自动化测试至少断言实际调用参数与输出来源，不能仅匹配源码字符串。真实验收至少包括：浏览器勾选 RAG 问答、course_auto 资源生成、AI 课堂生成、禁用 RAG 和一次降级。保存请求/日志及可打开产物，截图只作为辅助证据。

测量固定主题：遍历、排序、事务、跨文档比较、标题笼统资料。使用相同文档集合与片段 top_k 比较选择关闭和开启，各执行 3 次，记录原始数据；区分正常选择与降级。至少报告目标片段是否命中、选择耗时和最终范围大小，不以候选缩减率代替检索质量。

8 秒为选择调用超时配置，不能当作端到端时延承诺。测量发现的关键主题漏检须修复并重验，或明确记录为未通过；不得仅报告成功示例。

## 5. 通过门槛

- A01–A23 均有明确结果及证据；适用产品入口不得以“工具单测通过”替代验证。
- 权限、空范围、关闭 RAG、用户选择范围等确定性边界全部通过，越权来源数量为 0。
- 正常选择案例确实缩小范围且在片段检索前生效；所有降级原因可追踪。
- 新增行为测试与受影响回归通过；既有失败单独列出依据和影响。
- 问答、资源生成和全文来源兼容均有真实记录；无未解决的阻断问题。

## 6. 执行记录模板

| 日期 | 场景 ID | 版本/环境 | 方法/命令 | 实际结果 | 证据路径 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| 待填写 | A01–A23 | 待填写 | 待执行 | 无 | 无 | 待验收 |

| 问题 | 影响场景 | 严重程度 | 处理及复验 | 状态 |
| --- | --- | --- | --- | --- |
| 尚未执行，暂无实测问题记录 | — | — | — | 待验收 |

最终签收人：待填写。签收日期：待填写。最终结论：待验收。

## 7. 2026-09-07 实际执行结果

### 7.1 自动化测试

解释器：`/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python`；工作目录：项目 `backend/src`；版本：本次未提交工作区。

```bash
python -m pytest tests/chat/test_rag_document_selector.py tests/chat/test_rag_two_stage_retrieval.py tests/chat/test_rag_two_stage_stream.py tests/services/test_generation_two_stage_rag.py -q --tb=short
```

结果：**32 passed**，2.82 秒。[定向测试记录](evidence/2026-09-07-lightweight-agent-rag/focused-tests.txt)。

覆盖：A01、A03、A05–A06、A08–A12、A15、A19–A21、A23 的相关后端边界；A04 覆盖用户隔离和禁用/不可用来源；A14 验证大集合名称预算；A16 验证真实共用编排向资源 reader 输出限定片段。此处不表示每一场景的浏览器或真实模型要求已完成。

扩大回归执行上述四个文件，并加入：

```text
tests/chat/test_rag_v2_document_resolver.py
tests/chat/test_rag_v2_system_source_matching.py
tests/chat/test_rag_v2_system_public_owner_access.py
tests/chat/test_rag_llm_transport.py
tests/chat/test_rag_v2_runtime_import.py
tests/test_rag_document_lifecycle.py
tests/test_generation_source_resolver.py
tests/test_generation_task_handlers.py
tests/test_classroom_service.py
tests/test_classroom_generation_sources.py
tests/test_generation_source_provenance.py
```

结果：**143 passed、3 failed**，28.49 秒；该轮在最终新增两个选择器用例之前执行。[回归记录](evidence/2026-09-07-lightweight-agent-rag/regression-tests.txt)。既有全文/none 来源、任务来源与媒体 URL 测试包含在此范围中。

| 失败 | 基线复核 | 影响与处理 |
| --- | --- | --- |
| runtime_system_uses_host_storage_and_host_auth | [基线记录](evidence/2026-09-07-lightweight-agent-rag/baseline-storage.txt) | 测试写死仓库 storage 路径，当前部署配置使用外部数据目录；本次未修改存储策略 |
| merges_knowledge_graph_as_third_layer，asyncio/trio 两例 | [基线记录](evidence/2026-09-07-lightweight-agent-rag/baseline-regression.txt) | 预期的知识图谱上下文缺失；在原课堂服务代码上同样失败，本次未修改图谱路径 |

基线方法：读取 `git show HEAD:<对应模块>`，在独立 Python 进程内装载该模块代码，再执行相应测试；未覆盖工作区文件。

### 7.2 真实模型验证

使用部署环境已有模型配置和四个合成文件名，不读取生产资料、不写入知识库。复现命令（项目根目录）：

```bash
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python backend/src/scripts/evaluate_rag_document_selection.py --output /tmp/rag-selection.json
```

[最终结果](evidence/2026-09-07-lightweight-agent-rag/live-selector-final.json)：

| 问题 | 选中文档 | 候选缩小 | 选择耗时 |
| --- | --- | --- | --- |
| 二叉树中序遍历 | D1 树与二叉树 | 4 → 1 | 5.60 秒 |
| 排序算法练习 | D2 排序算法 | 4 → 1 | 4.22 秒 |
| 遍历与排序比较 | D1、D2 | 4 → 2 | 7.99 秒 |

三个案例均无降级，达到预期选择。[首次试跑](evidence/2026-09-07-lightweight-agent-rag/live-selector.json)中跨主题案例出现一次 model_or_parse_error 并退回四个原始候选；保留该记录，不能据最终一次成功宣称稳定性或性能达标。

### 7.3 待完成验收

- A02、A07、A13 的完整多轮问答及实际正文证据验证。
- A16 各资源类型浏览器生成、A17 课堂产物打开播放、A18–A19 页面操作兼容性。
- A14 大集合的真实模型漏选评估、A22 实际媒体点击，以及固定五主题各三轮的开关对照测量。
- 当前已有流式接口与资源 reader 集成测试，尚无浏览器登录态和成品操作证据；不能替代上述验收。

本次未启动或重启生产服务，未提交或部署。默认选择开关为开启，新的后端进程加载代码后生效；可通过 `RAG_DOCUMENT_SELECTION_ENABLED=0` 关闭选择阶段。最终结论仍为：**后端实现完成，产品验收待完成**。
