# 操作系统课程知识库真实端到端验收

**日期：** 2026-09-11  
**运行编号：** `2026-09-11-os-real-01`  
**课程：** `操作系统（真实E2E-2026-09-11-os-real-）`  
**课程 ID：** `course-91205880c651486aabef002a9c330617`  
**结论：** 本文前半部分保留 V1 首测历史；V2 最终复验见第 8 节，新建与增量均通过，但仍建议教师抽检教学材料。

## 1. 验收范围与环境

本次不是 API/SSE fixture 测试。浏览器通过真实教师账号操作真实前端，连接本机真实 FastAPI 服务、真实 PostgreSQL、已配置的真实模型以及真实外网检索和下载链路。测试数据保留，未改动原有 `operating-systems` 课程。

覆盖流程：

1. 创建一门新的“操作系统”隔离测试课程；
2. 由 Agent 生成三档大纲，教师选择简明版并确认图谱；
3. 执行真实检索、下载、切分、向量化、质量门禁和发布；
4. 在已发布版本上新增“Linux cgroups 与容器资源隔离”；
5. 验证增量方案拒绝与恢复、旧节点保留、新资料挂载和版本递增。

## 2. 各阶段截图

| 阶段 | 证据 |
| --- | --- |
| 登录并进入教师工作区 | [01-login-home.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/01-login-home.png) |
| 新建课程空表单与阴影提示 | [02-new-course-empty-form.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/02-new-course-empty-form.png) |
| 操作系统课程信息填写完成 | [03-new-course-filled-form.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/03-new-course-filled-form.png) |
| Agent 规划加载阶段 | [04-agent-planning.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/04-agent-planning.png) |
| Agent 三档方案生成完成 | [05-agent-proposal-ready.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/05-agent-proposal-ready.png) |
| 简明、标准、完整大纲比较 | [06-new-outline-options.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/06-new-outline-options.png) |
| 首次图谱审核 | [07-new-graph-review.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/07-new-graph-review.png) |
| 首次构建启动 | [08-new-build-started.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/08-new-build-started.png) |
| 教材发现、摄取与缺口检索阶段 | [教材发现](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/09-new-build-01-running-textbook_discovery-3.png) · [教材摄取](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/09-new-build-02-running-textbook_ingestion-10.png) · [缺口检索](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/09-new-build-05-running-gap_search-35.png) |
| 首次构建发布完成 | [10-new-build-published.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/10-new-build-published.png) |
| 增量空表单与阴影提示 | [11-increment-empty-requirements.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/11-increment-empty-requirements.png) |
| 增量需求填写完成 | [12-increment-filled-requirements.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/12-increment-filled-requirements.png) |
| 第一次方案被范围审查拒绝 | [13-increment-proposal-rejected-first-attempt.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/13-increment-proposal-rejected-first-attempt.png) |
| 同一草稿重试后方案通过 | [13-increment-proposal.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/13-increment-proposal.png) |
| 增量图谱审核：23 节点、新增 1、待完善 0 | [14-increment-graph-review.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/14-increment-graph-review.png) |
| 增量构建启动 | [15-increment-build-started.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/15-increment-build-started.png) |
| 增量检索与发布 | [缺口检索](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/16-increment-build-02-running-gap_search-35.png) · [发布完成](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/16-increment-build-29-succeeded-published-100.png) |
| 最终新增节点及 4 份挂载资料 | [17-increment-published-detail.png](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/17-increment-published-detail.png) |

## 3. 实测结果

### 3.1 新建课程与首次构建

| 指标 | 实测值 |
| --- | ---: |
| build ID | `kb-716b212c73724a6cbac74c232f3479bf` |
| 构建状态 | `succeeded / published / 100%` |
| 构建阶段耗时 | 18 分 58 秒 |
| 图谱节点 | 22（1 个根节点、5 个模块、16 个叶知识点） |
| 持久化资料 | 49 |
| 被选来源候选 | 123 |
| 抓取/摄取失败 | 18 |
| 教材候选 / 成功摄取 | 2 / 0 |
| 非 AI 覆盖率 | 100% |
| AI 资料占比 | 0% |
| 系统质量分 | 100 |
| 发布版本 | v1 |

结果说明：首次构建能从空课程生成可审核三档大纲，按简明版发布 16 个知识点；每个叶节点最终达到 3 份网页资料并建立索引。功能和数据落库成功，但候选量大、耗时较长，且主要来源为 CSDN、博客园、掘金、文档下载站和社区文章，100 分不代表权威性达到教学交付标准。

### 3.2 增量添加

教师输入：新增“Linux cgroups 与容器资源隔离”，覆盖 CPU、内存、I/O 限制、1 个 Docker 配置案例和 3 道带解析练习；保留全部已有目录与资料；优先 Linux Kernel、Docker 官方资料。

| 指标 | 实测值 |
| --- | ---: |
| build ID | `kb-31de16bb46264788904fc74e40b777ed` |
| 第一次方案生成 | 422，被范围审查正确拦截 |
| 同一草稿第二次尝试 | 通过并成功发布 |
| 实际构建阶段耗时 | 2 分 22 秒 |
| 图谱节点 | 22 → 23 |
| 原节点保留 | 22 / 22，全部保留 |
| 新增知识点 | 1 |
| 总资料数 | 49 → 53 |
| 新增资料 | 4 |
| 被选来源候选 | 9 |
| 失败项 | 4（含教材 PDF/下载失败 2、网页正文识别失败 2） |
| 系统质量分 | 100 |
| 发布版本 | v1 → v2 |

第一次 422 的原因是模型没有新增指定节点，并把 I/O 限制弱化为附带提及；独立范围审查正确拒绝了方案。第二次在同一草稿上重试后，方案新增节点并将其挂在“进程与线程”模块下，最终成功发布。这证明审查与恢复链路有效，但也反映同一清晰需求下模型方案存在波动。

## 4. 内容效果抽检

增量新增的 4 份资料实际来源为：

- 掘金 1 份；
- CSDN 2 份；
- 简书 1 份；
- Linux Kernel 官方文档 0 份；
- Docker 官方文档 0 份。

对四份落地 Markdown 做关键词核验：能找到 CPU、内存、I/O/blkio 和 `docker run` 相关内容，但未找到明确的练习题、题目、参考答案等结构，不能证明“3 道带解析练习”已交付。

因此，本次增量在“新增节点、增加资料、保留旧数据、建立索引”层面效果良好；在“遵守官方来源偏好、完整满足教学内容清单”层面不合格。当前 100 分只覆盖图谱结构、数量、非 AI 覆盖、来源字段、索引和发布原子性，没有覆盖来源权威性与教师逐项需求满足度。

## 5. 发现的问题

| 优先级 | 问题 | 影响 |
| --- | --- | --- |
| P1 | 质量门禁未校验教师逐项需求，缺少 3 道带解析练习仍得 100 分 | 可能把“不完整但数量达标”的内容直接发布 |
| P1 | 来源偏好未落实，指定官方资料但最终官方来源为 0 | 内容权威性与教师预期不一致 |
| P2 | 同一增量需求第一次连续修正后仍被审查拒绝，人工再次点击才成功 | 教师会感知为不稳定，需要明确的一键重试体验 |
| P2 | 首次构建选择 123 个候选、仅落地 49 份，耗时约 19 分钟 | 构建成本和等待时间偏高 |
| P2 | Agent 首次方案已入库后 SSE 未正常结束，且遗留一个额外空草稿 | 页面可能长时间显示处理中，并出现草稿状态混乱 |
| P2 | 首次构建高负载期间一次轮询连接被重置 | 后台构建会影响查询接口稳定性 |
| P3 | 增量规划看到的 49 份文档快照缺少标题与摘要，而页面实际有标题 | 模型无法可靠判断现有内容是否已覆盖，容易重复补充 |

## 6. 验收判定

- **新建课程功能：通过。** 从创建课程、Agent 规划、三档比较、人工确认到真实构建发布均成功。
- **增量数据安全：通过。** 旧节点 22/22 保留，资料总数增加，版本从 v1 递增为 v2。
- **失败恢复：通过。** 不合格方案被拦截，同一草稿可重试并最终发布。
- **内容完整性：有条件通过。** 基础 cgroups 内容存在，但未证明练习要求被满足。
- **来源质量：不通过。** 官方来源偏好未执行，不能以系统 100 分替代教师内容审查。
- **整体：有条件通过。** 可以继续迭代功能，但在补齐“需求逐项验收”和“来源权威性门禁”前，不建议将自动发布结果视为无需人工复核的最终教学知识库。

## 7. 自动化与原始证据

真实浏览器主流程最终结果：`1 passed (2.8m)`；发布后页面与资料明细复验：`1 passed (6.7s)`。测试脚本为 `frontend/tests/e2e/course-knowledge-real-operating-systems.spec.ts`。

结构化证据：

- [运行审计摘要](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/runtime-audit.json)
- [首次最终构建记录](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/09-new-build-final-build.json)
- [增量最终构建记录](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/16-increment-build-final-build.json)
- [前后节点与版本比较](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/comparison.json)
- [最终知识图谱](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/final-knowledge-graph.json)
- [完整截图和 JSON 证据目录](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-real-01/)

## 8. V2 优化后的最终真实复验

### 8.1 结论

2026-09-11 使用全新隔离课程 `course-44310c15c8dd4acd8d021649462b6527` 执行真实浏览器、真实模型、真实 PostgreSQL、真实外网抓取和真实向量化。Playwright 主流程 `1 passed (14.5m)`。

| 场景 | build | 结果 | 核心证据 |
| --- | --- | --- | --- |
| 新建课程 | `kb-b6dbacce7ef6462a971a4b752b3619b8` | 初次 59 分阻断；同 build 修复重试后 `published / 100` | 12 个叶节点全部覆盖，39 份文档，12 份教学材料审查分 88～100 |
| cgroups 增量 | `kb-8cc2c8640cfd4a28b31fee3782c5eb82` | `published / 100` | 27/27 旧节点保留，新增 1；Docker 2 + Kernel 3 + AI 1；案例 1 + 带解析练习 3 |

增量知识点的 `textbook_units=0`、`web_units=5`、`ai_units=1`，证明收紧后的标题级映射没有再把 OSTEP/xv6 因宽泛“进程”描述误挂到 cgroups。新增节点位于“进程与线程”下；此前挂到“虚拟内存”的真实失败促成了父章节语义门禁。所有 12 项增量检查通过，浏览器控制台错误为 0。

### 8.2 截图与结构化证据

- [新建表单详细阴影提示](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-01/02-new-course-empty-form.png)
- [Agent 方案完成](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-03/05-agent-proposal-ready.png)
- [首次构建教材映射阶段](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-02/09-new-build-15-running-textbook_mapping-25.png)
- [首次构建发布](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-02/10-new-build-published.png)
- [增量需求填写](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-03/12-increment-filled-requirements.png)
- [增量方案与图谱审核](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-03/14-increment-graph-review.png)
- [增量 AI 产物阶段](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-03/16-increment-build-50-running-ai_fallback-72.png)
- [增量发布页面](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-03/17-increment-published.png)
- [增量发布详情：正确父节点与 6 份资料](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-03-detail/17-increment-published-detail.png)
- [首次最终状态](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-02/09-new-build-final-build.json)
- [增量最终状态](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-03/16-increment-build-final-build.json)
- [节点与版本对比](evidence/2026-09-11-course-knowledge-real-operating-systems/2026-09-11-os-v2-final-03/comparison.json)

### 8.3 仍需继续优化

- 首次 Agent SSE 曾出现 BrokenPipe；持久化草稿可恢复，但自动重连和“处理中”反馈仍需完善。
- 首次从零构建历史最慢超过 20 分钟；本次修复重试约 7 分 14 秒，不能据此宣称冷启动 P95 已达标。
- cgroups AI 材料审查为 88 分，审查建议指出 I/O 限速案例最好使用 `dd/fio`，且 cgroup 路径依赖驱动；教师交付前仍应抽检。
- 真实检索曾接收 Docker `Prior Releases` 历史索引页；最终代码增加非教学标题拒绝规则后重跑，最终 6 份资料中不再包含该页面。
