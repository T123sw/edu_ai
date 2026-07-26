# AI 课堂场景适配与视频超时 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复长旁白 MP4 导出超时，并让 Edu AI 课堂原生播放 slide、interactive 和 quiz 三类普通课堂场景。

**Architecture:** 视频管线把页面连接超时与单场景播放超时拆开。课堂播放器新增判别式场景分发器；interactive 通过无同源权限的沙箱 iframe 播放，并由动作引擎定向发送 widget 消息；quiz 使用本地纯函数评分和浏览器缓存，简答题进入自评状态。

**Tech Stack:** TypeScript、React 18、Vite、Node test runner、Playwright、FFmpeg、`@openmaic/dsl`、`@openmaic/renderer`

---

**执行状态（2026-07-26）：** Task 1–8 已完成并按小阶段提交；Task 9 的真实 MP4、interactive、quiz 与恢复验收已完成。剩余工作仅为最终新鲜验证和快进合并到 `main`。

## 文件结构

- `Edu_AI/scripts/videoPipeline.ts`
  - 新增独立的 `sceneTimeoutMs`，页面连接继续使用 `timeoutMs`。
- `Edu_AI/scripts/videoPipeline.test.ts`
  - 覆盖默认值、覆盖参数和非法参数。
- `Edu_AI/src/stitch/api/types.ts`
  - 定义 slide、interactive、quiz 的课堂内容和题目契约。
- `Edu_AI/src/openmaic/classroomScene.ts`
  - 纯函数校验并解析场景类型。
- `Edu_AI/src/openmaic/classroomScene.test.ts`
  - 覆盖三类分发、类型错配和未知类型。
- `Edu_AI/src/openmaic/interactiveScene.ts`
  - HTML 安全修补、widget 动作到 postMessage 的映射。
- `Edu_AI/src/openmaic/interactiveScene.test.ts`
  - 覆盖修补注入、消息映射和非法动作。
- `Edu_AI/src/openmaic/actionEngine.ts`
  - 增加可注入的 widget controller。
- `Edu_AI/src/openmaic/actionEngine.test.ts`
  - 验证四类 widget 动作发往当前控制器。
- `Edu_AI/src/openmaic/SceneActionPlayback.tsx`
  - 为非 slide 内容复用现有顺序播放引擎和旁白兜底。
- `Edu_AI/src/openmaic/InteractiveScenePlayer.tsx`
  - 沙箱 iframe、运行时错误提示和重新加载。
- `Edu_AI/src/openmaic/quizScene.ts`
  - 客观题评分、简答自评、缓存序列化和容错。
- `Edu_AI/src/openmaic/quizScene.test.ts`
  - 覆盖评分、分值、未知题型和损坏缓存。
- `Edu_AI/src/openmaic/QuizScenePlayer.tsx`
  - 答题、提交、解析、重做和本地恢复界面。
- `Edu_AI/src/openmaic/ClassroomSceneRenderer.tsx`
  - 统一派发三个播放器。
- `Edu_AI/src/stitch/pages/ClassroomPlayer.tsx`
  - 使用统一派发器，保留导航、PPTX 和 MP4 按钮。
- `Edu_AI/tests/frontend/classroomSceneAdapters.source.test.ts`
  - 静态集成守卫，确保课堂页面不再内联 slide-only 分支。

### Task 1: 建立隔离工作区测试基线

- [ ] **Step 1: 复用主工作区依赖**

确认 `D:\github\edu_ai\Edu_AI\node_modules` 存在后，在当前 worktree 的 `Edu_AI\node_modules` 创建目录联接。该目录被 Git 忽略，不进入提交。

- [ ] **Step 2: 运行视频与播放器基线测试**

Run:

```powershell
node --import tsx --test scripts/videoPipeline.test.ts src/openmaic/actionEngine.test.ts src/openmaic/videoRenderState.test.ts
```

Expected: 现有测试全部通过。

- [ ] **Step 3: 检查 worktree 只包含已提交文档**

Run:

```powershell
git status --short
```

Expected: 无未提交文件。

### Task 2: 分离 MP4 页面连接与场景播放超时

**Files:**

- Modify: `Edu_AI/scripts/videoPipeline.test.ts`
- Modify: `Edu_AI/scripts/videoPipeline.ts`

- [ ] **Step 1: 写默认值和覆盖参数的失败测试**

在参数解析测试的期望对象中增加：

```ts
sceneTimeoutMs: 600000,
```

并增加：

```ts
test('parseVideoExportArguments separates navigation and scene timeouts', () => {
  const options = parseVideoExportArguments([
    '--output-dir',
    'out',
    '--fixture',
    '--timeout-ms',
    '45000',
    '--scene-timeout-ms',
    '720000',
  ]);
  assert.equal(options.timeoutMs, 45000);
  assert.equal(options.sceneTimeoutMs, 720000);

  assert.throws(
    () =>
      parseVideoExportArguments([
        '--output-dir',
        'out',
        '--fixture',
        '--scene-timeout-ms',
        '0',
      ]),
    /--scene-timeout-ms must be a positive integer/,
  );
});
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
node --import tsx --test scripts/videoPipeline.test.ts
```

Expected: 失败原因是缺少 `sceneTimeoutMs`，不是导入或语法错误。

- [ ] **Step 3: 实现最小超时拆分**

在 `VideoExportOptions` 中加入：

```ts
sceneTimeoutMs: number;
```

在参数解析中加入：

```ts
const sceneTimeoutValue = optionValue(args, '--scene-timeout-ms');
const sceneTimeoutMs = sceneTimeoutValue
  ? Number.parseInt(sceneTimeoutValue, 10)
  : 600000;
if (!Number.isInteger(sceneTimeoutMs) || sceneTimeoutMs <= 0) {
  throw new Error('--scene-timeout-ms must be a positive integer');
}
```

返回对象包含 `sceneTimeoutMs`，并把场景完成等待改为：

```ts
{ timeout: options.sceneTimeoutMs }
```

`page.goto()` 和根节点 `waitFor()` 继续使用 `options.timeoutMs`。

- [ ] **Step 4: 运行聚焦测试并确认 GREEN**

Run:

```powershell
node --import tsx --test scripts/videoPipeline.test.ts
```

Expected: 全部通过。

- [ ] **Step 5: 运行完整前端测试和构建**

Run:

```powershell
npm test
npm run build
```

Expected: 测试与构建退出码均为 0。

- [ ] **Step 6: 提交**

```powershell
git add -- Edu_AI/scripts/videoPipeline.ts Edu_AI/scripts/videoPipeline.test.ts
git commit -m "fix(video): allow long classroom scenes"
```

### Task 3: 用真实课件验证 MP4 导出

**Files:**

- Verify only: `Edu_AI/api/course_data/courses/computational-thinking/generated_materials/classrooms/Ii0-7a0bpN_media/video/`

- [ ] **Step 1: 使用本地教师认证创建验证任务**

通过现有 FastAPI 配置和任务服务创建 `render_video` 任务，调用：

```py
run_classroom_video_export_job(
    course_id="computational-thinking",
    classroom_id="Ii0-7a0bpN",
    edu_job_id=job_id,
)
```

以隐藏后台进程运行，日志写入系统临时目录，不写入仓库。

- [ ] **Step 2: 轮询任务直到终态**

每次读取 `Edu_AI/api/src/storage/jobs/<job_id>.json`，记录 `status`、`step`、`progress` 和 `message`。轮询间隔不超过 60 秒。

Expected: 任务越过此前第五个可录制场景并最终 `succeeded`。

- [ ] **Step 3: 验证产物**

Run:

```powershell
ffprobe -v error -show_entries format=duration -show_streams -of json classroom.mp4
```

Expected:

- `classroom.mp4`、`classroom.srt`、`timeline.json` 均非空。
- MP4 至少包含一个视频流和一个音频流。
- 时长为正数。

若真实导出失败，保留任务 JSON 和日志证据，回到根因调查，不进入场景适配实现。

### Task 4: 收紧课堂场景契约并建立统一分发

**Files:**

- Modify: `Edu_AI/src/stitch/api/types.ts`
- Create: `Edu_AI/src/openmaic/classroomScene.ts`
- Create: `Edu_AI/src/openmaic/classroomScene.test.ts`

- [ ] **Step 1: 写场景解析失败测试**

测试期望：

```ts
assert.equal(resolveClassroomSceneKind(slideScene), 'slide');
assert.equal(resolveClassroomSceneKind(interactiveScene), 'interactive');
assert.equal(resolveClassroomSceneKind(quizScene), 'quiz');
assert.equal(resolveClassroomSceneKind(mismatchedScene), 'invalid');
assert.equal(resolveClassroomSceneKind(pblScene), 'unsupported');
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
node --import tsx --test src/openmaic/classroomScene.test.ts
```

Expected: 模块不存在而失败。

- [ ] **Step 3: 定义判别式契约**

在 `types.ts` 定义：

```ts
export type ClassroomQuizQuestion = {
  id: string;
  type: "single" | "multiple" | "short_answer" | string;
  question: string;
  options?: Array<{ value: string; label: string }>;
  answer?: string[];
  analysis?: string;
  commentPrompt?: string;
  points?: number;
  hasAnswer?: boolean;
};

export type SlideClassroomContent = {
  type: "slide";
  canvas: Record<string, unknown>;
};

export type InteractiveClassroomContent = {
  type: "interactive";
  url?: string;
  html?: string;
  widgetType?: string;
  widgetConfig?: Record<string, unknown>;
};

export type QuizClassroomContent = {
  type: "quiz";
  questions: ClassroomQuizQuestion[];
};
```

`ClassroomScene.content` 使用这些内容或宽泛未知内容的联合，保持后端原样透传兼容。

- [ ] **Step 4: 实现场景解析**

`resolveClassroomSceneKind()` 同时校验 `scene.type` 和 `scene.content?.type`：

```ts
export type ClassroomSceneKind =
  | 'slide'
  | 'interactive'
  | 'quiz'
  | 'invalid'
  | 'unsupported';
```

- [ ] **Step 5: 运行测试并确认 GREEN**

Run:

```powershell
node --import tsx --test src/openmaic/classroomScene.test.ts
```

Expected: 全部通过。

- [ ] **Step 6: 提交**

```powershell
git add -- Edu_AI/src/stitch/api/types.ts Edu_AI/src/openmaic/classroomScene.ts Edu_AI/src/openmaic/classroomScene.test.ts
git commit -m "feat(classroom): add typed scene dispatch"
```

### Task 5: 为互动场景增加安全 HTML 与 widget 动作

**Files:**

- Create: `Edu_AI/src/openmaic/interactiveScene.ts`
- Create: `Edu_AI/src/openmaic/interactiveScene.test.ts`
- Modify: `Edu_AI/src/openmaic/actionEngine.ts`
- Modify: `Edu_AI/src/openmaic/actionEngine.test.ts`

- [ ] **Step 1: 写 HTML 修补和消息映射失败测试**

覆盖：

```ts
const patched = patchInteractiveHtml('<html><head></head><body>demo</body></html>');
assert.match(patched, /data-edu-storage-shim/);
assert.match(patched, /data-edu-runtime-error-shim/);
assert.match(patched, /data-edu-iframe-style/);

assert.deepEqual(widgetMessageForAction({
  id: 'set',
  type: 'widget_setState',
  state: { pivot: 6 },
}), {
  type: 'SET_WIDGET_STATE',
  payload: { state: { pivot: 6 }, content: undefined },
});
```

并覆盖 highlight、annotation、reveal 及 speech 返回 `null`。

- [ ] **Step 2: 写动作引擎 widget controller 失败测试**

使用记录调用的 fake controller，依次执行四种 widget action，断言发送类型和 payload 与 OpenMAIC 协议一致。

- [ ] **Step 3: 运行测试并确认 RED**

Run:

```powershell
node --import tsx --test src/openmaic/interactiveScene.test.ts src/openmaic/actionEngine.test.ts
```

Expected: 缺少模块和 widget controller 行为而失败。

- [ ] **Step 4: 实现安全修补和消息映射**

`patchInteractiveHtml()` 注入：

- 100% 宽高和纵向滚动样式。
- 无同源沙箱下的内存 `localStorage/sessionStorage` shim。
- `error`、`unhandledrejection` 和 `console.error` 的受限诊断 postMessage。

`widgetMessageForAction()` 只映射四种已知 widget action。

- [ ] **Step 5: 扩展动作引擎**

新增：

```ts
export interface ActionWidgetController {
  postMessage(type: string, payload: Record<string, unknown>): void;
}
```

`ActionEngineOptions` 增加 `widget`。四种 widget action 调用 `widgetMessageForAction()`，发送后等待 300ms；没有 controller 时安全返回。

- [ ] **Step 6: 运行测试并确认 GREEN**

Run:

```powershell
node --import tsx --test src/openmaic/interactiveScene.test.ts src/openmaic/actionEngine.test.ts
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```powershell
git add -- Edu_AI/src/openmaic/interactiveScene.ts Edu_AI/src/openmaic/interactiveScene.test.ts Edu_AI/src/openmaic/actionEngine.ts Edu_AI/src/openmaic/actionEngine.test.ts
git commit -m "feat(classroom): support interactive widget actions"
```

### Task 6: 接入互动场景播放器

**Files:**

- Create: `Edu_AI/src/openmaic/SceneActionPlayback.tsx`
- Create: `Edu_AI/src/openmaic/InteractiveScenePlayer.tsx`
- Create: `Edu_AI/src/openmaic/ClassroomSceneRenderer.tsx`
- Modify: `Edu_AI/src/stitch/pages/ClassroomPlayer.tsx`
- Create: `Edu_AI/tests/frontend/classroomSceneAdapters.source.test.ts`

- [ ] **Step 1: 写集成守卫失败测试**

断言：

- `ClassroomPlayer.tsx` 导入并使用 `ClassroomSceneRenderer`。
- 页面不再包含 `P3-1 只接了 slide`。
- `InteractiveScenePlayer.tsx` 包含 iframe `sandbox`，且不包含 `allow-same-origin`。
- `ClassroomSceneRenderer.tsx` 包含 interactive 派发。

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
node --import tsx --test tests/frontend/classroomSceneAdapters.source.test.ts
```

Expected: 新文件不存在或课堂页面仍是 slide-only 而失败。

- [ ] **Step 3: 实现非 slide 动作播放壳**

`SceneActionPlayback` 创建一个单场景 `PlaybackEngine` 和注入 widget controller 的 `ActionEngine`。自动开始、卸载时 dispose，完成后只把状态改为 idle，不触发课堂跳转。

- [ ] **Step 4: 实现互动播放器**

`InteractiveScenePlayer`：

- `html` 优先，使用 `patchInteractiveHtml()` 后传给 `srcDoc`。
- 没有 HTML 时使用 `url`。
- sandbox 允许 `allow-scripts allow-forms allow-modals allow-popups allow-downloads`。
- controller 只对 `iframeRef.current.contentWindow` 调用 `postMessage()`。
- 监听来自当前 iframe 的诊断消息，显示错误和“重新加载”按钮。
- 空内容显示可读错误。

- [ ] **Step 5: 实现场景分发器并替换页面内联分支**

`ClassroomSceneRenderer` 接收 `scene`、`courseId`、`classroomId` 和 slide 完成回调。slide 保持原 `SlidePlayer` 逻辑；interactive 使用新播放器；quiz 暂显示下一任务将替换的明确占位；invalid/unsupported 显示对应错误。

- [ ] **Step 6: 运行测试、lint 和构建**

Run:

```powershell
node --import tsx --test tests/frontend/classroomSceneAdapters.source.test.ts src/openmaic/interactiveScene.test.ts src/openmaic/actionEngine.test.ts
npm run lint
npm run build
```

Expected: 测试通过；lint 无 error；构建退出码 0。

- [ ] **Step 7: 提交**

```powershell
git add -- Edu_AI/src/openmaic/SceneActionPlayback.tsx Edu_AI/src/openmaic/InteractiveScenePlayer.tsx Edu_AI/src/openmaic/ClassroomSceneRenderer.tsx Edu_AI/src/stitch/pages/ClassroomPlayer.tsx Edu_AI/tests/frontend/classroomSceneAdapters.source.test.ts
git commit -m "feat(classroom): render interactive scenes"
```

### Task 7: 实现测验评分与恢复

**Files:**

- Create: `Edu_AI/src/openmaic/quizScene.ts`
- Create: `Edu_AI/src/openmaic/quizScene.test.ts`

- [ ] **Step 1: 写评分失败测试**

用单选、多选、简答和未知题型 fixture 验证：

```ts
assert.deepEqual(gradeQuizQuestions(questions, answers).results.map((item) => item.status), [
  'correct',
  'incorrect',
  'self_review',
  'unsupported',
]);
```

验证多选答案顺序不影响判分、客观题得分只统计 single/multiple、简答题不进入自动正确率。

- [ ] **Step 2: 写缓存失败测试**

验证：

- 缓存键包含 courseId、classroomId、sceneId。
- 合法 JSON 恢复答案和提交状态。
- 损坏 JSON 返回空状态并删除损坏值。

- [ ] **Step 3: 运行测试并确认 RED**

Run:

```powershell
node --import tsx --test src/openmaic/quizScene.test.ts
```

Expected: 模块不存在而失败。

- [ ] **Step 4: 实现纯函数**

实现：

```ts
quizStorageKey(courseId, classroomId, sceneId)
gradeQuizQuestions(questions, answers)
readQuizState(storage, key)
writeQuizState(storage, key, state)
clearQuizState(storage, key)
```

选择答案先去重排序后比较；未知题型不阻断其他题目。

- [ ] **Step 5: 运行测试并确认 GREEN**

Run:

```powershell
node --import tsx --test src/openmaic/quizScene.test.ts
```

Expected: 全部通过。

- [ ] **Step 6: 提交**

```powershell
git add -- Edu_AI/src/openmaic/quizScene.ts Edu_AI/src/openmaic/quizScene.test.ts
git commit -m "feat(classroom): add quiz grading and recovery"
```

### Task 8: 接入测验播放器

**Files:**

- Create: `Edu_AI/src/openmaic/QuizScenePlayer.tsx`
- Modify: `Edu_AI/src/openmaic/ClassroomSceneRenderer.tsx`
- Modify: `Edu_AI/tests/frontend/classroomSceneAdapters.source.test.ts`

- [ ] **Step 1: 扩展集成守卫并确认 RED**

断言分发器导入并渲染 `QuizScenePlayer`，组件源代码包含单选、多选、简答、提交和重做入口。

Run:

```powershell
node --import tsx --test tests/frontend/classroomSceneAdapters.source.test.ts
```

Expected: quiz 仍是占位而失败。

- [ ] **Step 2: 实现测验界面**

`QuizScenePlayer`：

- 初始化时从本地存储恢复。
- single 使用单选按钮，multiple 使用复选按钮，short_answer 使用 textarea。
- 每次修改写草稿。
- 提交后调用 `gradeQuizQuestions()`，显示客观题得分、正确选项、解析和简答自评。
- “重新作答”清除缓存。
- 外层使用 `SceneActionPlayback` 播放旁白，但不自动切换场景。

- [ ] **Step 3: 替换 quiz 占位**

`ClassroomSceneRenderer` 对合法 quiz 内容渲染 `QuizScenePlayer` 并传入课程、课堂和场景标识。

- [ ] **Step 4: 运行聚焦测试和完整验证**

Run:

```powershell
node --import tsx --test src/openmaic/quizScene.test.ts tests/frontend/classroomSceneAdapters.source.test.ts
npm test
npm run lint
npm run build
```

Expected: 所有测试通过；lint 无 error；构建退出码 0。

- [ ] **Step 5: 提交**

```powershell
git add -- Edu_AI/src/openmaic/QuizScenePlayer.tsx Edu_AI/src/openmaic/ClassroomSceneRenderer.tsx Edu_AI/tests/frontend/classroomSceneAdapters.source.test.ts
git commit -m "feat(classroom): render quiz scenes"
```

### Task 9: 真实浏览器验收与集成

**Files:**

- Modify: `docs/superpowers/specs/2026-07-26-classroom-scene-adapter-design.md`
- Modify: `docs/superpowers/specs/2026-07-26-classroom-video-scene-timeout-design.md`

- [ ] **Step 1: 打开真实课堂播放器**

访问：

```text
http://127.0.0.1:5173/#classroom-player?course_id=computational-thinking&classroom_id=Ii0-7a0bpN
```

使用已有教师登录状态。

- [ ] **Step 2: 验收 interactive**

导航到第 5 个场景，验证：

- 快速排序分区模拟可见。
- 预设、滑块或页面交互可操作。
- widget 状态和高亮动作能够送达。
- 没有未捕获页面异常。

- [ ] **Step 3: 验收 quiz**

导航到第 9 个场景，完成单选、多选和简答并提交。验证得分、解析、自评、重做和刷新恢复。

- [ ] **Step 4: 回归 slide 和导航**

验证 slide 旁白/聚焦、上一个/下一个、返回课件列表、PPTX 与 MP4 按钮仍存在。

- [ ] **Step 5: 更新规格验收状态并提交**

在两份设计规格追加真实任务 ID、MP4 媒体探测结果和浏览器验收结果。

```powershell
git add -- docs/superpowers/specs/2026-07-26-classroom-scene-adapter-design.md docs/superpowers/specs/2026-07-26-classroom-video-scene-timeout-design.md
git commit -m "docs(classroom): record scene adapter acceptance"
```

- [ ] **Step 6: 最终新鲜验证**

Run:

```powershell
npm test
npm run lint
npm run build
python -m pytest tests/test_classroom_video_export.py tests/chat/test_start_api_bat.py -q
git diff --check
git status --short --branch
```

Expected:

- 测试与构建退出码为 0。
- lint 为 0 error。
- `git diff --check` 无输出。
- 功能分支工作区干净。

- [ ] **Step 7: 快进合并到 main**

在主工作区确认只有用户原有的 `Edu_AI/package.json` 修改，然后执行快进合并。合并后重复关键测试，不暂存或修改该用户文件。
