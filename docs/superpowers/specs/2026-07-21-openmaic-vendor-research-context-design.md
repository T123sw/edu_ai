# OpenMAIC Vendor 基线与 researchContext 接缝设计

## 1. 目标

将 OpenMAIC 以普通子目录 `openmaic-sidecar/` 纳入 edu_ai 主仓库统一版本管理，并基于可追溯的干净上游提交增加最小 `researchContext` 接缝，使 edu_ai 后续可以把 Web/RAG/教材上下文传入 OpenMAIC 课件生成流水线。

本轮只交付干净 vendor 基线和三处 TypeScript 生产代码补丁，不接 Python Client、异步 Job、数据库、前端播放器，也不执行真实 LLM 生成。

## 2. 仓库形态与上游基线

- `openmaic-sidecar/` 是 edu_ai 主仓库中的普通目录。
- 不使用 Git submodule、git subtree 或嵌套 `.git`。
- 上游仓库固定为 `https://github.com/THU-MAIC/OpenMAIC.git`。
- 初始基线固定为提交 `b516427d272364f07cc54e5eb9c8a66278e827b3`。
- vendor 内容从该提交的 Git archive 生成，只纳入上游在该提交中跟踪的文件，不携带源工作区的未提交修改、日志、缓存或本地密钥。
- `openmaic-sidecar/.env`、`node_modules/`、`.next/` 等本地产物继续被忽略；上游跟踪的 `.env.example` 必须纳入主仓库。

基线导入和功能补丁分为独立提交。这样更新上游时可以先替换基线，再单独重放 edu_ai 接缝，避免把 1400 余个上游文件与本地行为修改混在同一个 diff 中。

## 3. 生产代码接缝

生产代码只修改两个上游文件，并新增一个测试文件：

1. `openmaic-sidecar/lib/server/classroom-generation.ts`
   - `GenerateClassroomInput` 新增 `researchContext?: string`。
   - 在内部 Web 搜索结束后，将 Web 搜索上下文与外部注入上下文合并。
   - 合并顺序固定为 Web 搜索结果在前、外部注入内容在后，中间使用两个换行符。
   - 任一来源为空时直接使用另一个来源；两者都为空时保持 `undefined`。

2. `openmaic-sidecar/app/api/generate-classroom/route.ts`
   - 从请求 JSON 中读取 `researchContext`。
   - 只有非空字符串才写入 `GenerateClassroomInput`，与 route 现有可选字段处理方式保持一致。
   - 不改变鉴权、Job 创建、响应结构或其他 provider 参数。

3. `openmaic-sidecar/tests/server/classroom-research-context.test.ts`
   - 这是本轮新增的行为测试文件，不属于生产补丁。
   - 测试 route 输入构造保留非空外部上下文。
   - 测试 Web 与外部上下文叠加、仅 Web、仅外部、全部为空四种行为。

为避免依赖真实模型和复杂 Job 生命周期，route 字段组装和上下文合并可以提取为同文件内的纯函数并导出给 Vitest 使用。纯函数仍位于上述两个生产文件中，不扩大生产文件数量或接口范围。

## 4. 数据流

```text
edu_ai（后续 Phase）
  -> POST /api/generate-classroom
     body.researchContext
  -> route.ts 构造 GenerateClassroomInput
  -> generateClassroom()
     -> 可选 OpenMAIC 内部 Web search
     -> merge(webContext, input.researchContext)
  -> generateSceneOutlinesFromRequirements(..., { researchContext })
```

外部内容是领域补充，不替代 LLM 基座能力。`enableWebSearch=false` 时仍能只消费外部上下文；外部上下文为空时保持上游原行为。

## 5. 补丁归档与升级方式

在 `docs/spec/patches/` 保存：

- 上游仓库和固定提交哈希。
- 三处生产代码修改的目的与不变量。
- 专项测试命令。
- 从新上游版本更新 vendor 后重放/人工复核补丁的步骤。
- 一份只包含本地接缝改动的可重放 patch，不包含 vendor 基线文件。

升级时先导入新的干净上游快照，再重放 patch，运行专项 Vitest、TypeScript 检查和 sidecar 健康检查。若上游已经原生支持外部 `researchContext`，应删除重复接缝并迁移测试，而不是双重合并。

## 6. 测试策略

严格按 TDD 实施：

1. 先写 route 透传与上下文合并测试并确认因功能缺失而失败。
2. 最小修改三个生产接缝，使专项测试通过。
3. 运行完整 Vitest，确认没有破坏上游行为。
4. 运行 `pnpm exec tsc --noEmit`，确认类型字段和 route 组装一致。
5. 启动 sidecar 后检查 `GET /api/health` 返回 200。

测试不调用真实 LLM、Web Search 或付费 API；这些属于 Phase 2 端到端验收。

## 7. 错误与边界处理

- `researchContext` 缺失或空字符串：视为未提供，不改变上游行为。
- 内部 Web Search 失败：沿用上游降级逻辑，若有外部上下文则仍传给大纲生成。
- 外部上下文与 Web 上下文同时存在：只拼接一次，不覆盖、不短路。
- 本轮不新增长度截断、内容审核或 provider 安全策略；这些由后续 edu_ai 编排层和既有 OpenMAIC 边界处理。

## 8. 验收标准

- `openmaic-sidecar/` 不含独立 `.git`，由 edu_ai 主仓库直接跟踪。
- vendor 基线能对应上游提交 `b516427d272364f07cc54e5eb9c8a66278e827b3`，差异仅为已归档的本地接缝。
- 上游 `.env.example` 被跟踪，真实 `.env` 仍被忽略。
- `GenerateClassroomInput` 接受可选 `researchContext`。
- route 透传非空 `researchContext`。
- Web 与外部上下文按规定顺序叠加，单源和空值行为正确。
- 专项 Vitest、完整 Vitest、TypeScript 检查通过。
- sidecar 健康检查返回 200。

## 9. 非目标

- Python `OpenMaicClient` 与 `classroom_service`。
- edu_ai Job、数据库表、校验器和落库。
- 前端 DSL/renderer 集成。
- TTS、图片、视频和媒体迁移。
- PBL 接入。
- 真实模型生成和内容质量验收。
