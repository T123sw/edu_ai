import { test, expect, type Page } from 'playwright/test';
import type { PreparationTask } from '../../src/liveLearning/preparationProgress';
import { seedState } from '../../src/selfLearning/model';
import { preparationFailure } from '../../src/liveLearning/preparationProgress';

async function setup(page: Page, initial?: PreparationTask) {
  const acceptedByRequest = new Map<string, PreparationTask>();
  const state = { task: initial, disconnected: false, submitFailure: false, cancelFailure: false, dropResponse: false, enterFailure: true, release: undefined as undefined | (() => void), hold: false, requests: [] as Record<string, unknown>[], controls: [] as string[] };
  await page.addInitScript(() => {
    if (!localStorage.getItem('edu-ai-auth')) localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'test', user: { username: 'alice', role: 'student' } }));
  });
  await page.route('**/api/**', async route => {
    const request = route.request(); const path = new URL(request.url()).pathname.replace(/^\/backend/, '');
    if (!path.startsWith('/api/')) return route.continue();
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
    if (path === '/api/personal-studio') return route.fulfill({ json: { resources: [], jobs: [] } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
    if (path === '/api/course-preparations' && request.method() === 'POST') {
      state.requests.push(request.postDataJSON());
      if (state.hold) await new Promise<void>(resolve => { state.release = resolve; });
      if (state.submitFailure) return route.fulfill({ status: 503, json: { detail: '服务暂不可用，请重试' } });
      const id = String(request.postDataJSON().request_id);
      state.task = acceptedByRequest.get(id) || { preparation_id: acceptedByRequest.size ? `prep-new-${acceptedByRequest.size + 1}` : 'prep-progress', status: 'running', stage: 'research_scope', revision: 2, attempt_no: 1 };
      acceptedByRequest.set(id, state.task);
      if (state.dropResponse) return route.abort('failed');
      return route.fulfill({ status: 202, json: state.task });
    }
    if (path === '/api/course-preparations') {
      if (state.disconnected) return route.fulfill({ status: 503, json: { detail: 'temporary disconnect' } });
      return route.fulfill({ json: { preparations: state.task ? [state.task] : [] } });
    }
    if (/\/prep-progress\/(cancel|retry)$/.test(path)) {
      const action = path.split('/').at(-1)!; state.controls.push(action);
      if (action === 'cancel') {
        expect(request.postDataJSON()).toEqual({ expected_attempt_no: state.task!.attempt_no });
        if (state.cancelFailure) return route.fulfill({ status: 503, json: { detail: '取消暂未提交，请重试' } });
      }
      state.task = { ...state.task!, status: action === 'retry' ? 'running' : 'canceled', revision: state.task!.revision + 1, error_code: null };
      return route.fulfill({ json: state.task });
    }
    if (path === '/api/self-learning/courses/ready-course') return state.enterFailure
      ? route.fulfill({ status: 503, json: { detail: '课程读取测试失败' } })
      : route.fulfill({ json: { ...seedState().rooms[0], id: 'ready-course' } });
    return route.fulfill({ json: { items: [] } });
  });
  await page.goto('/');
  await expect(page.getByLabel('学习知识点与目标')).toBeVisible();
  return state;
}

async function submit(page: Page) {
  await page.getByLabel('学习知识点与目标').fill('学习快速排序的原理与应用');
  await page.getByRole('button', { name: '开始学习', exact: true }).click();
}

for (const width of [1440, 390]) {
  test(`partial course opens while failed content can be retried (${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const state = await setup(page);
    await submit(page);
    const dialog = page.getByRole('dialog', { name: '课程准备', exact: true });
    state.task = { ...state.task!, status: 'failed', stage: 'review', revision: 3,
      error_code: 'RESOURCE_REPAIR_FORMAT_INVALID', result_ref: { course_id: 'ready-course', course_ready: false,
        course_available: true, available_resources: 11, planned_resources: 12 } };
    await expect(dialog.getByRole('heading', { name: '部分内容已完成，可以先学习' })).toBeVisible();
    await expect(dialog.getByText('已交付 11 / 12 份资料。未完成的内容可单独重试，已有资料会保留。')).toBeVisible();
    await dialog.getByRole('button', { name: '补齐未完成内容' }).click();
    await expect(dialog.getByRole('heading', { name: '已有资料可以开始学习' })).toBeVisible();
    expect(state.controls).toEqual(['retry']);
    state.enterFailure = false;
    await dialog.getByRole('button', { name: '先学习已完成内容' }).click();
    await expect(page).toHaveURL(/#\/classroom\/ready-course/);
    await expect(dialog).toHaveCount(0);
  });

  test(`failure explains every cause and retained drafts in plain language (${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const state = await setup(page);
    await submit(page);
    const dialog = page.getByRole('dialog', { name: '课程准备', exact: true });
    await expect(dialog.getByRole('heading', { name: '查找与核验学习资料' })).toBeVisible();
    state.task = { ...state.task!, status: 'failed', stage: 'review', revision: 3, error_code: 'CONTEXT_BUDGET_EXCEEDED', failure: {
      title: '部分内容生成失败，课程尚未完成', reason: '本次有 8 份学习内容未完成：一次处理的内容过多、生成额度不足、部分内容仍需修正。',
      next_step: '直接重试可能仍失败；可缩小课程范围重新创建，或联系维护人员调整。',
      stage: '汇总与检查学习内容', saved_resources: 4, planned_resources: 12,
      resource_issues: Array.from({ length: 8 }, (_, i) => ({ resource_title: `快速排序知识点 ${i + 1}`,
        resource_type: i === 1 ? '习题' : 'AI 课堂', step: '制作学习内容',
        reason: preparationFailure({ error_code: i === 0 ? 'CONTEXT_BUDGET_EXCEEDED' : i === 1 ? 'RESOURCE_CONTENT_REJECTED' : 'BUDGET_EXHAUSTED' }).reason })),
    } };
    const failure = dialog.getByRole('alert');
    await expect(failure).toContainText('已保存 4 份资料草稿');
    await expect(failure).toContainText('直接重试可能仍失败');
    await failure.getByText('查看未完成的内容（8）').click();
    await expect(failure.getByRole('listitem')).toHaveCount(8);
    await expect(failure).toContainText('单次处理上限');
    await expect(failure).toContainText('前后不一致');
    await expect(failure).toContainText('生成额度');
    await expect(dialog.getByText('CONTEXT_BUDGET_EXCEEDED')).toHaveCount(0);
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.screenshot({ path: `test-results/preparation-progress/readable-failure-${width}.png` });
    await dialog.getByRole('button', { name: '关闭', exact: true }).click();
    await page.getByRole('button', { name: '后台任务', exact: true }).click();
    await page.getByRole('dialog', { name: '后台任务', exact: true }).getByRole('button', { name: /需处理/ }).click();
    await expect(page.getByRole('dialog', { name: '后台任务', exact: true })).toContainText('部分内容生成失败，课程尚未完成');
  });
}

for (const width of [1440, 390]) {
  test(`submission opens animated real stages and can reopen (${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const state = await setup(page); state.hold = true;
    await submit(page);
    const dialog = page.getByRole('dialog', { name: '课程准备', exact: true });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('heading', { name: '正在提交学习目标' })).toBeVisible();
    await expect.poll(() => Boolean(state.release)).toBe(true);
    state.release!();
    await expect(dialog.getByRole('heading', { name: '查找与核验学习资料' })).toBeVisible();
    state.task = { ...state.task!, stage: 'produce', revision: 3 };
    await expect(dialog.getByRole('heading', { name: '正在制作学习内容' })).toBeVisible();
    await expect(dialog.getByRole('progressbar')).toHaveCount(0);
    await expect(dialog.locator('[aria-current="step"]')).toContainText('制作内容');
    const bounds = await dialog.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0); expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.screenshot({ path: `test-results/preparation-progress/preview-${width}.png`, fullPage: true });
    await dialog.getByRole('button', { name: '先去浏览' }).click();
    await expect(dialog).toHaveCount(0);
    await page.getByRole('button', { name: '后台任务，1 项进行中', exact: true }).click();
    await page.getByRole('dialog', { name: '后台任务', exact: true }).getByRole('button', { name: /进行中/ }).click();
    await expect(page.getByRole('dialog', { name: '后台任务', exact: true }).getByLabel('课程准备阶段')).toHaveCount(0);
    await page.getByRole('button', { name: '查看准备进度' }).click();
    await expect(dialog.getByRole('heading', { name: '正在制作学习内容' })).toBeVisible();
    await page.reload();
    await expect(dialog.getByRole('heading', { name: '正在制作学习内容' })).toBeVisible();
    expect(state.requests).toHaveLength(1);
    expect(state.controls).toEqual([]);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole('button', { name: '后台任务，1 项进行中', exact: true })).toBeVisible();
    await expect(dialog).toHaveCount(0);
  });
}

test('failure, retry, reconnect and committed completion use actual task state', async ({ page }) => {
  const state = await setup(page); await submit(page);
  const dialog = page.getByRole('dialog', { name: '课程准备', exact: true });
  await expect(dialog.getByRole('heading', { name: '查找与核验学习资料' })).toBeVisible();
  state.disconnected = true;
  await expect(dialog.getByRole('alert')).toContainText('正在自动重连');
  await expect(dialog.getByRole('button', { name: '进入课堂' })).toHaveCount(0);
  state.disconnected = false;
  state.task = { ...state.task!, status: 'failed', error_code: 'MODEL_UNAVAILABLE', revision: 3 };
  await expect(dialog.getByRole('heading', { name: '课程暂未准备完成' })).toBeVisible();
  await expect(dialog.getByRole('alert')).toContainText('生成服务响应超时或暂时不可用');
  await expect(dialog.getByText('MODEL_UNAVAILABLE')).toHaveCount(0);
  await dialog.getByRole('button', { name: '继续重试' }).click();
  await expect(dialog.getByRole('heading', { name: '查找与核验学习资料' })).toBeVisible();
  expect(state.controls).toEqual(['retry']);
  state.task = { ...state.task!, stage: 'commit', status: 'succeeded', revision: 5, result_ref: { course_ready: false } };
  await expect(dialog.getByRole('heading', { name: '本次准备已完成' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: '进入课堂' })).toHaveCount(0);
  state.task = { ...state.task!, revision: 6, result_ref: { course_ready: true, course_id: 'ready-course' } };
  await expect(dialog.getByRole('heading', { name: '你的课程已准备好' })).toBeVisible();
  await dialog.getByRole('button', { name: '进入课堂' }).click();
  await expect(dialog.getByRole('alert')).toContainText('课程读取测试失败');
  expect(page.url()).not.toContain('#/classroom/');
  state.enterFailure = false;
  await dialog.getByRole('button', { name: '进入课堂' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page).toHaveURL(/#\/classroom\/ready-course$/);
  await expect(page.getByText('课堂未找到')).toHaveCount(0);
});

test('cancel remains usable when generation advances after opening confirmation', async ({ page }) => {
  const state = await setup(page); await submit(page);
  const dialog = page.getByRole('dialog', { name: '课程准备', exact: true });
  await dialog.getByRole('button', { name: '取消任务', exact: true }).click();
  expect(state.controls).toEqual([]);
  state.task = { ...state.task!, revision: state.task!.revision + 4 };
  await dialog.getByRole('button', { name: '确认取消' }).click();
  await expect(dialog.getByRole('heading', { name: '课程准备已取消' })).toBeVisible();
  expect(state.controls).toEqual(['cancel']);
  await expect(dialog.getByRole('button', { name: '进入课堂' })).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: '继续重试' })).toBeVisible();
});

test('failed cancellation keeps confirmation open and a second click can succeed', async ({ page }) => {
  const state = await setup(page); await submit(page);
  const dialog = page.getByRole('dialog', { name: '课程准备', exact: true });
  await dialog.getByRole('button', { name: '取消任务', exact: true }).click();
  state.cancelFailure = true;
  await dialog.getByRole('button', { name: '确认取消' }).click();
  await expect(dialog.getByText('取消暂未提交，请重试')).toBeVisible();
  await expect(dialog.getByRole('button', { name: '确认取消' })).toBeEnabled();
  state.cancelFailure = false;
  await dialog.getByRole('button', { name: '确认取消' }).click();
  await expect(dialog.getByRole('heading', { name: '课程准备已取消' })).toBeVisible();
});

test('failed submission can be closed and resubmitted with the same request identity', async ({ page }) => {
  const state = await setup(page); state.submitFailure = true;
  await submit(page);
  const dialog = page.getByRole('dialog', { name: '课程准备', exact: true });
  await expect(dialog.getByRole('alert')).toContainText('服务暂不可用');
  await dialog.getByRole('button', { name: '关闭', exact: true }).click();
  state.submitFailure = false;
  await submit(page);
  await expect(dialog.getByRole('heading', { name: '查找与核验学习资料' })).toBeVisible();
  expect(state.requests).toHaveLength(2);
  expect(state.requests[0].request_id).toBe(state.requests[1].request_id);
});

for (const status of ['succeeded', 'failed', 'canceled', 'running'] as const) {
  test(`same goal creates a new task after an accepted ${status} task, including refresh`, async ({ page }) => {
    const state = await setup(page);
    await submit(page);
    const dialog = page.getByRole('dialog', { name: '课程准备', exact: true });
    await expect(dialog.getByRole('heading', { name: '查找与核验学习资料' })).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem('preparation:pending:alice'))).toBeNull();
    state.task = { ...state.task!, status, revision: 3 };
    await page.keyboard.press('Escape');
    await page.reload();
    await expect(page.getByLabel('学习知识点与目标')).toBeVisible();
    await submit(page);
    await expect.poll(() => state.requests.length).toBe(2);
    await expect(dialog.getByRole('heading', { name: '查找与核验学习资料' })).toBeVisible();
    expect(state.requests[0].goal).toBe(state.requests[1].goal);
    expect(state.requests[0].request_id).not.toBe(state.requests[1].request_id);
    expect(state.task!.preparation_id).toBe('prep-new-2');
    expect(state.controls).toEqual([]);
  });
}

test('legacy saved successful request identity is not reused for a new submission', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('preparation:pending:alice', JSON.stringify({
      request_id: 'old-successful-request',
      serialized: JSON.stringify({ operation: 'create_course', goal: '学习快速排序的原理与应用', uploads: [], overrides: { include_classroom: true } }),
    }));
  });
  const state = await setup(page);
  await submit(page);
  await expect.poll(() => state.requests.length).toBe(1);
  expect(state.requests[0].request_id).not.toBe('old-successful-request');
  expect(state.controls).toEqual([]);
});

test('lost acceptance response survives refresh without duplicating the task, then allows a new course', async ({ page }) => {
  const state = await setup(page);
  state.dropResponse = true;
  await submit(page);
  const dialog = page.getByRole('dialog', { name: '课程准备', exact: true });
  await expect(dialog.getByRole('alert')).toBeVisible();
  const acceptedId = state.task!.preparation_id;
  await dialog.getByRole('button', { name: '关闭', exact: true }).click();
  await page.reload();
  await expect(page.getByLabel('学习知识点与目标')).toBeVisible();
  state.dropResponse = false;
  await submit(page);
  await expect(dialog.getByRole('heading', { name: '查找与核验学习资料' })).toBeVisible();
  expect(state.requests).toHaveLength(2);
  expect(state.requests[0].request_id).toBe(state.requests[1].request_id);
  expect(state.task!.preparation_id).toBe(acceptedId);
  await page.keyboard.press('Escape');
  await submit(page);
  await expect.poll(() => state.requests.length).toBe(3);
  expect(state.requests[2].request_id).not.toBe(state.requests[1].request_id);
  expect(state.task!.preparation_id).not.toBe(acceptedId);
  expect(state.controls).toEqual([]);
});

test('another account does not restore the previous account progress window', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('preparation:progress:bob', JSON.stringify({ id: 'private-bob', goal: 'private course', open: true })));
  await setup(page);
  await expect(page.getByRole('dialog', { name: '课程准备', exact: true })).toHaveCount(0);
  await expect(page.getByText('private course')).toHaveCount(0);
});

test('reduced motion disables stage animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await setup(page); await submit(page);
  await expect(page.getByRole('heading', { name: '查找与核验学习资料' })).toBeVisible();
  expect(await page.locator('.sheet-front').evaluate(el => getComputedStyle(el).animationName)).toBe('none');
});

for (const width of [1440, 390]) {
  test(`long learning request is submitted intact without the old character cap (${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const state = await setup(page);
    const input = page.getByLabel('学习知识点与目标');
    const goal = '我希望深入理解快速排序，包含分区推导、复杂度、边界条件和完整示例。'.repeat(100);
    await input.fill(goal);
    await input.press('End');
    await input.pressSequentially('END');
    await expect(input).toHaveValue(goal + 'END');
    await page.getByRole('button', { name: '开始学习', exact: true }).click();
    await expect.poll(() => state.requests.length).toBe(1);
    expect(state.requests[0].goal).toBe(goal + 'END');
    await expect(page.getByRole('dialog', { name: '课程准备', exact: true })).toBeVisible();
  });
}


for (const classroom of [true, false]) {
  test(`new nodes always request a report and quiz (classroom=${classroom})`, async ({ page }) => {
    const state = await setup(page);
    if (!classroom) await page.getByRole('switch', { name: '生成 AI 课堂' }).click();
    await submit(page);
    await expect.poll(() => state.requests.length).toBe(1);
    expect(state.requests[0].overrides).toEqual({ include_classroom: classroom, required_resource_types: ['report', 'quiz'] });
  });
}
