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

test("knowledge graph reveals one level at a time", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=structure", { waitUntil: "domcontentloaded" });

  await expect(teacherPage.locator(".knowledge-map__node")).toHaveCount(3);
  await expect(teacherPage.getByText("运动学", { exact: true })).toHaveCount(0);

  await teacherPage.getByRole("button", { name: "展开力学" }).click();
  await expect(teacherPage.getByText("运动学", { exact: true })).toBeVisible();
  await expect(teacherPage.getByText("速度与加速度", { exact: true })).toHaveCount(0);

  await teacherPage.getByRole("button", { name: "收起力学" }).click();
  await expect(teacherPage.getByText("运动学", { exact: true })).toHaveCount(0);
});

test("course knowledge directory uses the same collapsed tree behavior", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=documents", { waitUntil: "domcontentloaded" });

  const directoryWidth = await teacherPage.locator(".knowledge-library__nodes").evaluate((element) => element.getBoundingClientRect().width);
  expect(directoryWidth).toBeGreaterThanOrEqual(360);
  await expect(teacherPage.locator(".knowledge-library__node-select")).toHaveCount(3);
  await expect(teacherPage.getByText("运动学", { exact: true })).toHaveCount(0);

  await teacherPage.getByRole("button", { name: "展开力学" }).click();
  await expect(teacherPage.getByText("运动学", { exact: true })).toBeVisible();
  await expect(teacherPage.getByText("速度与加速度", { exact: true })).toHaveCount(0);
});
