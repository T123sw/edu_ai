# Self-learning Frontend Implementation Plan

> 执行方式：按用户已授权的前端重建要求，在当前会话依次实现并验收。

**Goal:** 构建极简首页、三栏课堂、次级工作台及工作台资源中心的可交互前端。

**Architecture:** 新增 src/selfLearning 独立页面和本地模型，复用现有认证服务。main.tsx 默认加载新应用，旧 UI 和播放器导出入口保持显式兼容。

**Tech Stack:** React 18、TypeScript、Vite、原生 CSS、Node test、Playwright。

**Spec:** ../specs/2026-09-14-self-learning-frontend-v1.md

## Global Constraints

- 提交需求直接进入课堂，无独立路线确认步骤。
- 只有工作台出现后台任务控制。
- 学生没有学习文件上传入口。
- 本轮业务交互均为标明身份的本地演示，不调用真实生成和发布服务。
- 数据按账号隔离，刷新恢复学习位置，资源中心只存工作台产物。

## Task 1: 恢复基线与领域交互

Files: src/selfLearning/model.ts、model.test.ts、store.ts。

- [x] 完整备份、Git 基线标签及 history.bundle 校验。
- [x] 定义 Classroom、LearningResource、GenerationJob、Message、LearningState。
- [x] 通过 `createClassroom(requirement)` 构建演示路径；`advanceJobs(state, delta)` 按阶段准备资源，取消/重试保持同一资源身份。
- [x] 测试共享内容个人化、资源与任务分离、播放位置恢复、损坏缓存恢复、生成取消与幂等完成。

## Task 2: 统一入口、首页和课堂

Files: main.tsx、src/selfLearning/App.tsx、Home.tsx、Classroom.tsx、Content.tsx、ui.tsx、styles.css。

- [x] 使用现有 `useAuth` 登录；开发预览 `?preview=student` / `?preview=teacher` 不创建真实会话。
- [x] 首页自然语言提交直接到 `#/classroom/:id`。`#/`、`#/studio`、`#/resources` 分别为课堂首页、工作台、资源中心。
- [x] 资源选择使用 query 参数，阅读、播放、标记完成、笔记及对话随课堂保存。
- [x] 390px 单面板、901px 以上三栏、601–900px 目录+学习/Agent 切换。键盘焦点和弹窗 Escape 关闭。
- [x] 浏览器验证提交、切换、刷新及两个账号隔离；资源切换写入 hash 历史。

## Task 3: 工作台、资源中心与共享发布

Files: src/selfLearning/Studio.tsx、Resources.tsx、PublishDialog.tsx。

- [x] 工作台按需生成报告/视频/课件/习题演示资源；任务取消和重试只在任务页。
- [x] 知识来源页展示课堂关联的检索范围示例，不伪造已爬取来源。
- [x] 资源中心筛选、预览、重命名、二次确认删除；报告导出 Markdown，示例分镜不冒充真实媒体下载。
- [x] 教师上传仅进行本机格式/大小校验和发布预览，明确不真实解析文件；学生无入口。

## Task 4: 交付验证

Files: tsconfig.self-learning.json、playwright.self-learning.config.ts、tests/self-learning/frontend.spec.ts、docs/acceptance/2026-09-14-self-learning-frontend.md。

- [x] 执行新模块类型检查、行为测试、限定 ESLint 和生产构建。
- [x] Playwright 验证桌面及手机主路径、教师发布、学生权限、任务控制及无横向溢出（21 项通过）。
- [x] 实际查看页面截图，修正文字可读性并记录接口待接范围。
- [x] 更新项目总览、归档前端成果，提供本地预览与回退方法。
