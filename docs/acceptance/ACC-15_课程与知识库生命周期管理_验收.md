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

结果：`55 passed`。

覆盖：历史课程成员关系修复、单篇节点文档删除、整库接口不存在、owner 权限、课程级联删除、学生退出及非学生拒绝。

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
$env:PLAYWRIGHT_PORT='5194'
pnpm exec playwright test tests/e2e/course-lifecycle-actions.spec.ts --project=desktop1366 --grep "one document|exact title"
```

结果：两个纠正场景通过：

1. editor 在当前知识节点删除一篇文档，请求只包含目标文档 ID，删除后该文档从节点列表消失。
2. 未输入精确课程名时删除课程按钮禁用；输入后可删除并返回首页。

学生退出课程场景在前序验收中保持通过。

## 人工核对清单

- [x] 页面不存在“删除课程知识库”入口。
- [x] 当前节点的每篇文档具有独立删除入口。
- [x] 删除目标文档不会删除知识图谱节点或其他文档。
- [x] 历史课程创建者和管理员可以恢复看到缺失课程；学生课程隔离不变。
- [x] 删除课程需要输入精确课程名。
- [x] 学生退出课程前有不可撤销影响提示，并说明可用课程码重新加入。
