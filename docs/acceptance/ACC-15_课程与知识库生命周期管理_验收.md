# ACC-15 课程与知识库生命周期管理验收

## 验收结论

状态：通过。

## 自动化证据

### 后端

命令：

```powershell
$env:PYTHONPATH='src'
python -m pytest -q src/tests/test_course_crud_permissions.py src/tests/test_course_enrollment_api.py src/tests/persistence/test_postgres_knowledge_repository.py src/tests/persistence/test_postgres_core_repositories.py
```

结果：`36 passed`。

覆盖：owner 权限、运行任务冲突、课程级联删除、整库删除、个人资料保留、学生退出及非学生拒绝。

### 前端静态与构建

命令：

```powershell
pnpm exec eslint src/stitch/api/courses.ts src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx src/stitch/course/knowledge/KnowledgeDocumentsView.tsx src/stitch/pages/CourseEdit.tsx src/stitch/student/pages/StudentHome.tsx
pnpm build
```

结果：通过。

### 浏览器端到端

使用独立端口运行当前工作树，避免本机旧开发服务污染：

```powershell
$env:PLAYWRIGHT_PORT='5191'
pnpm exec playwright test tests/e2e/course-lifecycle-actions.spec.ts tests/e2e/student-workspace-foundation.spec.ts --project=desktop1366 --grep "course owner|student can leave"
```

结果：三个新增场景分别通过：

1. owner 确认后发送整库删除请求。
2. 未输入精确课程名时删除课程按钮禁用；输入后可删除并返回首页。
3. 学生确认退出后发送 membership 删除请求，课程卡立即从首页消失。

## 人工核对清单

- [x] editor 不显示“删除课程知识库”。
- [x] owner 在存在共享文档、图谱版本或构建方案时显示删除入口。
- [x] 删除整库后课程仍存在，学生个人资料仍存在。
- [x] 删除课程需要输入精确课程名。
- [x] 学生退出课程前有不可撤销影响提示，并说明可用课程码重新加入。
