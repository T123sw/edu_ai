# 教师端前端基线清单（2026-08-06）

此清单是第三份优化计划开始前的诊断证据，不是批准后的视觉金图。截图由 `tests/e2e/page-baseline.spec.ts` 使用固定教师、固定课程、固定资料、固定任务与固定时间生成，禁止连接真实后端。

## 固定环境

- 用户：`teacher-a`，课程角色 `editor`
- 课程：`course-physics / 大学物理`
- 资料：`doc-mechanics / 大学物理·力学.pdf / ready / 128 chunks`
- 资源：报告与 AI 课堂各一份，时间固定在 2026-08-05
- 视口：1366×768、1440×900、1920×1080、1280×720、1024×768
- 浏览器：Playwright Chromium，`zh-CN`、`Asia/Shanghai`、浅色主题、减少动画

## 页面证据清单

| 页面 | 当前路由 | 截图文件模式 | 已知基线问题 |
|---|---|---|---|
| 登录 | `#home`（无会话） | `baseline-login.png` | 登录态与首页路由耦合，需保留分屏方向并补清晰层级 |
| 课程首页 | `#home` | `baseline-home.png` | 课程卡不是语义链接；教师页面仍使用“智能学习之旅”文案 |
| 课程详情 | `#course-detail?course_id=course-physics` | `baseline-course-detail.png` | 入口较多但没有统一课程导航；主操作在白色内容区几乎不可见 |
| 问答工作台 | `#ai?course_id=course-physics` | `baseline-workspace.png` | 生成面板与问答主区关系不清；中等宽度容易拥挤 |
| 资料库 | `#knowledge?course_id=course-physics` | `baseline-knowledge-documents.png` | 与知识图谱分成两个入口，用户难以判断边界 |
| 知识图谱 | `#graph?course_id=course-physics` | `baseline-knowledge-structure.png` | 存在第二套教材导入心智；画布在紧凑视口受挤压 |
| AI 课堂 | `#classroom-studio?course_id=course-physics` | `baseline-classroom.png` | 与生成工厂入口和配置不统一 |
| 课程资源 | `#resources?course_id=course-physics` | `baseline-resources.png` | 中等宽度的列表/预览组合及长内容容器需要检查 |
| 课程设置 | `#edit?course_id=course-physics` | `baseline-settings.png` | 尚未使用统一课程外壳和共享状态组件 |

每个项目的实际截图保存在 Playwright `test-results/e2e/<project>/` 输出目录。只有对应优化任务通过结构、溢出、键盘与人工复核后，才允许建立批准快照。

## 优化后批准基线（2026-08-07）

优化后的批准快照由 `tests/e2e/visual-regression.spec.ts` 维护，固定存放在
`tests/e2e/visual-regression.spec.ts-snapshots/`。浅色主题覆盖上述五个视口和 11 个核心页面；
深色主题覆盖 1366×768 与 1024×768。截图只作为变化检测基线，是否批准仍以
`docs/qa/teacher-frontend-release-checklist.md` 的人工复核记录为准。

与诊断基线相比，批准基线已经具备统一课程工作空间、课程知识双视图、共享生成工厂、
类型化资源预览与紧凑视口课堂控制。登录页通过无效鉴权响应与本地会话清理双重隔离，
保证截图确实为未登录状态，而不是初始化脚本恢复出的课程首页。
