# Teacher Frontend IA Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the teacher frontend from a platform-first navigation model into a course-first experience with a welcome shell, a course shell, six teacher course sections, and compatibility redirects for existing teacher routes.

**Architecture:** Introduce a teacher-specific route model as the single source of truth for paths, labels, and legacy redirects. Build a lightweight global teacher header plus two teacher shells, then re-home teacher pages into `/teacher/welcome` and `/teacher/courses/:courseId/*` while keeping student routes unchanged. Split the old mixed teacher course detail surface into dedicated `details`, `knowledge-base`, and `videos` experiences so content flow rules become explicit in code.

**Tech Stack:** React 18, TypeScript, React Router v6, Ant Design 5, Zustand, Vite, `tsx`, `node:assert`

---

## File Structure

**Create:**

- `Edu_AI/src/routes/teacherRouteModel.ts`
- `Edu_AI/src/layout/teacherHeaderModel.ts`
- `Edu_AI/src/layout/TeacherHeader.tsx`
- `Edu_AI/src/layout/TeacherWelcomeLayout.tsx`
- `Edu_AI/src/layout/TeacherCourseLayout.tsx`
- `Edu_AI/src/pages/teacher/teacherWelcomeModel.ts`
- `Edu_AI/src/pages/teacher/TeacherWelcomePage.tsx`
- `Edu_AI/src/pages/teacher/TeacherCourseAssistantPage.tsx`
- `Edu_AI/src/pages/teacher/TeacherCourseResourcesPage.tsx`
- `Edu_AI/src/pages/teacher/TeacherCourseVideosPage.tsx`
- `Edu_AI/src/pages/teacher/TeacherCourseKnowledgeBasePage.tsx`
- `Edu_AI/src/pages/teacher/TeacherCourseDetailsPage.tsx`
- `Edu_AI/src/pages/teacher/courseAssetPlacement.ts`
- `Edu_AI/tests/frontend/teacherRouteModel.test.ts`
- `Edu_AI/tests/frontend/teacherHeaderModel.test.ts`
- `Edu_AI/tests/frontend/teacherWelcomeModel.test.ts`
- `Edu_AI/tests/frontend/teacherLegacyRedirects.test.ts`
- `Edu_AI/tests/frontend/courseAssetPlacement.test.ts`

**Modify:**

- `Edu_AI/src/routes/AppRoutes.tsx`
- `Edu_AI/src/layout/GlobalLayout.tsx`
- `Edu_AI/src/layout/CourseContextLayout.tsx`
- `Edu_AI/src/layout/SharedHeader.tsx`
- `Edu_AI/src/pages/WelcomePage.tsx`
- `Edu_AI/src/pages/teacher/CourseDetailPage.tsx`
- `Edu_AI/src/pages/teacher/CourseMaterialsPage.tsx`
- `Edu_AI/src/store/course/useCourseStore.ts`

**Keep but route through wrappers/adapters:**

- `Edu_AI/src/pages/teacher/AiStudioPage.tsx`
- `Edu_AI/src/pages/teacher/KnowledgeGraphPage.tsx`

---

### Task 1: Establish the Teacher Route Model

**Files:**
- Create: `Edu_AI/src/routes/teacherRouteModel.ts`
- Test: `Edu_AI/tests/frontend/teacherRouteModel.test.ts`

- [ ] **Step 1: Write the failing route-model test**

```ts
import assert from 'node:assert/strict';

import {
  TEACHER_HOME_PATH,
  TEACHER_SETTINGS_PATH,
  TEACHER_COURSE_SECTIONS,
  buildTeacherCourseNavItems,
  buildTeacherCoursePath,
  resolveTeacherLandingPath,
} from '../../src/routes/teacherRouteModel.ts';

assert.equal(TEACHER_HOME_PATH, '/teacher/welcome');
assert.equal(TEACHER_SETTINGS_PATH, '/settings');
assert.deepEqual(
  TEACHER_COURSE_SECTIONS,
  ['assistant', 'knowledge-graph', 'resources', 'videos', 'knowledge-base', 'details'],
);

assert.equal(
  buildTeacherCoursePath('course-1', 'assistant'),
  '/teacher/courses/course-1/assistant',
);

assert.equal(
  buildTeacherCoursePath('course-1', 'details'),
  '/teacher/courses/course-1/details',
);

assert.deepEqual(
  buildTeacherCourseNavItems('course-1').map((item) => item.key),
  [
    '/teacher/courses/course-1/assistant',
    '/teacher/courses/course-1/knowledge-graph',
    '/teacher/courses/course-1/resources',
    '/teacher/courses/course-1/videos',
    '/teacher/courses/course-1/knowledge-base',
    '/teacher/courses/course-1/details',
  ],
);

assert.deepEqual(
  buildTeacherCourseNavItems('course-1').map((item) => item.label),
  ['问答助手', '知识图谱', '课程资源', '教学视频', '课程知识库', '课程详情'],
);

assert.equal(
  resolveTeacherLandingPath({ courseId: 'course-1', isNewCourse: false }),
  '/teacher/courses/course-1/assistant',
);

assert.equal(
  resolveTeacherLandingPath({ courseId: 'course-1', isNewCourse: true }),
  '/teacher/courses/course-1/details',
);

console.log('teacherRouteModel tests passed');
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx tsx tests/frontend/teacherRouteModel.test.ts`
Expected: FAIL with `Cannot find module '../../src/routes/teacherRouteModel.ts'`.

- [ ] **Step 3: Implement the route model**

```ts
// Edu_AI/src/routes/teacherRouteModel.ts
export const TEACHER_HOME_PATH = '/teacher/welcome';
export const TEACHER_SETTINGS_PATH = '/settings';

export const TEACHER_COURSE_SECTIONS = [
  'assistant',
  'knowledge-graph',
  'resources',
  'videos',
  'knowledge-base',
  'details',
] as const;

export type TeacherCourseSection = (typeof TEACHER_COURSE_SECTIONS)[number];

export interface TeacherCourseNavItem {
  key: string;
  label: string;
}

const TEACHER_COURSE_LABELS: Record<TeacherCourseSection, string> = {
  assistant: '问答助手',
  'knowledge-graph': '知识图谱',
  resources: '课程资源',
  videos: '教学视频',
  'knowledge-base': '课程知识库',
  details: '课程详情',
};

export function buildTeacherCoursePath(
  courseId: string,
  section: TeacherCourseSection,
): string {
  return `/teacher/courses/${courseId}/${section}`;
}

export function buildTeacherCourseNavItems(courseId: string): TeacherCourseNavItem[] {
  return TEACHER_COURSE_SECTIONS.map((section) => ({
    key: buildTeacherCoursePath(courseId, section),
    label: TEACHER_COURSE_LABELS[section],
  }));
}

export function resolveTeacherLandingPath(args: {
  courseId: string;
  isNewCourse: boolean;
}): string {
  return buildTeacherCoursePath(args.courseId, args.isNewCourse ? 'details' : 'assistant');
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx tsx tests/frontend/teacherRouteModel.test.ts`
Expected: PASS with `teacherRouteModel tests passed`.

- [ ] **Step 5: Commit**

```bash
git add src/routes/teacherRouteModel.ts tests/frontend/teacherRouteModel.test.ts
git commit -m "feat: add teacher route model"
```

### Task 2: Build the Lightweight Teacher Header and Shell Layouts

**Files:**
- Create: `Edu_AI/src/layout/teacherHeaderModel.ts`
- Create: `Edu_AI/src/layout/TeacherHeader.tsx`
- Create: `Edu_AI/src/layout/TeacherWelcomeLayout.tsx`
- Create: `Edu_AI/src/layout/TeacherCourseLayout.tsx`
- Test: `Edu_AI/tests/frontend/teacherHeaderModel.test.ts`

- [ ] **Step 1: Write the failing header-model test**

```ts
import assert from 'node:assert/strict';

import { buildTeacherHeaderState } from '../../src/layout/teacherHeaderModel.ts';

const headerState = buildTeacherHeaderState({
  courses: [
    { id: 'course-a', title: '课程 A' },
    { id: 'course-b', title: '课程 B' },
  ] as any,
  currentCourseId: 'course-b',
});

assert.equal(headerState.homePath, '/teacher/welcome');
assert.equal(headerState.currentCourseLabel, '课程 B');
assert.deepEqual(
  headerState.courseOptions.map((item) => item.value),
  ['course-a', 'course-b'],
);

console.log('teacherHeaderModel tests passed');
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx tsx tests/frontend/teacherHeaderModel.test.ts`
Expected: FAIL with `Cannot find module '../../src/layout/teacherHeaderModel.ts'`.

- [ ] **Step 3: Implement the header model and teacher shell components**

```ts
// Edu_AI/src/layout/teacherHeaderModel.ts
import type { Course } from '../store/course/useCourseStore';
import { TEACHER_HOME_PATH } from '../routes/teacherRouteModel';

export function buildTeacherHeaderState(args: {
  courses: Course[];
  currentCourseId?: string;
}) {
  const courseOptions = args.courses.map((course) => ({
    label: course.title,
    value: course.id,
  }));

  const currentCourseLabel =
    args.courses.find((course) => course.id === args.currentCourseId)?.title || '选择课程';

  return {
    homePath: TEACHER_HOME_PATH,
    currentCourseLabel,
    courseOptions,
  };
}
```

```tsx
// Edu_AI/src/layout/TeacherHeader.tsx
import React from 'react';
import { Layout, Avatar, Dropdown, Space, Select, Input, Button } from 'antd';
import type { MenuProps } from 'antd';
import { HomeOutlined, UserOutlined, LogoutOutlined, SettingOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useCourseStore } from '../store/course/useCourseStore';
import { buildTeacherHeaderState } from './teacherHeaderModel';
import { buildTeacherCoursePath } from '../routes/teacherRouteModel';

const { Header } = Layout;

export default function TeacherHeader() {
  const navigate = useNavigate();
  const { courseId } = useParams();
  const { logout, user } = useAuth();
  const { courses } = useCourseStore();
  const headerState = buildTeacherHeaderState({ courses, currentCourseId: courseId });

  const userMenuItems: MenuProps['items'] = [
    { key: '/settings', icon: <SettingOutlined />, label: '个人设置' },
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
  ];

  const onUserMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'logout') {
      logout();
      navigate('/login');
      return;
    }
    navigate(String(key));
  };

  return (
    <Header style={{ background: '#fff', borderBottom: '1px solid var(--color-border)', padding: '0 16px' }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', height: '100%' }}>
        <Button icon={<HomeOutlined />} onClick={() => navigate(headerState.homePath)}>
          欢迎页
        </Button>
        <Select
          value={courseId}
          placeholder={headerState.currentCourseLabel}
          style={{ width: 240 }}
          options={headerState.courseOptions}
          onChange={(nextCourseId) => navigate(buildTeacherCoursePath(nextCourseId, 'assistant'))}
        />
        <Input.Search
          placeholder="全局搜索课程或内容"
          style={{ maxWidth: 320 }}
          onSearch={(value) => navigate(`${headerState.homePath}?q=${encodeURIComponent(value)}`)}
        />
        <div style={{ marginLeft: 'auto' }}>
          <Dropdown menu={{ items: userMenuItems, onClick: onUserMenuClick }} placement="bottomRight">
            <a onClick={(event) => event.preventDefault()}>
              <Space>
                <Avatar icon={<UserOutlined />} size="small" />
                {user?.username || '用户'}
              </Space>
            </a>
          </Dropdown>
        </div>
      </div>
    </Header>
  );
}
```

```tsx
// Edu_AI/src/layout/TeacherWelcomeLayout.tsx
import React from 'react';
import { Layout } from 'antd';
import { Outlet } from 'react-router-dom';
import TeacherHeader from './TeacherHeader';

const { Content } = Layout;

export default function TeacherWelcomeLayout() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <TeacherHeader />
      <Content style={{ padding: 24, overflow: 'auto' }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
```

```tsx
// Edu_AI/src/layout/TeacherCourseLayout.tsx
import React from 'react';
import { Layout, Menu } from 'antd';
import { Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import TeacherHeader from './TeacherHeader';
import { buildTeacherCourseNavItems } from '../routes/teacherRouteModel';

const { Sider, Content } = Layout;

export default function TeacherCourseLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { courseId = '' } = useParams();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <TeacherHeader />
      <Layout>
        <Sider width={220} theme="dark">
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[location.pathname]}
            items={buildTeacherCourseNavItems(courseId)}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Content style={{ padding: 0, overflow: 'hidden' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx tsx tests/frontend/teacherHeaderModel.test.ts`
Expected: PASS with `teacherHeaderModel tests passed`.

- [ ] **Step 5: Commit**

```bash
git add src/layout/teacherHeaderModel.ts src/layout/TeacherHeader.tsx src/layout/TeacherWelcomeLayout.tsx src/layout/TeacherCourseLayout.tsx tests/frontend/teacherHeaderModel.test.ts
git commit -m "feat: add teacher header and shell layouts"
```

### Task 3: Create the Teacher Welcome Page

**Files:**
- Create: `Edu_AI/src/pages/teacher/teacherWelcomeModel.ts`
- Create: `Edu_AI/src/pages/teacher/TeacherWelcomePage.tsx`
- Modify: `Edu_AI/src/store/course/useCourseStore.ts`
- Test: `Edu_AI/tests/frontend/teacherWelcomeModel.test.ts`

- [ ] **Step 1: Write the failing welcome-model test**

```ts
import assert from 'node:assert/strict';

import { buildTeacherWelcomeViewModel } from '../../src/pages/teacher/teacherWelcomeModel.ts';

const viewModel = buildTeacherWelcomeViewModel({
  courses: [
    { id: 'course-a', title: '课程 A', description: 'A', updatedAt: '2026-04-07T09:00:00Z' },
    { id: 'course-b', title: '课程 B', description: 'B', updatedAt: '2026-04-07T10:00:00Z' },
  ] as any,
  recentCourseIds: ['course-b'],
});

assert.equal(viewModel.summary.totalCourses, 2);
assert.equal(viewModel.recentCourses[0].id, 'course-b');
assert.equal(viewModel.primaryCtaLabel, '新建课程');

console.log('teacherWelcomeModel tests passed');
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx tsx tests/frontend/teacherWelcomeModel.test.ts`
Expected: FAIL with `Cannot find module '../../src/pages/teacher/teacherWelcomeModel.ts'`.

- [ ] **Step 3: Implement the welcome model and page**

```ts
// Edu_AI/src/pages/teacher/teacherWelcomeModel.ts
import type { Course } from '../../store/course/useCourseStore';

export function buildTeacherWelcomeViewModel(args: {
  courses: Course[];
  recentCourseIds: string[];
}) {
  const recentCourses = args.recentCourseIds
    .map((id) => args.courses.find((course) => course.id === id))
    .filter(Boolean) as Course[];

  return {
    summary: {
      totalCourses: args.courses.length,
      recentlyVisited: recentCourses.length,
    },
    recentCourses,
    primaryCtaLabel: '新建课程',
  };
}
```

```tsx
// Edu_AI/src/pages/teacher/TeacherWelcomePage.tsx
import React, { useEffect, useMemo, useState } from 'react';
import { Button, Card, Col, Form, Input, Modal, Row, Space, Statistic, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCourseStore } from '../../store/course/useCourseStore';
import { buildTeacherWelcomeViewModel } from './teacherWelcomeModel';
import { resolveTeacherLandingPath } from '../../routes/teacherRouteModel';

const { Title, Paragraph, Text } = Typography;

export default function TeacherWelcomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { courses, loadCoursesFromBackend, addCourse } = useCourseStore();
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    loadCoursesFromBackend();
  }, [loadCoursesFromBackend]);

  const recentCourseIds = useMemo(() => {
    const raw = window.localStorage.getItem('teacher-recent-course-ids');
    return raw ? (JSON.parse(raw) as string[]) : [];
  }, []);

  const viewModel = buildTeacherWelcomeViewModel({ courses, recentCourseIds });

  const openCourse = (courseId: string, isNewCourse = false) => {
    navigate(resolveTeacherLandingPath({ courseId, isNewCourse }));
  };

  const handleCreate = async () => {
    const values = await form.validateFields();
    const saved = await addCourse({
      id: '',
      title: values.title,
      description: values.description || '',
      icon: 'CommentOutlined',
      color: '#1890ff',
      objectives: [],
    });
    setCreateOpen(false);
    form.resetFields();
    openCourse(saved.id, true);
  };

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Title level={2}>欢迎回来，{user?.username || '教师'}</Title>
        <Paragraph type="secondary">从课程开始，而不是从平台模块开始。</Paragraph>
      </div>

      <Row gutter={16}>
        <Col span={8}><Card><Statistic title="课程总数" value={viewModel.summary.totalCourses} /></Card></Col>
        <Col span={8}><Card><Statistic title="最近访问" value={viewModel.summary.recentlyVisited} /></Card></Col>
        <Col span={8}><Card><Button type="primary" block onClick={() => setCreateOpen(true)}>{viewModel.primaryCtaLabel}</Button></Card></Col>
      </Row>

      <Card title="我的课程">
        <Row gutter={[16, 16]}>
          {courses.map((course) => (
            <Col span={8} key={course.id}>
              <Card hoverable onClick={() => openCourse(course.id)}>
                <Title level={4}>{course.title}</Title>
                <Text type="secondary">{course.description}</Text>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      <Card title="最近使用">
        <Space direction="vertical" style={{ width: '100%' }}>
          {viewModel.recentCourses.map((course) => (
            <Button key={course.id} type="text" onClick={() => openCourse(course.id)}>
              {course.title}
            </Button>
          ))}
        </Space>
      </Card>

      <Modal title="新建课程" open={createOpen} onOk={handleCreate} onCancel={() => setCreateOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="课程名称" rules={[{ required: true, message: '请输入课程名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="课程简介">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
```

```ts
// Edu_AI/src/store/course/useCourseStore.ts
// Change the addCourse signature and implementation so it returns the saved course.
addCourse: async (course) => {
  const payload: BackendCourse = {
    id: course.id || `course-${Date.now()}`,
    title: course.title,
    description: course.description,
    icon: course.icon,
    color: course.color,
    objectives: course.objectives,
    knowledgeGraph: course.knowledgeGraph,
  };
  const saved = await createCourseBackend(payload);
  const savedCourse = { ...saved, masterKnowledgeBase: [] };
  set((state) => ({
    courses: [...state.courses, savedCourse],
  }));
  return savedCourse;
},
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx tsx tests/frontend/teacherWelcomeModel.test.ts`
Expected: PASS with `teacherWelcomeModel tests passed`.

- [ ] **Step 5: Commit**

```bash
git add src/pages/teacher/teacherWelcomeModel.ts src/pages/teacher/TeacherWelcomePage.tsx src/store/course/useCourseStore.ts tests/frontend/teacherWelcomeModel.test.ts
git commit -m "feat: add teacher welcome page"
```

### Task 4: Wire Teacher Routes, Shells, and Legacy Redirects

**Files:**
- Create: `Edu_AI/src/pages/teacher/TeacherCourseAssistantPage.tsx`
- Create: `Edu_AI/src/pages/teacher/TeacherCourseResourcesPage.tsx`
- Modify: `Edu_AI/src/routes/AppRoutes.tsx`
- Modify: `Edu_AI/src/layout/GlobalLayout.tsx`
- Modify: `Edu_AI/src/layout/CourseContextLayout.tsx`
- Test: `Edu_AI/tests/frontend/teacherLegacyRedirects.test.ts`

- [ ] **Step 1: Write the failing legacy-redirect test**

```ts
import assert from 'node:assert/strict';

import {
  buildTeacherCoursePath,
  resolveTeacherLegacyRedirect,
} from '../../src/routes/teacherRouteModel.ts';

assert.equal(
  resolveTeacherLegacyRedirect('/welcome'),
  '/teacher/welcome',
);

assert.equal(
  resolveTeacherLegacyRedirect('/course/course-1/studio'),
  buildTeacherCoursePath('course-1', 'assistant'),
);

assert.equal(
  resolveTeacherLegacyRedirect('/course/course-1/resources'),
  buildTeacherCoursePath('course-1', 'resources'),
);

console.log('teacherLegacyRedirects tests passed');
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx tsx tests/frontend/teacherLegacyRedirects.test.ts`
Expected: FAIL with `resolveTeacherLegacyRedirect is not a function` or equivalent export error.

- [ ] **Step 3: Implement wrappers and route wiring**

```tsx
// Edu_AI/src/pages/teacher/TeacherCourseAssistantPage.tsx
import React from 'react';
import AiStudioPage from './AiStudioPage';

export default function TeacherCourseAssistantPage() {
  return <AiStudioPage />;
}
```

```tsx
// Edu_AI/src/pages/teacher/TeacherCourseResourcesPage.tsx
import React from 'react';
import CourseMaterialsPage from './CourseMaterialsPage';

export default function TeacherCourseResourcesPage() {
  return <CourseMaterialsPage />;
}
```
