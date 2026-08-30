# OpenMAIC 迁移验收索引

最近更新：2026-08-31

状态：Phase 0–6 与 AI 课堂实时问答已签收；连续授课与常驻问答体验优化、课程知识库可配置图谱先行构建待最终签收；Agent Memory V2 待实施、待验收

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
| [ACC-MEM-V2 Agent Memory V2 与 LangMem 集成](2026-08-31-agent-memory-v2-langmem-integration-acceptance.md) | [MEM-V2](../superpowers/specs/2026-08-31-agent-memory-v2-langmem-integration-design-cn.md) | Agent Memory | 后端闸门通过，待产品签收；[扩展评测](2026-08-31-agent-memory-v2-expanded-evaluation-report.md) |

“通过”要求对应 ACC 中的可判定标准和自动化/实物证据成立。历史或全仓既有失败必须在对应 ACC 中明确隔离，不能隐瞒为全绿。
