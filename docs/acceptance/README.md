# OpenMAIC 迁移验收索引

- [2026-09-18 Agent 分支整合验收](2026-09-18-agent-merge-cn.md)：保留原学习 Agent，接入完整课程准备 Agent。

- [2026-09-17：学习 Agent P2](2026-09-17-learning-agent-p2-cn.md)：版本化事实、完成与自评分离、无需聊天的继续学习及隔离测试。业务环境未启用。

- [2026-09-17：课程准备 Agent 研究与学习路径阶段](2026-09-17-course-preparation-research-path-cn.md)：真实检索与正文引用、路径与审阅、持久化任务/API；整课资源尚未交付。

- [2026-09-17：学习 Agent P3](2026-09-17-learning-agent-p3-cn.md)：准确阅读上下文、只读工具、持久化答疑/取消重试；隔离验证及三个真实模型问题通过，业务环境未启用。

- [2026-09-17：学习 Agent P2](2026-09-17-learning-agent-p2-cn.md)：版本化事实、完成与自评分离、无需聊天的继续学习及隔离测试。业务环境未启用。

- [2026-09-17：课程准备 Agent 研究与学习路径阶段](2026-09-17-course-preparation-research-path-cn.md)：真实检索与正文引用、路径与审阅、持久化任务/API；整课资源尚未交付。

[课程知识库 Agent 工作流程验收](2026-09-10-course-knowledge-agent-workflow-acceptance-cn.md)：新建课程自动交接、增量方案、状态查询、显式重试、人工确认边界和浏览器 E2E 已完成自动化验收；真实链路结果见下一项。

[操作系统课程知识库真实端到端验收](2026-09-11-course-knowledge-real-operating-systems-cn.md)：真实模型、真实外网和真实发布链路已跑通；新建与增量数据链路通过，来源权威性和教师逐项需求满足度有条件通过。

[课程知识库需求理解与内容质量闭环 V2 验收标准](2026-09-11-course-knowledge-intent-quality-v2-acceptance-cn.md)：把教师需求提取、来源权威性、教学产物和逐项覆盖升级为发布硬门禁；当前待实现、待验收。

[生成工厂统一 Agent 入口验收](2026-09-10-generation-factory-agent-entry-acceptance-cn.md)：覆盖八类入口路由、极简弹窗、自然语言提取、资料权限、并发恢复和真实模型链路；实现与自动化验收已完成，真实模型扩展项有条件通过。

[报告读取回复连续性](2026-09-08-report-answer-continuity-cn.md)：修复流式文档解释被完成通知覆盖，以及历史任务投影再次改写回答的问题。

[跨对话报告查询验证](2026-09-08-cross-conversation-report-cn.md)：用户与课程权限边界、旧会话查询已完成报告、只读关联及回归证据。

最近更新：2026-09-10

状态：Phase 0–6、AI 课堂实时问答与 AI 课堂课程目录化已签收；连续授课与常驻问答体验优化、课程知识库可配置图谱先行构建待最终签收；Agent Memory V2 待实施、待验收

| 验收 | 对应规格 | Phase | 状态 |
| --- | --- | --- | --- |
| ACC-00 Web 检索层 | SPEC-00 | 1.5 前置 | 已纳入主线 |
| ACC-01 Sidecar 裁剪与部署 | SPEC-01 | 0 | 通过 |
| ACC-02 数据契约 | SPEC-02 | 全阶段 | 通过 |
| ACC-03 ParsePDF | SPEC-03 | 1 | 通过 |
| ACC-04 GenerateClassroom | SPEC-04 | 2 | 通过 |
| ACC-05 异步任务协议 | SPEC-05 | 横切 | 通过 |
| ACC-06 Provider/BYOK | SPEC-06 | 横切 | 通过 |
| ACC-07 OpenMaicClient | SPEC-07 | 横切 | 通过 |
| ACC-08 前端集成播放 | SPEC-08 | 3 | 通过 |
| ACC-09 PPTX 导出 | SPEC-09 | 4 | 通过 |
| ACC-10 视频 A 导出 | SPEC-10 | 5 | 通过 |
| [ACC-11 旧模块下线](ACC-11_旧模块下线_验收.md) | SPEC-11 | 6 | 通过 |
| [ACC-12 AI 课堂实时问答与中断恢复](ACC-12_AI课堂实时问答与中断恢复_验收.md) | SPEC-12 | 产品增量 | 通过 |
| [ACC-13 AI 课堂连续授课与常驻问答体验优化](ACC-13_AI课堂连续授课与常驻问答体验优化_验收.md) | SPEC-13 | 产品增量 | 待实施、待验收 |
| [ACC-14 课程知识库可配置、图谱先行构建](ACC-14_课程知识库可配置图谱先行构建_验收.md) | SPEC-14 | 产品增量 | 核心真实 E2E 通过；扩展运维场景待最终签收 |
| [ACC-16 AI 课堂课程目录化](ACC-16_AI课堂课程目录化_验收.md) | [课程目录化规格](../superpowers/specs/2026-09-01-ai-classroom-curriculum-resource-tree-design-cn.md) | 产品增量 | 通过 |
| [ACC-MEM-V2 Agent Memory V2 与 LangMem 集成](2026-08-31-agent-memory-v2-langmem-integration-acceptance.md) | [MEM-V2](../superpowers/specs/2026-08-31-agent-memory-v2-langmem-integration-design-cn.md) | Agent Memory | 后端闸门通过，待产品签收；[扩展评测](2026-08-31-agent-memory-v2-expanded-evaluation-report.md) |

“通过”要求对应 ACC 中的可判定标准和自动化/实物证据成立。历史或全仓既有失败必须在对应 ACC 中明确隔离，不能隐瞒为全绿。

2026-08-06 至 2026-08-12 的早期产品验收记录集中保存在 [`legacy-product-evidence/`](legacy-product-evidence/README.md)，仅用于追溯。

## 轻量 Agent RAG

[验收标准与记录模板](../superpowers/acceptance/2026-09-07-lightweight-agent-rag-acceptance-cn.md)：覆盖两阶段检索、问答与资源生成、权限及降级；当前后端已实现，产品验收待完成、待验收。

## DeepSeek Harness 首版

[普通对话与报告接入验证](2026-09-07-deepseek-harness-report-dialogue-acceptance-cn.md)：代码接入、隔离回归与真实五轮报告链路通过；当前运行服务未切换，完整生产验收待完成。

- [Harness 知识点大纲优化验收](2026-09-07-harness-knowledge-outline-acceptance-cn.md)：五项能力、真实链路、最终审阅版大纲与自动质量限制。

- [根角色与完整报告审阅流程](2026-09-08-reviewed-report-acceptance-cn.md)：正文生成、审阅、修订、版本交付门槛和真实样例。

- [2026-09-17：学习 Agent P4](2026-09-17-learning-agent-p4-cn.md)：检查、显式偏好及删除传播、来源摘要与实际界面；测试日志完整保留，业务环境未启用。
- [学习 Agent P6：迁移、切换与完整验收](2026-09-17-learning-agent-p6-cn.md)：真实模型与浏览器任务、并发、备份恢复及阶段日志。

- [课程准备第一阶段迁移至 DeepSeek Harness](2026-09-18-preparation-harness-cn.md)：附件理解与需求归纳由真实 SDK/MCP 循环执行，保留检查点与逐次用量计量。
