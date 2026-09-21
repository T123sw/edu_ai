# 窗口 C：文件、检索与证据衔接 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 文件与网络资料处理有明确能力、可恢复快照和真实定位，长资料不因重复提取或上下文膨胀破坏链路。

**Architecture:** 保留当前资料理解与连续学习路径 Harness；改进底层解析控制、任务内网页快照和研究视图。来源权限、正文证据及缺口停止继续由程序校验。

**Tech Stack:** MinerU、Tavily/Bocha、SQLAlchemy、原生 Harness 研究工具、pytest。

**Spec:** [总计划](../2026-09-19-preparation-chain-optimization.md)、[共享契约](00-shared-contracts.md)、[已有健壮性改动](../../../architecture/2026-09-19-learning-path-robustness.md)。

## Global Constraints

- MinerU 支持格式继续交给 MinerU；文本文件保持原生读取。搜索摘要不得替代正文。
- uploaded_only 不得联网；附件、网页和缓存都不能授予新权限。
- 缺口不得变成排除项，不把真实 API 目标降低成伪代码；保留当前 blocker 行为与真实失败样例。

## 文件范围与交接

- 修改：`adapters/documents.py`、`adapters/document_store.py`、`adapters/sources.py`、`research_sources.py`、`research_agent.py`、`harness_research.py`、`research_factory.py`、`research_contracts.py`、`research_stages.py`、`intake.py`、`source_errors.py`、研究/需求 Skills。
- 修改共享解析器：`backend/src/app/integrations/pdf/mineru_cloud.py`，新增参数必须保留其他入口兼容。
- 新建：`source_snapshots.py`、`research_context_view.py`；需要新持久化表时将模型和迁移需求交 G 分配编号。
- 测试：既有 document/intake/source_policy/research_robustness 测试；新增 `test_source_snapshots.py`、`test_parse_cancellation.py`、`test_research_context_view.py`。
- `context.py`/provider 由 B 拥有；C 提供受预算约束的研究视图函数供 B 调用，不并行编辑该文件。

## Task C1：解析生命周期与可用性

- [ ] 为解析器加可选 deadline/canceled 控制，接口向旧调用兼容；由准备任务调用方传真实控制句柄，不把句柄写入检查点。
- [ ] 在提交远端、上传、每次轮询、下载结果前检查剩余时间和取消；HTTP timeout 不超过剩余预算。取消后不得登记为已读成功，记录真实已发生的远端任务引用。
- [ ] 轮询控制的验收代码采用注入时钟/传输，避免真实等待 15 分钟：

```python
def assert_canceled_parse_stops_before_next_poll(run_parse, poll_count):
    # 测试夹具在首轮 poll 返回后设置取消；run_parse 由本文件的假传输构建。
    import pytest
    with pytest.raises(Exception) as error:
        run_parse()
    assert getattr(error.value, 'code', '') == 'CANCELED'
    assert poll_count() == 1
```

- [ ] 上述测试中的可调用夹具必须在新测试文件定义并驱动真实解析控制代码；不能 mock 掉待验证的取消分支。
- [ ] 测试正常 DOCX、文本、扫描 PDF、表格/幻灯片的结构样例，以及空文档、损坏、核心解析缺页。保留真实定位，Office 无页码时不伪造页码。
- [ ] 给 E 输出可选的解析图片/版面资产引用契约，来源带 owner/document/version/hash；原始资产不得匿名外泄，提取不到时明确无资产。完整视觉接入由 E 完成。
- [ ] 真测 DOCX、PDF、PPTX 至少各一份，分别记录解析成功和人工核对覆盖结果；其余支持格式列清已测/未测，不概括为全格式通过。

## Task C2：网页快照分页与检索能力协商

- [ ] 新增任务内不可变正文快照，最小接口：`SourceSnapshots.get_or_fetch(url, *, read, scope, timeout) -> SourceSnapshot`，snapshot 含 canonical_url/content/content_sha256/retrieved_at；scope 包含 owner、preparation、来源策略与配置版本。
- [ ] 原 `fetch_source` 的 offset/limit 从同一快照切片；首次提取才计外部 I/O，分页和恢复不重新请求整页。缓存命中前仍检查来源授权与任务状态。
- [ ] 在测试中用计数 read 返回超过 10,000 字符正文，依次请求 0、5000、10000，断言外部 read 仅一次、三个片段同属一个快照且可拼回正文；重启后再分页仍复用同一版本。
- [ ] URL 重定向的 canonical identity、过期策略、提取失败不缓存为成功、不同用户/配置不串缓存，均分别测试。旧 evidence 仍能读取，不能用新网页覆盖其已验证引文。
- [ ] 提供可用能力结构：search provider、extract provider、各自配置/健康状态。Tavily 临时失败且 Bocha 可用时有限回退搜索；正文能力缺失时明确 EXTRACT_NOT_CONFIGURED，不假装搜索结果能直接支持路径。
- [ ] 统一 429/超时/5xx、认证、权限、无正文的类别与有限重试；每次外部尝试都计预算，来源/查询达到上限后换来源或输出 blocker。

## Task C3：长资料上下文与覆盖判断

- [ ] 为 B 提供 `build_research_context_view(state, *, required_ids, max_bytes) -> dict`，优先保留原要求、未解决缺口、已读定位、结论及精确引用；内容省略带明确标记和可读取的来源 ID。
- [ ] 已读证据的短句 ID 必须能由工具回读，不能只摘要掉原文再假称逐字校验。检索回执不重传旧候选，汇总不反复携带全部重复正文。
- [ ] 通过分页、独立研究会话恢复或有验证的紧凑视图控制预算；不取消 context guard，不单纯将上限翻倍。当前字节估计与实际 usage 分开报告。
- [ ] 测试多附件、目标位于长文后部、先修证据缺口、版本冲突和相反附件指令；每条 requirement 的 coverage 必须与实际能力匹配。
- [ ] 使用现有 `verify_preparation_intake_e2e.py` 跑联网路径和 expect-blocker，再把长资料用例交 G 的统一脚本。只到 produce 的测试明确标成路径交接测试。

## 完成门槛与交付记录

- [ ] 真实文件内容进入证据及后续生成；网页分页/恢复不重复提取；取消与超时有界；无来源能力时给具体失败。
- [ ] 交 A 的 brief/引用兼容说明、交 B 的上下文接口、交 E 的资产接口、交 G 的迁移与真实样例清单齐全。
- [ ] 记录每种工具的调用数、耗时、解析缺陷、有效证据和未测范围，而不是只记录 HTTP 200。
