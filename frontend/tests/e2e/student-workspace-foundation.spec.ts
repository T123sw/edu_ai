import { expect, test, type Page, type Route } from "playwright/test";

const course = {
  id: "course-student",
  title: "大学物理",
  description: "力学、电磁学与近代物理课程",
  icon: "school",
  color: "#3157d5",
  objectives: ["理解核心概念"],
  knowledgeGraph: "",
  revision: 3,
  membership_role: "viewer",
  created_by: "teacher-a",
  created_at: "2026-08-01T08:00:00+08:00",
  updated_at: "2026-08-08T10:00:00+08:00",
};

const courseDocument = {
  id: "course-doc-1",
  name: "牛顿运动定律.pdf",
  display_name: "牛顿运动定律",
  type: "file",
  course_id: course.id,
  scope_type: "course",
  scope_id: null,
  library_type: "course",
  owner_user_id: "teacher-a",
  created_at: "2026-08-02T09:00:00+08:00",
  status: "ready",
  chunk_count: 18,
  page_count: 12,
};

const personalDocument = {
  id: "personal-doc-1",
  name: "我的复习笔记.md",
  display_name: "我的复习笔记",
  type: "file",
  course_context_id: course.id,
  library_type: "personal",
  owner_user_id: "student-a",
  created_at: "2026-08-07T09:00:00+08:00",
  status: "ready",
  chunk_count: 7,
};

const personalReport = {
  material_id: "student-report-1",
  material_type: "report",
  course_id: course.id,
  owner_user_id: "student-a",
  visibility: "private",
  title: "我的力学复习报告",
  content: "# 我的力学复习报告\n\n个人复习重点。",
  status: "completed",
  created_at: "2026-08-08T11:00:00+08:00",
  updated_at: "2026-08-08T11:05:00+08:00",
};

const publishedReport = {
  material_id: "course-report-1",
  material_type: "report",
  course_id: course.id,
  visibility: "course",
  title: "教师发布的力学学习指南",
  content: "# 力学学习指南\n\n请先画受力图。",
  publication_status: "published",
  published_by: "teacher-a",
  published_at: "2026-08-08T12:00:00+08:00",
  status: "completed",
  created_at: "2026-08-08T12:00:00+08:00",
  updated_at: "2026-08-08T12:00:00+08:00",
};

const publishedClassroom = {
  material_id: "course-classroom-1",
  material_type: "classroom",
  course_id: course.id,
  visibility: "course",
  title: "牛顿定律互动课堂",
  summary: "通过受力图理解运动状态",
  scenes_count: 1,
  stage: { id: "course-classroom-1", name: "牛顿定律互动课堂" },
  scenes: [{
    id: "scene-1",
    type: "quiz",
    title: "先分析受力",
    content: { type: "quiz", questions: [] },
    actions: [],
  }],
  created_at: "2026-08-08T13:00:00+08:00",
  updated_at: "2026-08-08T13:00:00+08:00",
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json; charset=utf-8", body: JSON.stringify(body) });
}

async function installStudentApi(page: Page) {
  await page.route("https://images.unsplash.com/**", (route) => route.fulfill({ status: 200, contentType: "image/gif", body: Buffer.from("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==", "base64") }));
  await page.route("http://localhost:8001/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === "/api/auth/verify") return json(route, { valid: true, user: { username: "student-a", role: "student" } });
    if (path === "/api/courses") return json(route, [course]);
    if (request.method() === "DELETE" && path === `/api/courses/${course.id}/membership`) return json(route, { ok: true, message: "已退出课程" });
    if (path === `/api/courses/${course.id}`) return json(route, course);
    if (path === "/api/chat/v2/generation/tools") return json(route, { tools: ["report", "mind_map", "quiz", "classroom", "flashcard", "game"].map((tool_id) => ({ tool_id, output_scope: "personal", allowed_source_scopes: ["none", "personal", "course"], can_publish: false })) });
    if (path === "/api/chat/v2/reply") return json(route, { message: { role: "assistant", content: "牛顿第二定律说明合力决定加速度。" }, conversation: { conversation_id: "student-conversation-1" }, action: {}, artifacts: [], trace: { path: "fast" } });
    if (path === "/api/personal-knowledge/documents") return json(route, [personalDocument]);
    if (path === `/api/personal-knowledge/documents/${personalDocument.id}/content`) return json(route, { document_id: personalDocument.id, content: "# 我的复习笔记\n\n合力与加速度同向。" });
    if (path.endsWith("/knowledge-base/documents")) {
      if (request.method() !== "GET") return json(route, { detail: "学生不能修改课程知识库" }, 403);
      return json(route, [courseDocument]);
    }
    if (path.endsWith(`/knowledge-base/documents/${courseDocument.id}/content`)) return json(route, { document_id: courseDocument.id, content: "牛顿第二定律：F=ma。" });
    if (path.endsWith("/knowledge-graph")) return json(route, { root: { id: "physics", label: "大学物理", data: { level: 0, summary: "课程知识" }, children: [{ id: "mechanics", label: "力学", data: { level: 1, summary: "运动与相互作用" }, children: [] }] } });
    if (path === `/api/courses/${course.id}/classrooms`) return json(route, url.searchParams.get("space") === "course" ? [publishedClassroom] : []);
    if (path === `/api/courses/${course.id}/classrooms/${publishedClassroom.material_id}`) return json(route, publishedClassroom);
    if (path === `/api/courses/${course.id}/materials`) return json(route, url.searchParams.get("space") === "course" ? [publishedReport, publishedClassroom] : [personalReport]);
    if (path.includes("/publish") || path.endsWith("/publication")) return json(route, { detail: "学生不能发布课程资源" }, 403);
    if (path.startsWith("/api/jobs")) return json(route, { items: [], next_cursor: null, server_time: "2026-08-09T20:00:00+08:00" });
    return json(route, {});
  });
}

test.beforeEach(async ({ page }) => {
  await installStudentApi(page);
  await page.addInitScript(() => {
    window.localStorage.setItem("edu-ai-auth", JSON.stringify({ token: "student-fixture-token", user: { username: "student-a", role: "student" } }));
    window.localStorage.setItem("stitch-theme", "ocean");
  });
});

async function ensureNavigation(page: Page) {
  const home = page.getByRole("link", { name: "学习首页" }).first();
  if (!(await home.isVisible())) await page.getByRole("button", { name: "打开导航" }).click();
}

test("student enters the isolated six-destination workspace and can ask with course knowledge", async ({ page }) => {
  await page.goto("/#student-home", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("student-shell")).toBeVisible();
  await ensureNavigation(page);
  for (const label of ["学习首页", "AI问答", "课程知识", "个人知识库", "AI课堂", "资源管理"]) await expect(page.getByRole("link", { name: label }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /课程详情|课程设置|运行设置/ })).toHaveCount(0);

  await page.goto(`/#student-ai?course_id=${course.id}`, { waitUntil: "domcontentloaded" });
  if ((page.viewportSize()?.width ?? 0) <= 1180) await page.getByRole("button", { name: "知识库", exact: true }).first().click();
  await expect(page.getByText("课程资料由教师维护，学生仅可选择和预览。")).toBeVisible();
  await page.getByLabel("选择牛顿运动定律").check();
  if ((page.viewportSize()?.width ?? 0) <= 1180) await page.getByRole("button", { name: "知识库", exact: true }).first().click();
  await page.getByPlaceholder("输入问题，Shift + Enter 换行").fill("合力和加速度是什么关系？");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.getByText("牛顿第二定律说明合力决定加速度。")).toBeVisible();

  if ((page.viewportSize()?.width ?? 0) <= 1180) await page.getByRole("button", { name: "生成工具", exact: true }).first().click();
  for (const allowed of ["教学报告", "思维导图", "习题", "AI 课堂", "闪卡", "课堂小游戏"]) await expect(page.getByRole("button", { name: allowed, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "教案", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "教学博客", exact: true })).toHaveCount(0);
});

test("course knowledge and course shared spaces stay read-only while personal spaces remain manageable", async ({ page }) => {
  await page.goto(`/#student-course-knowledge?course_id=${course.id}&view=documents`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("牛顿运动定律", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /上传资料/ })).toHaveCount(0);

  await page.goto("/#student-personal-knowledge", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "只属于你的学习资料" })).toBeVisible();
  await expect(page.getByText("我的复习笔记", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "上传资料" })).toBeVisible();
  await expect(page.getByRole("button", { name: "用于问答" })).toBeDisabled();

  await page.goto(`/#student-resources?course_id=${course.id}&space=mine`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("我的力学复习报告", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "重命名" })).toBeVisible();
  await expect(page.getByRole("button", { name: "删除" })).toBeVisible();
  for (const action of ["发布", "发布到课程", "撤回", "撤回发布"]) await expect(page.getByRole("button", { name: action, exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "课程共享" }).click();
  await expect(page.getByText("教师发布的力学学习指南", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "重命名" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "删除" })).toHaveCount(0);
  for (const action of ["发布", "发布到课程", "撤回", "撤回发布"]) await expect(page.getByRole("button", { name: action, exact: true })).toHaveCount(0);
});

test("course AI classroom is playable and role/API escape paths are denied", async ({ page }) => {
  await page.goto(`/#student-classroom?course_id=${course.id}&space=mine`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: "创建 AI 课堂" })).toBeVisible();
  await page.getByRole("button", { name: "课程 AI 课堂" }).click();
  await expect(page.getByText("牛顿定律互动课堂", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "创建 AI 课堂" })).toHaveCount(0);
  await page.getByRole("button", { name: "开始学习" }).click();
  await expect(page).toHaveURL(new RegExp(`#classroom-player\\?course_id=${course.id}&classroom_id=${publishedClassroom.material_id}`));
  await expect(page.getByRole("region", { name: "课堂舞台" })).toBeVisible();

  await page.goto("/#settings", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/#student-home$/);
  await expect(page.getByTestId("student-shell")).toBeVisible();

  const statuses = await page.evaluate(async (courseId) => {
    const auth = { Authorization: "Bearer student-fixture-token" };
    const courseWrite = await fetch(`http://localhost:8001/api/courses/${courseId}/knowledge-base/documents`, { method: "POST", headers: auth, body: new FormData() });
    const publish = await fetch(`http://localhost:8001/api/courses/${courseId}/materials/report/student-report-1/publish`, { method: "POST", headers: auth });
    return [courseWrite.status, publish.status];
  }, course.id);
  expect(statuses).toEqual([403, 403]);
});

test("student can leave a course from the home course card", async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/#student-home", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: "退出课程" })).toBeVisible({ timeout: 15_000 });

  const requestPromise = page.waitForRequest((request) =>
    request.method() === "DELETE"
      && new URL(request.url()).pathname === `/api/courses/${course.id}/membership`,
  );
  await page.getByRole("button", { name: "退出课程" }).click();
  await requestPromise;
  await expect(page.getByRole("article", { name: course.title })).toHaveCount(0);
});
