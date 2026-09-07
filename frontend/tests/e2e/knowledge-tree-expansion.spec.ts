import { expect, test } from "./fixtures/teacherApp";

const knowledgeTree = {
  root: {
    id: "physics",
    label: "大学物理",
    children: [
      {
        id: "mechanics",
        label: "力学",
        children: [
          {
            id: "kinematics",
            label: "运动学",
            children: [{ id: "velocity", label: "速度与加速度" }],
          },
        ],
      },
      { id: "electromagnetism", label: "电磁学" },
    ],
  },
};

test.beforeEach(async ({ teacherPage }) => {
  await teacherPage.route("**/api/courses/course-physics/knowledge-graph", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(knowledgeTree),
    }),
  );
});

test("knowledge directory labels reveal and collapse one level at a time", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=structure", { waitUntil: "domcontentloaded" });

  await expect(teacherPage.locator(".knowledge-library__node-select")).toHaveCount(3);
  await expect(teacherPage.getByText("运动学", { exact: true })).toHaveCount(0);

  await teacherPage.locator(".knowledge-library__node-select").filter({ hasText: "力学" }).click();
  await expect(teacherPage.getByText("运动学", { exact: true })).toBeVisible();
  await expect(teacherPage.getByText("速度与加速度", { exact: true })).toHaveCount(0);

  await teacherPage.locator(".knowledge-library__node-select").filter({ hasText: "力学" }).click();
  await expect(teacherPage.getByText("运动学", { exact: true })).toHaveCount(0);
});

test("course knowledge directory uses the same collapsed tree behavior", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=documents", { waitUntil: "domcontentloaded" });

  const directoryWidth = await teacherPage.locator(".knowledge-library__nodes").evaluate((element) => element.getBoundingClientRect().width);
  expect(directoryWidth).toBeGreaterThan(0);
  await expect(teacherPage.locator(".knowledge-library__node-select")).toHaveCount(3);
  await expect(teacherPage.getByText("运动学", { exact: true })).toHaveCount(0);

  await teacherPage.locator(".knowledge-library__node-select").filter({ hasText: "力学" }).click();
  await expect(teacherPage.getByText("运动学", { exact: true })).toBeVisible();
  await expect(teacherPage.getByText("速度与加速度", { exact: true })).toHaveCount(0);
});

test("workspace directory labels toggle children and directly attached documents", async ({ teacherPage }, testInfo) => {
  await teacherPage.goto("/#ai?course_id=course-physics");
  await teacherPage.getByRole("button", { name: testInfo.project.name === "mobile" ? "知识库" : "展开知识库", exact: true }).click();
  const root = teacherPage.locator('.source-panel__tree-node-header').filter({ hasText: '大学物理' });
  await expect(root).toHaveAttribute('aria-expanded', 'true');
  await root.click();
  await expect(root).toHaveAttribute('aria-expanded', 'false');
  await expect(teacherPage.locator('.source-panel__tree-node-label').filter({ hasText: '力学' })).toHaveCount(0);
  await root.press('Enter');
  await expect(root).toHaveAttribute('aria-expanded', 'true');
  const mechanics = teacherPage.locator('.source-panel__tree-node-header').filter({ hasText: '力学' });
  await mechanics.click();
  await expect(mechanics).toHaveAttribute('aria-expanded', 'true');
  await mechanics.press('Space');
  await expect(mechanics).toHaveAttribute('aria-expanded', 'false');
});
