import { test, expect, type Page } from 'playwright/test';
import { seedState } from '../../src/selfLearning/model';

async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}

test('learning space connects course context to a persistent personal research draft', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/?preview=student');
  await expect(page.getByRole('navigation', { name: '学习空间导航' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /学有所思/ })).toBeVisible();
  await noOverflow(page);
  await page.screenshot({ path: info.outputPath('learning-space.png'), fullPage: true });
  await page.getByRole('region', { name: '继续上次学习' }).getByRole('button', { name: '继续学习' }).click();
  await expect(page.locator('.sl-reader')).toBeVisible();
  await noOverflow(page);
  const before = page.url();
  await page.getByRole('link', { name: '以本节发起实践' }).click();
  await expect(page).toHaveURL(/#\/research\?classroom=/);
  await expect(page.locator('.sl-research-source')).toContainText('来自课程');
  await page.getByRole('textbox', { name: '项目名称', exact: true }).fill('工具调用的对照实验');
  await page.getByRole('textbox', { name: '我想研究的问题' }).fill('增加工具是否一定提高任务完成率？');
  await page.getByRole('textbox', { name: /希望得到的成果/ }).fill('一组实验和结论');
  await page.getByRole('button', { name: '保存项目草稿' }).click();
  await expect(page).toHaveURL(/#\/research\?draft=/);
  const draftUrl = page.url();
  await page.reload();
  await expect(page.getByRole('textbox', { name: '项目名称', exact: true })).toHaveValue('工具调用的对照实验');
  await expect(page.getByRole('textbox', { name: '我想研究的问题' })).toHaveValue('增加工具是否一定提高任务完成率？');
  await expect(page.getByText('实验与导师功能筹备中')).toBeVisible();
  await noOverflow(page);
  await page.screenshot({ path: info.outputPath('research-draft.png'), fullPage: true });
  await page.getByRole('link', { name: '回到来源资料' }).click();
  await expect(page).toHaveURL(new RegExp(before.split('#')[1].split('?')[0]));
  await expect(page.locator('.sl-reader')).toBeVisible();
  await page.goto(draftUrl.replace('preview=student', 'preview=teacher'));
  await expect(page.getByRole('alert')).toContainText('不在当前账号');
  await expect(page.getByRole('button', { name: '保存项目草稿' })).toBeDisabled();
  await page.goto(draftUrl);
  await page.getByRole('button', { name: '删除草稿', exact: true }).click();
  await page.getByRole('button', { name: '确认删除' }).click();
  await expect(page.getByRole('complementary', { name: '我的实践草稿' })).not.toContainText('工具调用的对照实验');
  expect(errors).toEqual([]);
});

test('reserved interview entry and unavailable research sources are honest and recoverable', async ({ page }, info) => {
  await page.goto('/?review=1#/interview');
  await expect(page.getByText('独立产品 · 筹备中', { exact: true })).toBeVisible();
  await expect(page.getByText('面试 Agent 将独立提供服务')).toBeVisible();
  await expect(page.getByRole('button', { name: /开始面试/ })).toHaveCount(0);
  await noOverflow(page);
  await page.screenshot({ path: info.outputPath('interview-entry.png'), fullPage: true });
  await page.goto('/?review=1#/research?classroom=unavailable&resource=unavailable');
  await expect(page.getByRole('alert')).toContainText('来源课程或资料不可用');
  await expect(page.getByRole('button', { name: '保存项目草稿' })).toBeDisabled();
  await page.getByRole('link', { name: '新建独立草稿' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('.sl-research-source')).toContainText('独立探索');
});

test('storage failure keeps draft input and never reports a successful save', async ({ page }) => {
  await page.goto('/?preview=student#/research');
  await page.getByRole('textbox', { name: '项目名称', exact: true }).fill('需要保留的研究想法');
  await page.getByRole('textbox', { name: '我想研究的问题' }).fill('我想验证一个假设');
  await page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function(key, value) {
      if (key.startsWith('edu-ai:research-drafts:')) throw new DOMException('Full', 'QuotaExceededError');
      original.call(this, key, value);
    };
  });
  await page.getByRole('button', { name: '保存项目草稿' }).click();
  await expect(page.getByRole('alert')).toContainText('草稿未保存');
  await expect(page.getByRole('textbox', { name: '项目名称', exact: true })).toHaveValue('需要保留的研究想法');
  await expect(page.getByRole('status')).not.toContainText('已保存');
});

test('authenticated frontend preserves course submission and exposes the same module routes', async ({ page }, info) => {
  const state = { ...seedState(), shared: [], serverJobs: [] };
  const requests: { goal: string; overrides: { include_classroom: boolean } }[] = [];
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'space-fixture', user: { username: 'space-user', role: 'student' } })));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'space-user', role: 'student' } } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: state });
    if (path.endsWith('/course-preparations') && route.request().method() === 'POST') {
      requests.push(route.request().postDataJSON());
      return route.fulfill({ json: { preparation_id: 'accepted', status: 'queued' } });
    }
    if (path.endsWith('/course-preparations')) return route.fulfill({ json: { preparations: [] } });
    return route.fulfill({ json: { items: [] } });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /学有所思/ })).toBeVisible();
  const inputBounds = await page.getByRole('textbox', { name: '学习知识点与目标' }).boundingBox();
  const optionsBounds = await page.getByRole('switch', { name: '生成 AI 课堂' }).boundingBox();
  const submitBounds = await page.getByRole('button', { name: '开始学习', exact: true }).boundingBox();
  expect(optionsBounds!.y).toBeGreaterThanOrEqual(inputBounds!.y + inputBounds!.height);
  expect(submitBounds!.y).toBeGreaterThanOrEqual(optionsBounds!.y + optionsBounds!.height);
  await noOverflow(page);
  await page.screenshot({ path: info.outputPath('authenticated-home.png'), fullPage: true });
  await page.getByRole('textbox', { name: '学习知识点与目标' }).fill('根据资料学习操作系统');
  await page.getByRole('button', { name: '开始学习', exact: true }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0]).toMatchObject({ goal: '根据资料学习操作系统', overrides: { include_classroom: true } });
  await page.getByRole('navigation', { name: '学习空间导航' }).getByRole('link', { name: '科研实践', exact: true }).click();
  await expect(page.getByRole('region', { name: '实践项目草稿' })).toBeVisible();
  await noOverflow(page);
  await page.getByRole('navigation', { name: '学习空间导航' }).getByRole('link', { name: /面试 Agent/ }).click();
  await expect(page.getByText('面试 Agent 将独立提供服务')).toBeVisible();
  await noOverflow(page);
});
