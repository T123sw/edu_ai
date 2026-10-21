# Sandpack 算法练习 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.
>
> 本项目执行选择：默认采用 `executing-plans` 在当前会话逐项执行，未获用户或适用指令授权不启用子代理。本次已获用户“开始执行，直到最后的端到端验收”授权；按所选执行技能完成实现及复审。生产部署仍单独交接。

**Goal:** 用户输入快速排序后获得一个可编码、运行、检查、保存恢复的 JavaScript 单任务练习。

**Architecture:** 后端产生结构化教学候选，使用固定契约和浏览器执行器验证，发布不可变练习。前端以左侧任务目录和 Sandpack 原生组件承载学生工程，显式运行时把源码快照交给预览内可终止 Worker。个人工作区、生成产物和运行报告分别存储。

**Tech Stack:** 现有 React 18 / Vite 6 / TypeScript、FastAPI / Pydantic / SQLAlchemy、durable task、PostgreSQL、Playwright；已锁定 `@codesandbox/sandpack-react@2.20.0`，真实托管运行兼容性已验证。

**Spec:** [Sandpack 算法练习接入设计](../../architecture/2026-10-13-sandpack-algorithm-practice-design-cn.md)。执行每项任务前同时读取设计中的对应章节。

## 执行记录（2026-10-13）

P0—P4 的源码与验收目标已实现，最终证据以[验收记录](../../acceptance/2026-10-13-sandpack-algorithm-practice/README.md)及其 `verification.json` 为准。以下勾选表示目标已落实；实际文件组织与示例命令有这些调整：

- `runState` 断言合并在 `protocol.test.ts`；装配、保存和状态交互主要由 `pbl.spec.ts` 的真实编辑器浏览器测试覆盖，没有为示例中每个测试文件名单独建文件。
- 后端测试统一通过 `scripts/pbl/isolated.py` 启动，避免生产 `.env` 覆盖测试存储；PostgreSQL 并发和迁移在独立数据库/schema 中验收。
- 前端 `tsc` 已执行并与修改前基线比较：既存 146 项去重诊断，本次没有新增；不能将勾选理解为全仓类型检查通过。
- 保存恢复最终复审修复了冲突版本读取失败、报告上传期间继续编辑两处问题，并补充响应丢失后的幂等重放测试。
- 未提交、合并或部署；生产迁移未执行。验收构建 `dist-pbl` 指向隔离后端，不可作为正式发布包。

## Global Constraints

- 首个交付样例为 JavaScript 快速排序单任务练习。
- 函数约定：`export function quickSort(array)`，有限数字数组输入，升序新数组输出，不修改输入，保留重复元素。
- `tasks` 使用数组，首版严格为一个任务；不为一个算法拆出强制步骤。
- 学生可编辑范围：`/src/algorithm.js`；其他文件由平台模板提供。
- 模型不生成用户 ID、数据库 ID、运行域名、文件权限、依赖版本、任务完成状态或安全配置。
- 复用 `SandpackProvider`、`SandpackLayout`、`SandpackCodeEditor`、`SandpackPreview`；左目录、主体工作区，无固定聊天栏。
- `index.js` 不直接 import `/src/algorithm.js`；学生源码仅在显式运行时进入 Worker。
- 首版不使用 `SandpackTests` 作为唯一判题入口。
- 每例默认 2 秒、整次检查默认 15 秒；停止或超时从 Worker 外部终止，结束后能够重跑。
- 运行结果标记 `browser_reported`；功能通过不代表算法方式和知识掌握已验证。
- 不改旧模拟实验 HTML 协议；不改 AI 课堂生成；不执行业务数据迁移、服务重启或部署作为写文档的一部分。
- 现有工作区存在大量未提交改动，实施时逐路径检查，不重置、覆盖或一并提交其他工作。

## 交付顺序与阶段门槛

| 阶段 | 对应任务 | 可验收产物 | 后续依赖 |
| --- | --- | --- | --- |
| P0 运行兼容性 | 1 | 固定样例在真实 Sandpack 中运行、停止、重跑 | 不通过时不进入业务接入 |
| P1 固定练习闭环 | 2、3、4 | 类型协议、可靠执行器、目录和原生工作区 | 不依赖模型和生产数据库 |
| P2 保存与 API | 5、6 | 本人工作区、版本冲突、运行历史、创建接口 | 使用独立测试数据库 |
| P3 自动生成 | 7 | 模型候选、验证、修复、恢复、发布 | 使用与前端相同的执行器 |
| P4 正式入口与验收 | 8、9 | 首页开始、任务跳转、真实模型完整流程 | 后续部署单独记录 |

不按理想情况给出固定天数。任务 1 先消除外部 bundler、iframe 和 Worker 兼容性不确定性，再根据实际结果估算剩余工作。

## 文件与接口分工

后端新增 `app/pbl/` 和 `api/pbl.py`；前端新增 `src/pbl/`；原生运行器唯一来源为 `src/pbl/runtime/`。具体文件在各任务中列出，禁止为快速排序分别做两套检查器。

以下公共接口名称在各任务间保持一致：

```ts
type RunMode = "sample" | "check";
type CaseStatus = "passed" | "failed" | "error" | "timeout";
type RunStatus = "passed" | "failed" | "error" | "timeout" | "canceled";

type NumberCase = {
  id: string; label: string; input: number[]; expected: number[];
};
type RunRequest = {
  runId: string; exerciseId: string; artifactVersion: number;
  templateVersion: string; taskId: string; codeHash: string;
  code: string; mode: RunMode; cases: NumberCase[];
};
type CaseResult = {
  caseId: string; status: CaseStatus;
  actual?: number[]; expected: number[]; inputAfter?: number[];
  returnedSameReference?: boolean;
  error?: { code: string; message: string };
};
type RunReport = {
  runId: string; exerciseId: string; artifactVersion: number;
  templateVersion: string; taskId: string; codeHash: string;
  mode: RunMode; status: RunStatus;
  results: CaseResult[]; durationMs: number;
};
type ExecutionHandle = {
  result: Promise<RunReport>;
  stop: () => void;
};
```

公共业务类型 `ExerciseArtifact`、`Workspace`、候选字段采用设计第 4 节；字段命名以 camelCase 对外，SQL 列使用 snake_case。

## Task 1: 验证真实 Sandpack 与 Worker 运行通路

**Files:**
- Modify: `frontend/package.json`、`frontend/pnpm-lock.yaml`
- Create: `frontend/src/pbl/fixtures/quicksort.ts`
- Create: `frontend/src/pbl/probe/SandpackProbe.tsx`
- Create: `frontend/pbl-probe.html`
- Create: `frontend/src/pbl/runtime/{index,runner,worker-source}.js`
- Create: `frontend/src/pbl/runtime/{styles.css,template.ts}`
- Create: `frontend/tests/live-learning/pbl-runtime.spec.ts`
- Create: `frontend/playwright.pbl.config.ts`
- Modify when required by the compatibility result: `frontend/vite.config.ts`（现有 `optimizeDeps.noDiscovery=true`，必要时明确加入 Sandpack 预构建入口）

**Interfaces:**
- Consumes: 设计第 6～7 节的固定文件与消息协议。
- Produces: `createExecution(request: RunRequest): ExecutionHandle`；预览握手返回经验证的 MessagePort；可复现的 bundler/Worker 运行证据。

- [x] 锁定 Sandpack 版本。执行 `pnpm add --save-exact @codesandbox/sandpack-react@2.20.0`，核对 lockfile 和 React peer dependency；不升级项目其他包。
- [x] 创建原型 fixture：直接使用设计第 4.2 节中的骨架、参考实现和七类完整用例，同时补 `[10, 2, 1]` 和 `[1.5, -0.5, 0]`。
- [x] 创建仅供本地验收的 `frontend/pbl-probe.html`，以 module script 加载 `src/pbl/probe/SandpackProbe.tsx`；不把它加入正式构建入口，不把未经验证组件接入正式首页。
- [x] 先写真实浏览器验收：

```ts
import { test, expect } from "@playwright/test";

test("循环可停止，停止后正确实现能再次运行", async ({ page }) => {
  await page.goto("/pbl-probe.html");
  await expect(page.getByTestId("runtime-ready")).toHaveText("ready");
  await page.getByRole("button", { name: "加载死循环样例" }).click();
  await page.getByRole("button", { name: "运行样例" }).click();
  await page.getByRole("button", { name: "停止" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("canceled");
  await page.getByRole("button", { name: "加载正确样例" }).click();
  await page.getByRole("button", { name: "检查练习" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("passed");
});
```

- [x] 原型用 `SandpackPreview` ref 的 client 定位 iframe。核对真正的执行窗口，不把“页面 DOM 已出现”当成 runtime 就绪。
- [x] 固定预览壳通过专用 MessageChannel 收到源码快照，在 Worker 里导入源码 Blob module。先验证普通运行，再验证函数内无限循环、递归溢出、停止、Blob URL 清理。
- [x] 验证原型页面在实际部署网络中加载官方 bundler；记录 origin、CSP、错误和加载过程，不保存凭据。未通过时先修运行协议，不实施后续依赖任务。
- [x] 运行 `pnpm exec playwright test -c playwright.pbl.config.ts pbl-runtime.spec.ts`。配置默认启动 `pnpm exec vite --host 127.0.0.1 --port 5207 --strictPort`，与既有 practice 5206 隔离；显式指定 `PBL_FRONTEND_URL` 时使用外部测试服务器。
- [x] 通过后保留原型作回归夹具，不把 probe 的测试按钮放入正式页面。只审阅本任务文件；若执行环境要求提交，精确暂存本任务路径。

## Task 2: 确定候选、产物和运行协议

**Files:**
- Create: `backend/src/app/pbl/{__init__,schemas,contracts}.py`
- Create: `frontend/src/pbl/{types,protocol,runState}.ts`
- Create: `backend/src/tests/pbl/{__init__,test_contracts}.py`
- Create: `frontend/src/pbl/{protocol,runState}.test.ts`
- Create: `frontend/src/pbl/fixtures/code-hash.json`

**Interfaces:**
- Produces Python: `GeneratedExerciseCandidate`、`ExerciseArtifact`、`normalize_candidate(payload: dict) -> GeneratedExerciseCandidate`、`public_artifact(candidate, *, exercise_id, artifact_version, validation_summary) -> ExerciseArtifact`。
- Produces TS: `hashCode(code: string): Promise<string>`、`isCurrentReport(report, artifact, codeHash): boolean`、`deriveTaskStatus({hasEdits, currentCodeHash, artifact, latestCheck}): "not_started" | "in_progress" | "tests_passed" | "needs_recheck"`。

- [x] 将设计中的候选 JSON 做成测试 fixture，固定服务端函数契约、模板版本和单任务要求。禁止候选额外注入 owner/runtime/依赖字段。
- [x] 写必需覆盖和公开对象隔离测试：

```python
def test_public_artifact_never_contains_reference(candidate_payload):
    candidate = normalize_candidate(candidate_payload)
    artifact = public_artifact(
        candidate,
        exercise_id="pbl_test",
        artifact_version=1,
        validation_summary={"passed": True, "templateVersion": "js-function-v1"},
    )
    payload = artifact.model_dump(mode="json")
    assert "referenceSolution" not in payload
    assert len(payload["tasks"]) == 1
    assert payload["tasks"][0]["testCaseIds"]
```

- [x] 对 expected 错误、无限数字、重复 case ID、两个任务、导出名变化、参考代码混入 public 对象编写拒绝断言。七类缺失时程序补齐经过审核的基础用例。
- [x] 定义独立于模型的数值预期生成器；规范化用例后再计算 testCaseIds，不按模型给的完成状态发布。
- [x] 写旧报告不能更新新代码状态的测试：

```ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { deriveTaskStatus } from "./runState";
import { artifact, passedReport } from "./fixtures/quicksort";

test("旧代码的通过结果不属于新代码", () => {
  assert.equal(deriveTaskStatus({
    hasEdits: true, currentCodeHash: "new-hash", artifact,
    latestCheck: { ...passedReport, codeHash: "old-hash" },
  }), "needs_recheck");
});
```

- [x] `isCurrentReport` 同时核对 exercise/artifact/template/task/hash；完整检查必须 case ID 集合相等、无重复、全部 passed 且 report.status=passed。
- [x] 用共享 code-hash fixture 对齐 Python/TS 的 UTF-8 与 JSON 序列化。对 sample/缺 case/重复 case/canceled 写负例。
- [x] 执行 `pytest src/tests/pbl/test_contracts.py -q`（backend 工作目录），以及 `node --import tsx --test src/pbl/protocol.test.ts src/pbl/runState.test.ts`（frontend 工作目录），预期全部通过。

## Task 3: 完成可恢复的算法执行器和生成验证脚本

**Files:**
- Modify: `frontend/src/pbl/runtime/{index,runner,worker-source}.js`
- Create: `frontend/src/pbl/runtime/sourceValidation.ts`
- Create: `frontend/src/pbl/runtime/runner.d.ts`
- Create: `frontend/src/pbl/runtime/runner.test.ts`
- Create: `frontend/scripts/{validate-pbl.mjs,pbl-harness.html}`
- Create: `frontend/scripts/pbl-validation.test.ts`
- Create: `backend/src/app/pbl/validation.py`
- Create: `backend/src/tests/pbl/test_validation.py`
- Modify: `frontend/package.json`、`frontend/pnpm-lock.yaml`（明确声明源码 AST 解析依赖，不依赖偶然存在的传递依赖）

**Interfaces:**
- Produces: `validateSource(code: string): {ok: boolean; issues: {code: string; message: string}[]}`。
- Produces: `createExecution(request: RunRequest): ExecutionHandle`，签名与 Task 1 相同。
- Produces Python: `validate_candidate(candidate: GeneratedExerciseCandidate) -> dict`，报告至少含 `passed`、`issues`、`templateVersion`、`caseResults`。
- Script command: `node --import tsx scripts/validate-pbl.mjs`（frontend 工作目录）。stdin 是含 `candidate` 与 `templateVersion` 的 JSON；stdout 是上述 JSON 报告；退出码 0 表示检查过程执行完毕，内容是否有效由 passed 决定；进程故障非 0。

- [x] 写浏览器 fixture，分别覆盖 NOT_IMPLEMENTED、语法错误、缺导出、返回非数组、修改输入、返回同一数组、丢重复值、无限循环、停止和重复运行。
- [x] AST 校验只接受纯 JS 模块、所需导出和允许的声明；拒绝 imports、顶层运行表达式和异步调用。直接 sort/toSorted 提示实现要求，但不伪装成快速排序证明。`sourceValidation.ts` 仅在宿主和 Node 验证脚本中使用；预览原生 JS 模块不直接 import TypeScript 文件或未打包的 AST 依赖。
- [x] 在 Worker 中保存输入副本、调用函数并检查对象身份；核心逻辑如下，错误映射由外层统一处理：

```js
export function inspectResult(fn, input, expected) {
  const argument = input.slice();
  const before = argument.slice();
  const result = fn(argument);
  const validArray = Array.isArray(result) &&
    Array.from(result).every(value => typeof value === "number" && Number.isFinite(value));
  const unchanged = argument.length === before.length &&
    before.every((value, index) => Object.hasOwn(argument, index) && argument[index] === value);
  const matches = validArray && result.length === expected.length &&
    expected.every((value, index) => result[index] === value);
  return {
    actual: validArray ? result : undefined,
    inputAfter: argument,
    returnedSameReference: result === argument,
    passed: matches && unchanged && result !== argument,
  };
}
```

- [x] 超时计时器放在预览运行器中，从模块加载前开始。每例创建 Worker；结束时清理 Worker、Blob URL 和定时器。`stop()` 幂等，取消后批次不启动新例。
- [x] 在 `runner.d.ts` 声明 `createExecution` 和 `inspectResult`，复用 Task 2 类型，使现有 `allowJs=false` 的 TypeScript 配置可以检查导入调用。非法顶层代码先由静态检查拒绝；绕过静态检查直达 Worker 的专项负例用于验证执行器仍可终止。
- [x] 限制日志与输出序列化大小，捕获 DataCloneError；将不可克隆、过大输出映射为 INVALID_RESULT，不让结果消息把页面拖死。
- [x] 增加 `return new Array(input.length)`、删除输入数组某一索引、返回包含 undefined/NaN 的数组等负例，防止 `Array.every` 跳过空槽而误报通过。
- [x] 运行器只通过协议端口报告；固定壳不 import 学生文件。热更新固定壳时清理旧 session，用户修改代码不触发 run-intent。
- [x] validation 脚本启动隔离浏览器，加载同一套 runtime 源码；参考实现必须通过，骨架返回 NOT_IMPLEMENTED 视为正常。脚本本身的错误与材料错误分别报告，Python 调用超时清理整个浏览器进程组。
- [x] 后端用 subprocess argv 和 JSON stdin 传递候选，不拼 shell。临时上下文不含登录信息，关闭非必需网络请求。
- [x] 执行 frontend 的 `node --import tsx --test scripts/pbl-validation.test.ts src/pbl/runtime/runner.test.ts`、backend 的 `pytest src/tests/pbl/test_validation.py -q`，再运行真实 Sandpack runtime 浏览器测试。

## Task 4: 完成固定练习的学习工作区

**Files:**
- Create: `frontend/src/pbl/{assemble,bridge}.ts`
- Create: `frontend/src/pbl/{PblWorkspace,PblDirectory,PblLesson,SandpackWorkspace}.tsx`
- Create: `frontend/src/pbl/pbl.css`
- Create: `frontend/src/pbl/assemble.test.ts`
- Create: `frontend/tests/live-learning/pbl.spec.ts`

**Interfaces:**
- Consumes: `ExerciseArtifact`、`Workspace`、Task 3 执行协议。
- Produces: `assembleSandpackFiles(artifact, workspace): SandpackFiles`。
- Produces: `<PblWorkspace exerciseId={id} />`；组件外侧通过 repository adapter 提供固定 fixture 或真实 API 数据，不在展示代码写第二份运行规则。
- Produces: bridge `connectRuntime(iframe, allowedOrigin, sessionId)`，返回 `{requestRun, stop, dispose}`，回调输出 `RunReport`。

- [x] 先写装配不覆盖用户代码、参考答案不进入文件的测试：

```ts
test("已有代码优先于模型骨架", () => {
  const files = assembleSandpackFiles(artifact, {
    ...workspace,
    files: { "/src/algorithm.js": "export function quickSort(a) { return [...a]; }" },
  });
  assert.equal(files["/src/algorithm.js"].code,
    "export function quickSort(a) { return [...a]; }");
  assert.equal(Object.keys(files).some(path => /solution/i.test(path)), false);
});
```

- [x] 使用单个 SandpackProvider，默认打开 algorithm.js；原生 editor/preview 保留，外侧只添加目录、任务头和折叠教程/提示。禁止重复实现 CodeMirror 或整套文件树。
- [x] 固定 preview 添加数组输入、运行、检查、停止和结果表；输入保留 raw 文本，按需解析为 finite number array。错误显示具体 case、预期、实际和可理解原因。
- [x] 上层读取代码后生成 runId/hash，把当前版本快照交给 bridge。检查完成前编辑代码，报告显示旧版本且当前需重查。
- [x] 初版隐藏外部发布入口；本地下载当前算法文件。重置先保存可恢复副本，再替换为 artifact 的 starterCode。
- [x] 断开 runtime 时显示重试运行环境入口，保留代码和草稿；不渲染模拟成功输出。
- [x] 浏览器验证 1440、1024、390 像素布局；目录折叠和视图切换不得重建 Provider。确保没有固定右侧聊天栏。
- [x] 运行 `pnpm exec tsc --noEmit`、`pnpm lint`、`pnpm exec playwright test -c playwright.pbl.config.ts pbl.spec.ts`。此时使用明确标记的固定 fixture，不宣称 AI 已生成。

## Task 5: 持久化练习、用户工程和运行记录

**Files:**
- Create: `backend/src/app/pbl/{db_models,repository}.py`
- Create: `backend/src/alembic/versions/20261013_0038_pbl_practice.py`
- Modify: `backend/src/app/database/__init__.py`
- Create: `backend/src/tests/pbl/test_repository.py`
- Create: `backend/src/tests/pbl/test_repository_postgres.py`

**Interfaces:**
- `PblRepository.create_or_get(owner, request_id, topic) -> ExerciseRecord`
- `PblRepository.get_owned(owner, exercise_id) -> ExerciseRecord`
- `PblRepository.get_or_create_workspace(owner, exercise_id) -> Workspace`
- `PblRepository.save_workspace(owner, exercise_id, patch) -> Workspace`
- `PblRepository.append_run(owner, exercise_id, payload) -> RunRecord`
- `PblRepository.claim_generation(owner, exercise_id, job_id, retry_of_job_id) -> bool`
- `PblRepository.save_checkpoint(owner, exercise_id, job_id, payload) -> None`
- `PblRepository.publish(owner, exercise_id, job_id, artifact, private_candidate, validation_report) -> None`

- [x] 实施前重新读取 Alembic head；当前设计编号 0038 不得与并行变更冲突。将 Base 导入与 metadata 注册补齐。
- [x] 建立设计第 9 节三张表及唯一约束，候选/参考和公开产物分列。public API 使用白名单 schema。
- [x] 写多版本和幂等测试。冲突异常使用 `WorkspaceConflict`：

```python
def test_stale_revision_does_not_replace_code(repository, ready_exercise):
    first = repository.get_or_create_workspace("alice", ready_exercise.id)
    saved = repository.save_workspace("alice", ready_exercise.id, {
        "artifactVersion": 1, "expectedRevision": first.revision,
        "mutationId": "mutation-a", "files": {"/src/algorithm.js": "new code"},
        "activeTaskId": "implement-sort", "customInputText": "[3,1,2]",
    })
    with pytest.raises(WorkspaceConflict):
        repository.save_workspace("alice", ready_exercise.id, {
            "artifactVersion": 1, "expectedRevision": first.revision,
            "mutationId": "mutation-b", "files": {"/src/algorithm.js": "old code"},
            "activeTaskId": "implement-sort", "customInputText": "[]",
        })
    assert saved.revision == first.revision + 1
    assert repository.get_or_create_workspace("alice", ready_exercise.id).files[
        "/src/algorithm.js"
    ] == "new code"
```

- [x] 使用条件 UPDATE 实现 CAS，不以读后无条件写代替。最近一次 mutation ID 同内容返回成功；相同 ID 不同内容拒绝，不覆盖。仅存 last_mutation_id 时，更早且已经过期的 mutation 返回 409，不宣称保存了无限历史幂等回执。
- [x] append_run 重算哈希，检查 case 集合、版本、模式、不可变源码快照；重复 runId 同内容幂等，不同内容 409。报告来源固定 browser_reported。
- [x] 生成认领与发布都匹配 current_job_id；旧生成尝试写入失败。已发布 artifact 不在后台重试中重建。
- [x] 单元测试 SQLite；独立 PostgreSQL 两个事务并发写同 revision，必须恰好一个成功。测试库必须明确隔离，不调用生产库清表。
- [x] 执行 `pytest src/tests/pbl/test_repository.py -q`，配置独立 `PBL_TEST_DATABASE_URL` 后执行 PostgreSQL 测试；迁移仅在测试数据库演练 upgrade/downgrade。

## Task 6: API、前端保存恢复和创建任务契约

**Files:**
- Create: `backend/src/app/api/pbl.py`
- Modify: `backend/src/app/bootstrap.py`、`backend/src/app/services/job_store.py`
- Create: `backend/src/tests/pbl/test_api.py`
- Create: `frontend/src/pbl/{api,draftStore,usePblWorkspace,usePblHome}.ts`
- Create: `frontend/src/pbl/draftStore.test.ts`
- Modify: `frontend/src/pbl/PblWorkspace.tsx`
- Modify: `frontend/tests/live-learning/pbl.spec.ts`

**Interfaces:**
- HTTP 路径和请求字段逐项使用设计第 9.2 节，不新增参考答案公开接口。
- Frontend `pblApi` methods: `create`、`list`、`get`、`getWorkspace`、`saveWorkspace`、`appendRun`、`listRuns`，逐一对应 HTTP 路径。
- `usePblWorkspace(exerciseId)` 返回 artifact、workspace、saveStatus、latestCheck、onFilesChange、onInputChange、onRunReport、resetCode。

- [x] 写所有接口的 owner 隔离测试；用 alice 的 ID 由 bob 调用读写，预期 404。未就绪 workspace 为 409，字段错误为 422。
- [x] 创建使用认证 owner 和请求 UUID；同请求同主题返回同 exercise/job，同请求不同主题 409。对练习记录创建后入队失败增加恢复测试，检查 durable task 是否已存在后再补齐。
- [x] 增加 JobKind.GENERATE_PBL；创建响应为 202 和 exerciseId/jobId，结果入队复用 `enqueue_platform_task` 和模型运行配置快照。
- [x] 独立测试公开详情、列表、日志、下载都不包含 referenceSolution；私有校验错误的公开文案不回显整段参考代码。
- [x] 实现 IndexedDB 草稿和 800ms 串行防抖保存。应用关闭不依赖最后一次异步请求成功，本地写入必须先于服务器保存。
- [x] 对保存中继续编辑、响应丢失、断网重连、旧响应迟到、409、多账号草稿隔离分别写状态测试。冲突保留本地内容，不自动以旧服务器结果覆盖。
- [x] 运行记录可独立上传代码快照，不要求编辑器退回运行时版本；runId 重传复用，保存失败只显示待同步，不伪称服务器保存成功。
- [x] 浏览器模拟先保存 A、延迟响应时编辑 B、返回 A 响应；断言编辑器仍为 B，后续按新 revision 保存 B。刷新恢复 B。
- [x] 执行 `pytest src/tests/pbl/test_api.py -q` 和前端保存/恢复浏览器测试，确认旧 `/api/practice` 行为未改变。

## Task 7: 模型生成、校验、修复和 durable 恢复

**Files:**
- Create: `backend/src/app/pbl/{generator,service}.py`
- Modify: `backend/src/app/services/durable_job_runtime.py`
- Modify: `backend/src/app/pbl/repository.py`
- Create: `backend/src/tests/pbl/{test_generation,test_task_recovery}.py`
- Create: `backend/src/tests/pbl/fixtures/candidate.json`

**Interfaces:**
- `async generate_candidate(owner, topic, config_snapshot, prior_candidate=None, issues=None) -> GeneratedExerciseCandidate`
- `async generate_exercise(command, context) -> dict`，command 必含稳定 exercise_id 和 topic。
- `PblTaskHandler.__call__(command, context)` 用 `asyncio.run` 调用流程，注册 `pbl_generate` handler version 1；浏览器验证通过 `asyncio.to_thread(validate_candidate, candidate)` 执行。
- Consumes: Task 2 schema、Task 3 validate_candidate、Task 5 repository、现有模型网关与 durable context。

- [x] 建立快速排序范围检查；不能支持的主题返回 UNSUPPORTED_TOPIC，不自动生成其他算法或整门课。
- [x] 通过既有模型网关提交固定 schema 和 contract。一次生成完整候选，再做程序检查；不要为了命名为 Agent 增加无关角色和多轮聊天。
- [x] 测试生成候选 expected 错误、缺基础用例、starter 已包含答案、reference 错误、JSON 格式错误、模型超时的处理。生成骨架函数体只允许注释和 NOT_IMPLEMENTED 抛错，学生代码不受这一骨架规则约束；不宣称静态检查能证明教学质量。
- [x] 失败报告归类为结构、源码、用例、参考运行或运行环境错误。材料问题最多两次定向修复，环境故障不要求模型改算法来绕过。
- [x] 每阶段保存 checkpoint 和 repair_count；重新领取复用有效候选，验证结果必须匹配模板版本。示例恢复断言：

```python
@pytest.mark.asyncio
async def test_resume_after_validation_does_not_regenerate(
    repository, model_spy, validation_spy, context, command, validated_checkpoint
):
    repository.save_checkpoint(
        context.owner_user_id, command["exercise_id"], context.task_id,
        validated_checkpoint,
    )
    result = await generate_exercise(command, context)
    assert model_spy.call_count == 0
    assert validation_spy.call_count == 0
    assert result["result_ref"]["exercise_id"] == command["exercise_id"]
```

- [x] 测试用户重试产生新 job ID，仍指向相同 exercise_id；claim_generation 原子切换 current_job_id，旧任务迟到发布被拒绝。并发重试只有一个被认领。
- [x] 每个模型/浏览器长操作前后检查取消；发布前验证有效任务归属与租约。先持久化、回读，再交付 saved=true；同一有效 job 重入不重复发布。
- [x] 任务成功返回设计中的 pbl_exercise result_ref；失败保留候选和可读错误，不下发半成品。运行日志只含阶段、模型标识与必要指标，不输出凭据和参考代码。
- [x] 执行 `pytest src/tests/pbl/test_generation.py src/tests/pbl/test_task_recovery.py -q`。随后用真实模型在隔离练习中生成一份材料并运行校验，记录真实失败/通过，不替换为 fixture 冒充模型成果。

## Task 8: 首页入口、任务中心和最近练习

**Files:**
- Modify: `frontend/src/practice/PracticeHome.tsx`
- Modify: `frontend/src/liveLearning/LiveApp.tsx`
- Modify: `frontend/src/jobs/{jobPresentation,jobResultTarget}.ts`
- Modify: `frontend/src/jobs/{jobPresentation,jobResultTarget}.test.ts`
- Modify: `frontend/src/pbl/usePblHome.ts`
- Modify: `frontend/tests/live-learning/pbl.spec.ts`

**Interfaces:**
- `#/practice` 为原模拟实验；`#/practice/code` 为编程练习首页；`#/practice/code/:exerciseId` 为 PBL 工作区。
- job result `resource_type=pbl_exercise` → `#/practice/code/${exercise_id}`。

- [x] 增加“模拟实验 / 编程练习”入口选择，复用首页输入和资源卡片；编程练习首页提示首版 JavaScript 快速排序范围。切换入口不改变已有实验记录。
- [x] 路由先识别 /practice/code，再识别旧 /practice/:id，避免把 code 当实验 ID。
- [x] 提交成功后清理本次请求编号；只有接收结果未知时复用编号。刷新只恢复任务查询，不自动新建或重试。
- [x] 列表显示真实 job 状态；重试新 job ID 与稳定 exercise ID 的关系保持一致。任务中心使用统一取消/重试 API。
- [x] jobResultTarget 在 course/material 必填检查之前处理新资源类型：

```ts
if (result?.resource_type === "pbl_exercise" && result.exercise_id) {
  return "#/practice/code/" + encodeURIComponent(String(result.exercise_id));
}
```

- [x] 编写“无 courseId 的 PBL 任务也能打开”“旧课堂跳转不变”“旧 practice 路由不变”的回归。
- [x] 执行 `node --import tsx --test src/jobs/jobPresentation.test.ts src/jobs/jobResultTarget.test.ts`，运行首页创建、离开、返回与结果打开的浏览器流程。

## Task 9: 完整验收、文档和部署交接

**Files:**
- Modify: `frontend/tests/live-learning/{pbl,pbl-runtime}.spec.ts`
- Modify: `docs/architecture/2026-10-13-sandpack-algorithm-practice-design-cn.md`
- Modify: `docs/README.md`、`项目总览地图.md`、`DEPENDENCIES.md`
- Create: `docs/acceptance/2026-10-13-sandpack-algorithm-practice/README.md`
- Create: `docs/acceptance/2026-10-13-sandpack-algorithm-practice/verification.json`

**Interfaces:**
- Consumes: 全部前述接口和设计第 12 节验收标准。
- Produces: 可追溯的自动化结果、真实模型和浏览器运行证据、部署前置条件及尚未验证项。

- [x] 在隔离测试环境执行全部 PBL 后端测试、类型检查、lint、build、PBL 浏览器流程，以及旧 practice 必要回归。记录命令、退出码、实际测试数量；不要在计划阶段伪写通过。
- [x] 真实链路：输入快速排序 → 等待生成 → 查看模型材料 → 输入故意丢重复值实现 → 检查显示失败 → 修正算法 → 全部通过 → 编辑使报告过期 → 刷新恢复 → 再检查通过。
- [x] 验证 runtime 不可达、断网保存、取消生成、失败重试、循环停止、账号切换、多标签冲突和私有答案隔离。
- [x] 检查 1440/1024/390 宽度与键盘可操作性，保存页面截图。确认教程/目录没有盖住编辑器，移动端切换保留代码。
- [x] 实际模型检查与固定 fixture 测试分别记录；本地运行器通过与托管 Sandpack 真实运行通过分别记录。
- [x] 核对所有测试结果后更新设计状态、依赖、文档入口和项目地图，区分源码完成、迁移完成和部署完成。
- [x] 部署交接列出数据库迁移 head、Sandpack 资源域名、前后端版本、浏览器检查依赖和回滚方式。除非用户届时已授权，不把部署当作文档或本地实现已自动完成。

建议验证命令（按阶段运行，已有通过结果不无故反复全量重跑）：

```bash
# backend 工作目录，明确使用隔离测试配置
pytest src/tests/pbl src/tests/practice/test_practice.py -q

# frontend 工作目录
pnpm exec tsc --noEmit
pnpm lint
pnpm build
node --import tsx --test "src/pbl/**/*.test.ts" "src/pbl/*.test.ts" scripts/pbl-validation.test.ts
pnpm exec playwright test -c playwright.pbl.config.ts
pnpm exec playwright test -c playwright.practice.config.ts
```

原有 practice 配置依赖 `dist-practice`，其回归构建使用 `pnpm exec vite build --outDir dist-practice`。PBL 全套测试默认启动 5207 的 Vite dev server，包含不进入生产包的 probe。另做正式构建复验：`pnpm exec vite build --outDir dist-pbl`，启动 5208 的 Vite preview，指定 `PBL_FRONTEND_URL=http://127.0.0.1:5208` 仅运行 `pbl.spec.ts` 的正式业务场景，不请求开发 probe。测试库变量由测试 fixture 明确注入，不从生产 DATABASE_URL 默认继承执行清理操作。

## 计划自检与需求覆盖

| 设计要求 | 任务 |
| --- | --- |
| 单算法、单任务、结构化材料 | 2、7 |
| 原生 Sandpack 主体加左目录 | 1、4 |
| 显式执行、超时和停止 | 1、3 |
| 输入输出、原数组和新数组检查 | 2、3 |
| 模型候选、私有参考与公开工程分离 | 2、5、7 |
| 生成恢复、取消、重试和版本保护 | 5、6、7 |
| 保存、刷新、多标签冲突、账号隔离 | 5、6 |
| 当前代码与检查报告对应 | 2、4、6 |
| 首页、最近练习和任务结果跳转 | 8 |
| 真实端到端和原功能回归 | 9 |

后续复杂项目通过扩展任务内容和新增 web_project 运行/检查模式实现，不在本计划实现计算器阶段、DOM 自动验收或 Agent 辅导。
