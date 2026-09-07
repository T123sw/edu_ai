# 首页继续备课／学习：实施计划（Agent A）

状态：A 实现及前端验收已完成，等待 B 组合验收。设计：[首页继续入口](../specs/2026-09-07-home-resume-design-cn.md)；验收：[A 验收](../acceptance/2026-09-07-home-resume-acceptance-cn.md)；执行边界：[并行约定](2026-09-07-frontend-experience-parallel-handoff-cn.md)。

## 文件所有权

A 独占修改：`frontend/src/stitch/resume/**`（新增）、`pages/HomeDashboard.tsx`、`pages/HomeDashboard.css`、`student/pages/StudentHome.tsx`、`student/pages/studentRecentLearning*`、`student/styles/studentHome.css`、`student/StudentApp.tsx`、`stitch/App.tsx`。这里的简写路径均相对 `frontend/src/stitch/`。

仅在 App 中增加必要的 tracker 挂载，避免改认证、路由协议和全局布局。B／C 要求共享接入时向 A 提交最小补丁说明。

## 执行步骤

- [x] A1 基线：读 AGENTS.md、项目地图、设计及并行约定；记录 HEAD、工作区状态，核对主入口、师生路由、现有 recentLearning 和课程加载流程。
- [x] A2 记录逻辑：实现账号隔离的记录读写、允许路由、参数白名单、损坏降级。为跨账号、非法路由、查询参数变化、权限失效添加行为测试。
- [x] A3 访问跟踪：在成功进入业务页面后记录；避免首页覆盖、首屏加载误写和 StudentApp 原 tracker 双重写入。与 B 核对知识点参数的标准解析，不另加别名。
- [x] A4 界面：新增独立 ResumeEntry 样式，在两端主内容最上方展示真实课程名称＋一个按钮；移除学生旧大块区域，不触碰加入课程流程。
- [x] A5 恢复：使用现有路由构造器；验证所属课程权限。目标子资源失效时同课程降级、请求失败可重试。未发送输入不恢复。
- [x] A6 验证：运行模块测试、师生浏览器用例和生产构建，记录窄屏及桌面证据。
- [x] A7 交付：独立提交并更新 A 验收状态、命令结果、证据路径、恢复粒度和限制；不修改 B／C 验收结果。

## 建议测试与命令

在 `frontend/` 执行（新增文件实现后方可运行对应命令）：

```sh
node --import tsx --test "src/stitch/resume/*.test.ts"
pnpm exec playwright test tests/e2e/home-resume.spec.ts --project=desktop1366
pnpm build
```

新增 `tests/e2e/home-resume.spec.ts`，在用例中再覆盖 390px 窄屏；现有配置没有 mobile project，不调用不存在的项目。针对已变更旧学生历史测试同步调整行为断言，不能只删除失败测试。

## 与其他 Agent 交接

A 可完全独立实现。向 B 提交恢复的 route、courseId、scopeId 例子。若恢复对话当前无可靠 URL 协议，先恢复课程＋知识点工作区，准确记录限制；不要为追求“全部恢复”侵入 ChatPanel。

## 回退

撤回 ResumeEntry 和 tracker 挂载即可恢复原入口；新增存储键可忽略。不得删除整个 localStorage 或覆盖他人工作。


## A 实施交付（2026-09-07）

实现提交：`6ad477dd224e2f9c03499d560743b5f2792aee16`。本轮在现有分支按文件所有权提交，没有 checkout/reset 或打包 B／C 的业务改动。原始基线为 `511ba6b38d616489fd4d03a26e5e839b926798a3`。仓库未配置提交身份，使用仅本次命令生效的 `Codex Agent A <codex-agent-a@localhost>`，未改全局或仓库 Git 配置。

实际契约及恢复限制见 [A 验收交接](../acceptance/2026-09-07-home-resume-acceptance-cn.md#交给-b-的实际契约)。共享 `readWorkspaceScopeFromSearch` 为只读依赖；没有改写 B／C 的聊天、生成、知识点状态或公共文档。

A6 已执行：12 项模块／旧布局测试、15 项 Chromium 浏览器用例、修改范围 ESLint、生产构建。全项目 tsc 不通过：原始基线 80 个诊断、当前并行工作区 72 个诊断，A 修改文件无诊断；详见验收证据。真实后端、真实退出／登录和 I01–I05 组合验证保留给 B。
