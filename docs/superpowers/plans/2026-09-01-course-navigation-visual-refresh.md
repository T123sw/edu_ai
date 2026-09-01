# Course Navigation Visual Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将课程顶部五个主导航入口改为无图标的 B1 纯文字样式，并用均衡字体、沉稳颜色和短下划线表达选中状态。

**Architecture:** 保持 `CourseShell` 的路由和无障碍语义不变，只移除主导航链接中的装饰图标节点。视觉规则继续集中在 `stitch/styles.css`，通过伪元素绘制选中下划线，避免改变 DOM 与布局高度。为保持当前开发服务热更新，本计划在现有前端工作区执行。

**Tech Stack:** React、TypeScript、CSS、Node.js test runner、Vite

---

### Task 1: 移除主导航图标结构

**Files:**
- Modify: `frontend/src/stitch/course/CourseShell.test.ts`
- Modify: `frontend/src/stitch/course/CourseShell.tsx`

- [ ] **Step 1: 写入失败测试**

在 `CourseShell.test.ts` 的课程工作栏测试中增加源码契约：

```ts
assert.doesNotMatch(shell, /course-navigation__icon|<MaterialIcon name=\{item\.icon\}/u);
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd Edu_AI && node --import tsx --test src/stitch/course/CourseShell.test.ts`

Expected: FAIL，因为 `CourseShell.tsx` 仍渲染 `course-navigation__icon`。

- [ ] **Step 3: 写入最小实现**

将主导航链接内容从：

```tsx
<span className="course-navigation__icon"><MaterialIcon name={item.icon} /></span>
<strong>{item.label}</strong>
```

改为：

```tsx
<strong>{item.label}</strong>
```

课程下拉箭头、课程菜单图标、任务中心、个人中心和移动端菜单图标保持不变。

- [ ] **Step 4: 运行测试并确认通过**

Run: `cd Edu_AI && node --import tsx --test src/stitch/course/CourseShell.test.ts`

Expected: 3 tests PASS。

- [ ] **Step 5: 提交结构修改**

```bash
git add frontend/src/stitch/course/CourseShell.test.ts frontend/src/stitch/course/CourseShell.tsx
git commit -m "refactor: remove course navigation icons"
```

### Task 2: 应用 B1 字体、颜色和选中态

**Files:**
- Modify: `frontend/src/stitch/course/CourseShell.test.ts`
- Modify: `frontend/src/stitch/styles.css`

- [ ] **Step 1: 写入失败样式测试**

在 `desktop workbar navigation is left aligned with readable labels` 测试中验证以下规则：

```ts
assert.match(styles, /\.course-navigation__link strong\s*\{[^}]*font-family:\s*"Microsoft YaHei UI"[^}]*font-size:\s*25px;[^}]*font-weight:\s*600;/u);
assert.match(styles, /\.course-navigation__link\.is-active strong\s*\{[^}]*font-weight:\s*700;/u);
assert.match(styles, /\.course-navigation__link\.is-active::after\s*\{[^}]*width:\s*30px;[^}]*height:\s*2px;/u);
assert.doesNotMatch(styles, /\.course-navigation__icon/u);
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd Edu_AI && node --import tsx --test src/stitch/course/CourseShell.test.ts`

Expected: FAIL，因为现有样式仍使用 760 字重、图标规则和方框选中态。

- [ ] **Step 3: 写入最小样式实现**

将主导航样式调整为：

```css
.course-navigation__link {
  position: relative;
  display: inline-flex;
  min-height: 48px;
  align-items: center;
  border-radius: 10px;
  padding: 0 15px;
  color: color-mix(in srgb, var(--course-shell-ink) 72%, var(--course-shell-muted));
  white-space: nowrap;
  transition: background-color 160ms ease, color 160ms ease;
}

.course-navigation__link::after {
  position: absolute;
  bottom: 2px;
  left: 50%;
  width: 0;
  height: 2px;
  border-radius: 999px;
  background: var(--course-shell-brand);
  content: "";
  transform: translateX(-50%);
  transition: width 160ms ease;
}

.course-navigation__link:hover {
  background: color-mix(in srgb, var(--course-shell-brand-soft) 38%, transparent);
  color: var(--course-shell-ink);
}

.course-navigation__link.is-active {
  background: transparent;
  color: var(--course-shell-brand);
  box-shadow: none;
}

.course-navigation__link.is-active::after { width: 30px; }

.course-navigation__link strong {
  display: block;
  font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
  font-size: 25px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 1.2;
}

.course-navigation__link.is-active strong { font-weight: 700; }
```

删除 `.course-navigation__icon`、`.course-navigation__icon .app-icon` 以及 1179px 媒体查询中的图标隐藏规则。

- [ ] **Step 4: 运行聚焦测试**

Run: `cd Edu_AI && node --import tsx --test src/stitch/course/CourseShell.test.ts`

Expected: 3 tests PASS。

- [ ] **Step 5: 运行完整验证**

```bash
cd Edu_AI
pnpm test
pnpm lint
pnpm build
```

Expected: 402 tests PASS；lint 为 0 errors；Vite production build succeeds。

- [ ] **Step 6: 检查补丁并提交**

```bash
git diff --check
git add frontend/src/stitch/course/CourseShell.test.ts frontend/src/stitch/styles.css
git commit -m "style: refine course navigation typography"
```
