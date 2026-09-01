# AI 课堂本地场景适配层设计

## 背景

当前 Edu AI 课堂播放器只派发 `slide` 场景。真实课堂 `Ii0-7a0bpN` 包含：

- 8 个 `slide`
- 1 个 `interactive`
- 1 个 `quiz`

因此第 5 个互动场景和第 9 个测验场景只能显示“不支持播放”的占位。OpenMAIC 的播放分发器支持 `slide / interactive / quiz / pbl`，但其中 PBL 依赖独立的项目配置、会话接口和状态机，不属于普通 AI 课堂的本轮同步范围。

## 目标与范围

本次让普通 AI 课堂完整播放生成链路实际产生的三类场景：

```text
slide + interactive + quiz
```

PBL 保留明确的未支持提示，不复制一个缺少后端状态机的假播放器。MP4 仍只录制确定性的 `slide` 场景。

## 方案比较

### 方案 A：Edu 本地场景适配层（采用）

在 Edu 前端新增小型分发器和两种本地播放器，继续复用现有 `@openmaic/dsl`、`@openmaic/renderer`、播放引擎和动作引擎。

优点是与现有 Vite/React 18 架构一致，不依赖第二个前端页面，也能针对 Edu 的鉴权和课程存储直接测试。

### 方案 B：直接导入 OpenMAIC 页面组件

OpenMAIC 场景组件依赖 Next.js、React 19、路径别名、Zustand 场景状态、IndexedDB、国际化、模型配置及多组接口。直接导入会把大部分 OpenMAIC 应用层一并带入 Edu，版本和运行时边界不稳定。

### 方案 C：iframe 嵌入完整 OpenMAIC 播放页

可以减少场景组件迁移，但需要新增课件数据桥、跨窗口状态协议、鉴权传递和播放生命周期同步，并让 Edu 课堂播放永久依赖 OpenMAIC 前端服务在线。

## 组件边界

### `ClassroomSceneRenderer`

统一接收 `ClassroomScene`，只负责按内容判别式分发：

- `slide` → 现有 `SlidePlayer`
- `interactive` → `InteractiveScenePlayer`
- `quiz` → `QuizScenePlayer`
- 其他类型 → 带场景类型和原因的明确错误卡片

分发判断以 `scene.type` 与 `scene.content.type` 同时匹配为准。两者不一致时显示数据错误，不猜测或强制转换内容。

### `SceneActionPlayback`

把与画面类型无关的旁白和动作播放从 `SlidePlayer` 中抽成可复用边界：

- `speech` 继续使用已鉴权转换后的音频 Blob URL，失败时沿用浏览器语音和阅读时长兜底。
- `widget_setState`、`widget_highlight`、`widget_annotation`、`widget_reveal` 通过一个小型 widget adapter 定向发送到当前互动 iframe。
- slide 的 spotlight、laser 和 video 行为保持现状。

互动和测验场景播放完旁白后停留在当前场景，等待用户操作或点击“下一个”；不调用课堂自动跳转。

### `InteractiveScenePlayer`

- `content.html` 非空时优先使用 `srcDoc`。
- 没有内嵌 HTML 时才使用 `content.url`。
- iframe 使用 `sandbox`，允许脚本和表单等互动能力，但不添加 `allow-same-origin`，避免 LLM 生成页面逃逸沙箱。
- 注入与 OpenMAIC 同等目的的尺寸修正、内存 storage shim 和运行时错误捕获。
- widget adapter 只向当前 iframe 的 `contentWindow` 发送已知消息类型，不广播给其他窗口。
- iframe 加载错误或运行时错误在播放器上显示可读提示，同时保留重新加载按钮。

切换离开互动场景时允许卸载 iframe；本轮不实现 OpenMAIC 的跨场景 keep-alive 池。当前生成课堂每个互动场景是自包含练习，重新进入时从初始状态开始。

### `QuizScenePlayer`

支持 OpenMAIC 普通课堂题型：

- `single`
- `multiple`
- `short_answer`

单选和多选依据 `answer[]` 在浏览器本地评分，展示得分、正确选项和 `analysis`。简答题不调用新的 AI 接口；提交后展示学生答案、参考分析和“待自评”状态，不把简答题计入自动正确率。

草稿与已提交状态写入浏览器本地存储，键包含：

```text
courseId + classroomId + sceneId
```

这样刷新页面或切换场景后可恢复，同一课堂和不同课堂之间不会串答案。用户可以清除本场答案并重新作答。

## 数据契约

前端把宽泛的 `ClassroomScene.content` 收紧为判别联合：

- `SlideClassroomContent`
- `InteractiveClassroomContent`
- `QuizClassroomContent`
- `UnknownClassroomContent`

题目选项、答案、解析、分值以及互动页的 `html/url/widgetType/widgetConfig` 均从后端原样读取，不修改持久化格式，也不要求后端迁移既有课堂文件。

## 错误与安全

- content 缺失或类型不一致时显示数据错误，不让整个课堂页面崩溃。
- 互动页同时缺少 `html` 和 `url` 时显示“互动内容为空”。
- 外部 URL 和内嵌 HTML 均处于无同源权限的沙箱内。
- 运行时消息只接受当前 iframe 发出的诊断消息，并限制错误文本长度。
- 本地存储损坏时丢弃该场景缓存，从空白答题状态开始。
- 未知题型显示“暂不支持此题型”，其余题目仍可作答。

## 验证

自动化测试覆盖：

- 三类场景的分发以及类型不一致的错误分支。
- interactive HTML 修补、沙箱属性和四类 widget 消息映射。
- quiz 单选、多选评分、简答待自评、总分计算和缓存解析容错。
- 现有 slide 播放、动作引擎、视频选择、PPTX 导出测试不回归。
- 完整前端测试、lint 和生产构建。

真实浏览器验收使用课堂 `Ii0-7a0bpN`：

1. 第 1–4 个 slide 保持原有画面和旁白。
2. 第 5 个 interactive 显示快速排序分区模拟，可操作，并能响应状态和高亮动作。
3. 第 9 个 quiz 可完成单选、多选和简答，提交后显示客观题结果与解析。
4. 前后切换、刷新恢复和返回课件列表正常。
5. 控制台无未捕获异常。

## 提交阶段

1. MP4 长场景超时修复。
2. 场景数据契约与统一分发器。
3. interactive 渲染与 widget 动作。
4. quiz 渲染、评分与本地恢复。
5. 真实课堂浏览器验收及文档状态更新。

每个阶段独立测试和提交，最后快进合并到 `main`，不包含用户当前对 `frontend/package.json` 的未提交修改。

## 验收结果（2026-07-26）

已使用真实课堂 `computational-thinking / Ii0-7a0bpN` 在独立的本地验收端口完成浏览器检查：

- 第 1–4、6–8、10 场 slide 正常渲染，原有上下页导航、PPTX 和 MP4 按钮保留。
- 第 5 场 interactive 完整显示快速排序单趟分区模拟。
- 后台 `SET_WIDGET_STATE` 动作自动选择基准 9，页面进入右指针步骤。
- 验收中发现 OpenMAIC 旧生成模板把消息监听器与 `simState/handleCardClick` 放在不同脚本作用域；本地 HTML 适配器已在不修改持久化课件的前提下桥接这两个既有符号，并增加回归测试。
- 第 9 场 quiz 可完成 3 道客观题和 1 道简答题；正确答案得到 `40/40`，同时显示答案、解析和简答自评标准。
- 离开 quiz 再返回后，选择项、简答文本、提交状态、分数和解析全部恢复。
- interactive iframe 未授予 `allow-same-origin`，运行时诊断仅接受当前 iframe 来源。

自动验证当前包含 86 项前端单元测试，并另有课堂场景适配静态集成守卫；生产构建通过。PBL 仍保持明确的范围边界，未伪装成普通课堂场景。
