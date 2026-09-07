# 已生成资料的 Agent 修改：实施计划（Agent C）

状态：C 模块已实现，服务与模型分项验证完成；整体 UI/组合验收未完成。设计：[C 设计](../specs/2026-09-07-artifact-revision-design-cn.md)；验收：[C 验收](../acceptance/2026-09-07-artifact-revision-acceptance-cn.md)；[并行约定](2026-09-07-frontend-experience-parallel-handoff-cn.md)。

## 文件所有权

C 拥有 `components/generation/**`、`components/teacher/StudioPanel.tsx`、`stitch/pages/CourseResources.tsx`、新增 `stitch/artifactRevision/**`，以及后端 `chat/workflows/report/edit_runtime.py`、`chat/domain/artifact_reference.py`、新增资料修改服务和按类型适配器。必要资源存储／版本迁移由 C 负责，先定位现有文件，列在交付清单中；不要创建平行数据库。

B 拥有 ChatPanel、chatV2、useStore、共享后端 schema／调度层。C 不直接修改这些共享文件，提供精确的导出和接入说明，由 B 完成。同理，B 提供的生成 scope 透传由 C 写入其拥有的工厂文件。

## 执行步骤

- [x] C1 审计：核对 report edit runtime、当前 ReAct 主链、artifact readback、资源内容更新、发布版本和学习快照。列出实际支持类型及已有缺口，不能把旧 workflow 存在当成当前入口可达。
- [x] C2 交接契约：与 B 确定修改服务输入输出、产物引用类型、澄清持久化和结果映射；提供新模块类型与最小集成说明。开发早期完成，避免最后才发现协议冲突。
- [x] C3 目标解析与原文读取：独立实现授权候选搜索、唯一判定、版本读取，新增行为测试验证跨账号、同名资料、当前引用与“上次”语义。
- [x] C4 先完成报告闭环：原文读取→局部编辑→结构验证→版本保存，测试读取失败、歧义追问、补充意见续接、幂等及版本冲突。
- [ ] C5 扩展类型适配：按设计矩阵处理实际生成目录的各类型；保留结构约束及播放器／评分能力。逐项填覆盖表，不停留于报告示例。
- [ ] C6 版本与发布：复用现有存储，必要时做可回滚增量迁移；验证已发布资源、任务快照和学生学习记录不变。迁移在专用数据库验证，不改真实用户资料做测试。
- [ ] C7 UI：工厂完成区、资源预览加“让 AI 修改”；新增引用／修改结果组件。向 B 提供 ChatPanel 插槽、事件和聚焦接入，关闭引用与连续修改行为也要覆盖。
- [x] C8 合入 B scope 透传补丁；对新生成和原资料修改区分：新生成用当前知识点，修改保留原资料归属。
- [ ] C9 前后端联调：真实主入口走按钮及自然语言、流式及非流式；看真实原文、生成后的数据、版本和预览，不能只测服务函数。
- [ ] C10 交付：提交代码、迁移（如需）、类型覆盖表、回滚说明和验收证据。将共享接入清单交 B，等待组合回归后才标整体完成。

## 测试命令

在 `backend/src/` 使用项目 Python 环境：

```sh
python -m pytest tests/chat/test_report_edit_runtime.py tests/chat/test_report_edit_intent_parser.py tests/chat/test_report_edit_numbered_section.py
python -m pytest tests/chat/test_reply_service_v2_artifact_reference.py tests/chat/test_reply_service_v2_stream_artifact_reference.py
python -m pytest tests/chat/runtime/test_agent_artifact_readback.py
python -m pytest tests/chat/test_artifact_revision.py
```

最后一个计划新增，覆盖各类型适配、版本与权限；具体主调用链若不同，补对应测试，不能只跑旧实现。

在 `frontend/`：

```sh
node --import tsx --test "src/stitch/artifactRevision/*.test.ts"
pnpm exec playwright test tests/e2e/artifact-revision.spec.ts --project=desktop1366
pnpm build
```

新增文件后执行。真实模型冒烟在专用课程／资料副本进行，覆盖报告以及结构化类型；凭据不写入文档。

## 内部里程碑和回退

报告可作为第一个可演示里程碑，随后完成各类型，不代表范围缩减。数据库迁移须记录旧数据兼容、版本关系及回退限制；不能以恢复旧前端为理由删除已生成版本。失败时关闭新增入口，原文预览、手动编辑和既有导出应继续可用。

## C 交付说明

实际接口、文件清单、回退和集成阻塞见 [C→B 接入契约](2026-09-07-artifact-revision-integration-cn.md)。C5/C6/C7 已完成模块实现，但对应完整使用与 UI 验收未完成；C9 已通过共享 reply/SSE 四组合服务测试，浏览器最终复测发现初始化竞态。C10 交付后由 B 完成整体组合验证。
