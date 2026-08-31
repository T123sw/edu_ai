# 学习资源生成内嵌配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“学习资源生成”按钮改为在课程知识页下方展开配置，并删除错误的独立页面跳转。

**Architecture:** `CourseKnowledgeBuildCard` 统一管理知识库向导与学习资源面板的互斥状态。学习资源面板复用 `StandardLearningResources`，现有后台批次、轮询、审核和重试逻辑保持不变；应用路由恢复到变更前状态。

**Tech Stack:** React 18、TypeScript、Node test runner、Playwright、现有课程知识组件。

---

### Task 1: 用失败测试锁定内嵌展开行为

**Files:**
- Modify: `Edu_AI/src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`
- Modify: `Edu_AI/tests/e2e/course-knowledge.spec.ts`

- [ ] **Step 1: 把源码约束改为按钮、内嵌面板和无独立路由**

测试必须断言 `CourseKnowledgeBuildCard` 使用 `button` 和本地展开状态、渲染 `StandardLearningResources`，并断言应用不再注册 `learning-resource-generation`。

- [ ] **Step 2: 把浏览器测试改为点击后 URL 不变且配置区域可见**

浏览器测试点击“学习资源生成”按钮，验证仍处于 `#knowledge`，随后选择知识点并确认生成按钮可用。

- [ ] **Step 3: 运行定向测试确认因当前链接跳转实现而失败**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

Expected: FAIL，失败信息表明入口仍是独立路由链接，尚无内嵌面板状态。

### Task 2: 实现内嵌配置并保证面板互斥

**Files:**
- Create: `Edu_AI/src/stitch/course/knowledge/LearningResourceGenerationPanel.tsx`
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx`
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.css`

- [ ] **Step 1: 创建内嵌配置面板**

组件接收 `onClose`，渲染标题、后台任务说明、收起按钮与 `<StandardLearningResources />`。

- [ ] **Step 2: 将链接替换为状态按钮**

在 `CourseKnowledgeBuildCard` 增加 `resourceConfigOpen`；点击学习资源按钮时切换该状态并关闭 `wizardOpen`。

- [ ] **Step 3: 打开知识库向导时关闭学习资源面板**

在知识库草稿恢复和新建成功的两个分支中先调用 `setResourceConfigOpen(false)`，再打开向导。

- [ ] **Step 4: 在操作区下方条件渲染面板并补充样式**

面板与现有向导处于同一布局层级，采用当前卡片的边框、圆角和背景变量。

- [ ] **Step 5: 运行定向测试确认通过**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

Expected: PASS。

### Task 3: 删除独立页面与路由

**Files:**
- Delete: `Edu_AI/src/stitch/pages/LearningResourceGeneration.tsx`
- Delete: `Edu_AI/src/stitch/pages/learningResourceGeneration.css`
- Modify: `Edu_AI/src/stitch/App.tsx`
- Modify: `Edu_AI/src/stitch/shared.tsx`
- Modify: `Edu_AI/src/stitch/teacherRoutes.ts`
- Modify: `Edu_AI/src/stitch/course/courseNavigation.ts`
- Modify: `Edu_AI/src/stitch/course/courseNavigation.test.ts`

- [ ] **Step 1: 移除页面懒加载和路由表项**

删除 `LearningResourceGenerationPage` 的懒加载、页面映射和共享路由常量。

- [ ] **Step 2: 从教师路由类型与课程导航归属中移除独立路由**

恢复知识导航仅包含 `knowledge` 和 `graph`，删除教师路由解析白名单中的 `learning-resource-generation`。

- [ ] **Step 3: 删除独立页面文件并更新导航测试**

导航测试不再期望独立路由属于知识分组。

- [ ] **Step 4: 运行相关单元测试**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts src/stitch/course/courseNavigation.test.ts src/stitch/teacherRoutes.test.ts`

Expected: PASS。

### Task 4: 验证完整行为

**Files:**
- Verify: `Edu_AI/tests/e2e/course-knowledge.spec.ts`

- [ ] **Step 1: 运行前端全量测试和构建**

Run: `cd Edu_AI && pnpm test`

Expected: 全部通过。

Run: `cd Edu_AI && pnpm build`

Expected: 构建成功，无类型错误。

- [ ] **Step 2: 运行课程知识浏览器测试**

Run: `cd Edu_AI && pnpm exec playwright test tests/e2e/course-knowledge.spec.ts`

Expected: 全部通过；学习资源入口不再改变 URL。
