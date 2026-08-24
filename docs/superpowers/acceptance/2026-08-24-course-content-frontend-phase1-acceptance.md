# 课程内容体系前端收口（阶段一）验收文档

**日期：** 2026-08-24

**状态：** 待实施后执行

**设计依据：** `docs/superpowers/specs/2026-08-24-course-content-frontend-phase1-design-cn.md`

**实施依据：** `docs/superpowers/plans/2026-08-24-course-content-frontend-phase1.md`

## 1. 验收范围

本次只验收不依赖数据库迁移的前端改造：双端课程知识入口收口、个人资源单空间、个人中心外观设置，以及相关路由兼容和回归验证。后端知识结构、数据库迁移、旧共享副本清理、课程标准资源、学习证据增强和分层 RAG 均不属于本次完成声明。

## 2. 功能验收清单

### A. 课程知识

- [ ] `ACC-KNOW-01` 教师端课程知识直接显示课程知识库，不出现“知识图谱”标签或图谱画布。
- [ ] `ACC-KNOW-02` 学生端课程知识直接显示只读课程知识库，不出现“知识图谱”标签或图谱画布。
- [ ] `ACC-KNOW-03` 教师历史 `#graph?course_id=<id>` 链接重定向到同课程的 `#knowledge?course_id=<id>`。
- [ ] `ACC-KNOW-04` 历史 `view=structure`、`view=documents` 或未知 `view` 参数被安全忽略，不产生空白页。
- [ ] `ACC-KNOW-05` 后端知识结构、知识点作用域和相关 API 未被删除或修改。

### B. 个人资源

- [ ] `ACC-RES-01` 教师端和学生端导航、课程概览、首页指标与资源页面统一使用“个人资源”。
- [ ] `ACC-RES-02` 个人资源页面和聚合计数仅请求 `space=mine`，不并行请求课程共享空间。
- [ ] `ACC-RES-03` 页面不再出现“我的资源/课程共享”切换、发布、更新共享或撤回操作。
- [ ] `ACC-RES-04` 搜索、类型筛选、排序、置顶、预览、重命名、内容编辑和删除仍可用。
- [ ] `ACC-RES-05` 指向非本人私有资源的历史深链接显示“不在个人资源中或无权访问”，不会恢复共享列表。
- [ ] `ACC-RES-06` 教师和学生的 AI课堂入口仍存在，AI课堂自己的个人/课程列表没有被本次收口影响。

### C. 外观设置

- [ ] `ACC-THEME-01` 页面右下角不再出现齿轮形主题悬浮按钮。
- [ ] `ACC-THEME-02` 个人中心显示带调色盘语义的“外观设置”。
- [ ] `ACC-THEME-03` 海蓝、森绿、日落、暗色四个主题均可选择，并有文字或图标选中状态。
- [ ] `ACC-THEME-04` 主题按钮可通过键盘聚焦和操作，并暴露 `aria-pressed` 状态。
- [ ] `ACC-THEME-05` 刷新页面后主题仍通过现有 `stitch-theme` 本地存储保持；非法值仍回落到海蓝。

## 3. 非功能与边界验收

- [ ] `ACC-BOUND-01` `git diff` 不包含 `Edu_AI/api/`、Alembic、数据库文件、`storage/`、`course_data/` 或密钥。
- [ ] `ACC-BOUND-02` 教师端与学生端窄屏导航、个人资源列表和个人中心无新增水平溢出。
- [ ] `ACC-BOUND-03` 历史图谱兼容路由存在，但新导航和按钮不再生成 `#graph`。
- [ ] `ACC-BOUND-04` 前端生产构建成功，未引入新的 TypeScript 或 ESLint 错误。

## 4. 自动化验证命令

在 `Edu_AI/` 目录运行：

```powershell
pnpm test
pnpm lint
pnpm build
```

定向契约检查：

```powershell
pnpm exec node --import tsx --test src/stitch/teacherRoutes.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/legacyRetirement.test.ts src/stitch/course/courseNavigation.test.ts src/stitch/pages/courseCardPresentation.test.ts src/stitch/pages/courseResourcesManagement.test.ts src/stitch/theme/ThemeAppearanceSettings.test.ts
```

边界检查在仓库根目录运行：

```powershell
git diff --name-only a4749c4..HEAD
git status --short
```

## 5. 角色验收路径

| 角色 | 路径 | 预期结果 |
| --- | --- | --- |
| 教师 | 课程 → 课程知识 | 直接进入可管理的课程知识库，无图谱标签 |
| 学生 | 课程 → 课程知识 | 直接进入只读课程知识库，无图谱标签 |
| 教师 | 课程 → 个人资源 | 只见本人生成资源和个人维护操作 |
| 学生 | 课程 → 个人资源 | 只见本人生成资源和个人维护操作 |
| 教师/学生 | 课程 → AI课堂 | 原个人/课程列表仍可访问 |
| 任意角色 | 个人中心 → 外观设置 | 四主题可切换、可访问、刷新后保持 |

## 6. 执行记录

实施完成后，将每条命令的实际退出码和关键输出记录在下表，并据此更新本文状态。任何未通过项必须保留未勾选，不得用“基本通过”替代。

| 验证项 | 实际结果 | 证据摘要 |
| --- | --- | --- |
| 定向测试 | 未执行 | 实施后记录通过数量与退出码 |
| 完整 `pnpm test` | 未执行 | 实施后记录通过数量与退出码 |
| `pnpm lint` | 未执行 | 实施后记录退出码与警告数量 |
| `pnpm build` | 未执行 | 实施后记录退出码与构建产物摘要 |
| 教师手工烟雾 | 未执行 | 实施后记录知识、资源、AI课堂和主题路径 |
| 学生手工烟雾 | 未执行 | 实施后记录知识、资源、AI课堂和主题路径 |
| 修改边界 | 未执行 | 实施后记录差异路径与工作树状态 |

## 7. 阶段二保留项

以下项目明确留到数据库与文件迁入后处理，不应阻塞阶段一验收，也不得被误报为已经完成：

1. 旧课程共享副本与教师个人原件的映射和清理。
2. 叶子知识点标准 AI课堂、学习讲义、练习测评的批量生成。
3. 单项审核、批量通过、版本替换和失败重试。
4. 阅读型/测评型任务、个人资源任务快照和学习证据增强。
5. 教师学习进度与知识点掌握分析。
6. 分层文档检索与后续 RAG 升级。
