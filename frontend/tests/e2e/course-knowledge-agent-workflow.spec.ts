import { expect, test } from "./fixtures/teacherApp";


const createdCourse = {
  id: "course-agent-new",
  title: "算法设计",
  description: "面向大二学生的算法设计课程。",
  icon: "school",
  color: "#3157d5",
  objectives: ["掌握复杂度分析", "能设计经典算法"],
  audience: "计算机专业大二学生",
  language: "zh-CN",
  difficulty: "intermediate",
  revision: 1,
  membership_role: "owner",
  created_by: "teacher-a",
};

const root = {
  id: "algorithms",
  label: "算法设计",
  data: { type: "course", summary: "课程知识结构" },
  children: [{
    id: "foundations",
    label: "算法基础",
    data: { type: "knowledge_module", summary: "分析与设计基础" },
    children: [{
      id: "complexity",
      label: "复杂度分析",
      data: { type: "knowledge_point", summary: "时间与空间复杂度" },
      children: [],
    }],
  }],
};

const build = {
  build_id: "kb-agent-1",
  library_id: createdCourse.id,
  status: "draft",
  phase: "proposal_review",
  progress: 0,
  revision: 2,
  config: { update_strategy: "incremental" },
  baseline_graph_version: null,
  baseline_graph: null,
  graph_draft: null,
  textbooks: [],
  topics: [],
  source_candidates: [],
  warnings: [],
  metrics: {},
  quality_checks: [],
  knowledge_proposal: {
    mode: "create",
    summary: "已根据课程信息生成三档可审核大纲。",
    requirements: "",
    items: [],
    options: ["brief", "standard", "complete"].map((level) => ({
      id: level,
      level,
      description: `${level} 课程大纲`,
      root,
      metrics: { leaf_count: 1 },
    })),
  },
};


test("新建课程自动交给 Agent 规划，并从聊天审核链接打开对应方案", async ({ teacherPage: page }) => {
  let sentPrompt = "";
  let chatRequestCount = 0;

  await page.route("**/api/courses", async (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ json: createdCourse });
    }
    return route.fallback();
  });
  await page.route(`**/api/courses/${createdCourse.id}`, (route) =>
    route.fulfill({ json: createdCourse }),
  );
  await page.route(`**/api/courses/${createdCourse.id}/knowledge-base/documents**`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route(`**/api/courses/${createdCourse.id}/knowledge-base/versions`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route(
    `**/api/courses/${createdCourse.id}/knowledge-builds/${build.build_id}`,
    (route) => route.fulfill({ json: build }),
  );
  await page.route("**/api/chat/v2/stream", async (route) => {
    chatRequestCount += 1;
    const request = route.request().postDataJSON() as { question?: string; course_id?: string };
    sentPrompt = request.question || "";
    expect(request.course_id).toBe(createdCourse.id);
    const reviewUrl = `#knowledge?course_id=${createdCourse.id}&build_id=${build.build_id}&action=build`;
    const payload = {
      message: {
        role: "assistant",
        content: `已生成三档课程知识库方案。\n\n[审核方案](${reviewUrl})`,
      },
      conversation: { conversation_id: "course-agent-conversation" },
      action: { name: "knowledge.review" },
      workflow: {
        type: "course_knowledge_base",
        status: "awaiting_confirm",
        stage: "proposal_review",
      },
      knowledge_plan: {
        build_id: build.build_id,
        revision: build.revision,
        status: "awaiting_review",
        review_url: reviewUrl,
      },
      artifacts: [],
      sources: [],
      trace: { path: "deepseek-harness" },
    };
    const events = [
      { type: "result", payload },
      { type: "done", payload: { conversation_id: "course-agent-conversation" } },
    ];
    return route.fulfill({
      contentType: "text/event-stream; charset=utf-8",
      body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""),
    });
  });

  await page.goto("/#home", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "创建课程" }).click();
  const dialog = page.getByRole("dialog", { name: "创建课程并准备知识库" });
  await expect(dialog.getByPlaceholder("例如：高中 Python 编程基础")).toBeVisible();
  await expect(dialog.getByPlaceholder("例如：没有编程基础的高一学生")).toBeVisible();
  await expect(dialog.getByPlaceholder(/能独立完成一个小型数据处理项目/)).toBeVisible();
  await dialog.getByLabel("课程名称").fill(createdCourse.title);
  await dialog.getByLabel("课程简介").fill(createdCourse.description);
  await dialog.getByLabel("教学对象 / 年级").fill(createdCourse.audience);
  await dialog.getByLabel("课程目标").fill(createdCourse.objectives.join("\n"));
  await dialog.getByRole("button", { name: "创建并继续" }).click();

  await expect(page).toHaveURL(new RegExp(`#ai\\?course_id=${createdCourse.id}`));
  await expect.poll(() => sentPrompt).toContain("为这门课规划课程知识库");
  expect(chatRequestCount).toBe(1);
  expect(sentPrompt).toContain(createdCourse.title);
  expect(sentPrompt).toContain(createdCourse.audience);
  expect(sentPrompt).toContain("不要直接发布");

  const reviewLink = page.getByRole("link", { name: "审核方案" });
  await expect(reviewLink).toBeVisible();
  await reviewLink.click();

  await expect(page).toHaveURL(new RegExp(
    `#knowledge\\?course_id=${createdCourse.id}&build_id=${build.build_id}&action=build`,
  ));
  await expect(page.getByRole("dialog", { name: "创建课程知识库" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "比较课程大纲" })).toBeVisible();
  expect(chatRequestCount).toBe(1);
});
