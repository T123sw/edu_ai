import { test, expect } from "playwright/test";

for (const entry of ["review", "old-preview"] as string[]) test(`original workbench and resource flow from ${entry}`, async ({ page }, info) => {
  test.setTimeout(75000);
  const signedIn = entry.startsWith("signed-in");
  const role = entry === "signed-in-student" ? "student" : "teacher";
  const auth = signedIn ? JSON.stringify({ token: "fixture-token", user: { username: "T", role } }) : "real-session-must-stay-unchanged";
  const requests: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/api/**", route => {
    if (signedIn && new URL(route.request().url()).pathname.endsWith("/api/auth/verify")) return route.fulfill({ json: { valid: true, user: { username: "T", role } } });
    if (/^\/(backend\/)?api\//.test(new URL(route.request().url()).pathname)) {
      requests.push(route.request().url()); return route.abort();
    }
    return route.continue();
  });
  await page.addInitScript(value => {
    if (!localStorage.getItem("edu-ai-auth")) localStorage.setItem("edu-ai-auth", value);
  }, auth);
  await page.goto(entry === "review" ? "/?review=1" : entry === "old-preview" ? "/?preview=student" : "/");
  await page.locator(".sl-class-card").filter({ hasText: "从零开始，理解 Agent" }).click();
  const navigation = page.getByRole("navigation", { name: "主导航" });
  await expect(navigation.getByRole("link")).toHaveText(["AI 课堂", "科研实践", "工作台", "资源中心"]);
  await page.screenshot({ path: info.outputPath("classroom-review.png") });
  if (entry === "signed-in-teacher") {
    // The user's existing bookmarked URL used to render the simplified Studio.
    await page.goto("/#/studio?classroom=sample-agent");
  } else await navigation.getByRole("link", { name: "工作台", exact: true }).click();
  await expect(page.locator(".ai-studio-page")).toBeVisible({ timeout: 25000 });
  await expect(page.locator(".review-reference")).toHaveCount(0);
  expect(page.url()).not.toContain("reference=");
  const switcher = page.getByRole("button", { name: "生成工厂", exact: true });
  if (await switcher.isVisible()) await switcher.click();
  const collapsed = page.getByRole("button", { name: "打开生成工厂", exact: true });
  if (await collapsed.isVisible()) await collapsed.click();
  await page.getByRole("button", { name: "教学报告", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("textbox").fill("生成一份 Agent 工具调用补充报告");
  await dialog.getByRole("button", { name: /交给|生成|发送/ }).click();
  await expect(page.getByRole("status")).toContainText("示例资源已准备好", { timeout: 10000 });
  await page.screenshot({ path: info.outputPath("workbench-review.png") });
  await navigation.getByRole("link", { name: "资源中心", exact: true }).click();
  await expect(page.getByRole("tab", { name: /课程资料/ })).toHaveCount(0);
  await expect(page.locator(".sl-library-item").filter({ hasText: "Agent 基础概念 · 讲解" })).toHaveCount(0);
  await page.locator(".sl-library-item").filter({ hasText: "Agent 工具调用补充报告" }).click();
  await expect(page.getByRole("region", { name: "资源预览" })).toContainText("Agent 工具调用补充报告");
  await expect(page.getByRole("link", { name: "引用到工作台", exact: true })).toHaveAttribute("href", /scopeType=knowledge_point.*reference=/);
  await page.getByRole("button", { name: "置顶资源", exact: true }).click();
  await expect(page.getByRole("button", { name: "取消置顶", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "重命名", exact: true }).click();
  await page.getByRole("textbox", { name: "资源名称" }).fill("Agent 工具调用 · 我的补充报告");
  await page.getByRole("button", { name: "保存名称", exact: true }).click();
  await page.screenshot({ path: info.outputPath("resources-review.png") });
  await page.getByRole("button", { name: "加入本节学习", exact: true }).click();
  await page.getByRole("button", { name: "确认加入", exact: true }).click();
  await expect(page.getByText("已在学习目录中", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "在课堂学习" }).click();
  await expect(page.locator(".sl-reader")).toContainText("Agent 工具调用 · 我的补充报告");
  await expect(page.locator(".sl-reader")).toContainText("选择一个小案例，用自己的话解释，并加入本节学习。");
  await page.reload();
  await expect(page.locator(".sl-reader")).toContainText("Agent 工具调用 · 我的补充报告");
  const classroomUrl = page.url();
  await navigation.getByRole("link", { name: "资源中心", exact: true }).click();
  await page.getByRole("textbox", { name: "搜索资源" }).fill("不存在的资源名称");
  await expect(page.getByText("没有匹配的资源，试试其他筛选条件。")).toBeVisible();
  await page.getByRole("textbox", { name: "搜索资源" }).fill("我的补充报告");
  await page.locator(".sl-library-item").filter({ hasText: "我的补充报告" }).click();
  await page.getByRole("button", { name: "删除资源", exact: true }).click();
  await page.getByRole("button", { name: "确认删除", exact: true }).click();
  await expect(page.locator(".sl-library-item").filter({ hasText: "我的补充报告" })).toHaveCount(0);
  await page.goto(classroomUrl);
  await expect(page.locator(".sl-reader")).toContainText("Agent 工具调用 · 我的补充报告");
  expect(await page.evaluate(() => localStorage.getItem("edu-ai-auth"))).toBe(auth);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(requests).toEqual([]);
  expect(errors).toEqual([]);
});
