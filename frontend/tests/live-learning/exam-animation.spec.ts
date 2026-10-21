import { test, expect, type Page } from 'playwright/test';

type Task = {generation_id: string; job_id: string; status: string; progress: number; message: string; requirement: string; title?: string};

async function setup(page: Page, initial: Task[] = []) {
  let items: Task[] = initial;
  let rejectCreate = false;
  let rejectPoll = false;
  let retryPending = false;
  let posts = 0;
  const base: Task = {generation_id: 'exam-1', job_id: 'job-1', status: 'queued', progress: 0, message: '正在排队', requirement: '保持原卷题型、题数和考点，生成一套新的模拟试卷。'};
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({token: 'fixture', user: {username: 'alice', role: 'student'}})));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/verify')) return route.fulfill({json: {valid: true, user: {username: 'alice', role: 'student'}}});
    if (path.endsWith('/self-learning/state')) return route.fulfill({json: {version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: []}});
    if (path.endsWith('/exam-generations/documents')) return route.fulfill({status: 201, json: {document_id: 'doc-1', filename: 'sample.pdf'}});
    if (path.endsWith('/exam-generations')) {
      if (route.request().method() === 'POST') {
        posts++;
        if (rejectCreate) return route.fulfill({status: 503, json: {detail: '提交失败，请稍后重试'}});
        items = [{...base}];
        return route.fulfill({status: 202, json: base});
      }
      if (rejectPoll) return route.fulfill({status: 503, json: {detail: '暂时断线'}});
      return route.fulfill({json: {items}});
    }
    if (path.endsWith('/jobs/job-1/retry')) {
      retryPending = true;
      return route.fulfill({status: 202, json: {edu_job_id: 'job-2', status: 'queued', progress: 0, message: '正在排队'}});
    }
    if (path.endsWith('/paper')) return route.fulfill({json: {questions: [{question_id: 'q1', question_type: 'short_answer', question: '新的试卷题目', children: []}]}});
    if (path.endsWith('/practice')) return route.fulfill({json: {generation_id:'exam-1',title:'新的试卷题目',version:'v1',questions:[],answer_count:0}});
    if (path.endsWith('/practice-runs') && route.request().method()==='POST') return route.fulfill({json:{id:'run-1',paper_id:'exam-1',version:'v1',status:'active',created_at:1,total:0,drafts:{},answers:{}}});
    return route.fulfill({json: {items: []}});
  });
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/#/exam');
  await page.getByLabel('出题方式').selectOption('mimic');
  await page.getByLabel('上传资料（单文件最多 30 MB）').setInputFiles({name: 'sample.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF fixture')});
  await expect(page.getByText('sample.pdf', {exact: true})).toBeVisible();
  return {
    update(change: Partial<Task>) { items = [{...base, ...change}]; },
    replace(next: Task[]) {items = next;},
    rejectCreate() {rejectCreate = true;},
    pollError(value: boolean) {rejectPoll = value;},
    get retryPending() {return retryPending;},
    get posts() {return posts;},
    errors,
  };
}

for (const width of [1440, 390, 320]) test(`exam animation lifecycle at ${width}px`, async ({page}) => {
  await page.setViewportSize({width, height: 900});
  const state = await setup(page);
  await page.getByRole('button', {name: '生成模拟试卷', exact: true}).click();
  const dialog = page.getByRole('dialog', {name: '试卷准备'});
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('.sl-prep-art.art-produce')).toBeVisible();
  state.update({status: 'running', progress: 67, message: '已处理 2/4 题，正在生成第 3 题'});
  await expect(dialog.getByRole('status')).toContainText('2/4');
  await expect(dialog.getByRole('progressbar')).toHaveAttribute('value', '67');
  if (width === 1440) {
    await page.emulateMedia({reducedMotion: 'no-preference'});
    await expect(dialog.locator('.sheet-front')).toHaveCSS('animation-name', 'prep-float');
    await page.emulateMedia({reducedMotion: 'reduce'});
    await expect(dialog.locator('.sheet-front')).toHaveCSS('animation-name', 'none');
  }
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 2)).toBe(true);
  await page.screenshot({path: `../.runtime/exam-generation-animation/animation-${width}.png`});
  await dialog.getByRole('button', {name: '先去浏览'}).click();
  await expect(dialog).toHaveCount(0);
  expect(state.posts).toBe(1);
  await page.getByRole('button', {name: '查看进度'}).click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await page.reload();
  await page.getByRole('button', {name: '查看进度'}).click();
  await expect(dialog.getByRole('status')).toContainText('2/4');
  state.update({status: 'succeeded', progress: 100, message: '试卷已生成'});
  await expect(dialog.locator('.art-done')).toBeVisible();
  await dialog.getByRole('button', {name: '查看试卷'}).click();
  await expect(dialog).toHaveCount(0);
  await expect(page).toHaveURL(/#\/exam\/exam-1$/);
  await expect(page.getByRole('heading',{name:'新的试卷题目'})).toBeVisible();
  expect(state.errors).toEqual([]);
});

test('failed retry tracks replacement job and reconnects without false completion', async ({page}) => {
  const state = await setup(page);
  await page.getByRole('button', {name: '生成模拟试卷', exact: true}).click();
  const dialog = page.getByRole('dialog', {name: '试卷准备'});
  state.update({status: 'failed', message: '结构不完整'});
  await expect(dialog.locator('.art-stopped')).toBeVisible();
  const papers = page.getByRole('region', {name: '我的试卷'});
  await expect(papers.locator('.exam-task')).toHaveCount(0);
  await expect(papers.getByRole('heading')).toHaveText('我的试卷 0');
  await expect(dialog).toContainText('本次任务不会保留在“我的试卷”中');
  await dialog.getByRole('button', {name: '重试生成'}).click();
  await expect.poll(() => state.retryPending).toBe(true);
  // Retry creates the new generation only when a worker claims it.
  await expect(dialog.getByRole('status')).toContainText('正在等待生成');
  state.update({generation_id: 'exam-2', job_id: 'job-2', status: 'running', progress: 81, message: '已处理 3/4 题，正在生成第 4 题'});
  await expect(dialog.getByRole('status')).toContainText('3/4');
  state.pollError(true);
  await expect(dialog.getByRole('alert')).toContainText('正在重新连接');
  await expect(dialog.locator('.art-done')).toHaveCount(0);
  state.pollError(false);
  state.replace([
    {generation_id: 'exam-1', job_id: 'job-1', status: 'failed', progress: 100, message: '结构不完整', requirement: '旧失败任务'},
    {generation_id: 'exam-2', job_id: 'job-2', status: 'succeeded', progress: 100, message: '试卷已生成', requirement: '重试成功试卷'},
  ]);
  await expect(dialog.locator('.art-done')).toBeVisible();
  await expect(dialog.getByRole('alert')).toHaveCount(0);
  await dialog.getByRole('button', {name: '关闭', exact: true}).click();
  await expect(papers.locator('.exam-task')).toHaveCount(1);
  await expect(papers).toContainText('重试成功试卷');
  await expect(papers).not.toContainText('旧失败任务');
  await page.reload();
  await expect(papers.locator('.exam-task')).toHaveCount(1);
  await expect(papers).not.toContainText('旧失败任务');
  expect(state.errors).toEqual([]);
});

const storedTask = (id: string, status: string, requirement: string): Task => ({
  generation_id: id, job_id: `job-${id}`, status, requirement, progress: 100, message: '',
});

test('failed and canceled history does not affect paper count, search or expansion', async ({page}) => {
  const items = [
    ...Array.from({length: 5}, (_, n) => storedTask(`failed-${n}`, 'failed', `历史失败${n}`)),
    storedTask('canceled', 'canceled', '取消的试卷'),
    storedTask('python', 'succeeded', 'python基础联系'),
  ];
  const state = await setup(page, items);
  const papers = page.getByRole('region', {name: '我的试卷'});
  await expect(papers.locator('.exam-task')).toHaveCount(1);
  await expect(papers.getByRole('heading', {level: 2})).toHaveText('我的试卷 1');
  await expect(papers).toContainText('python基础联系');
  await expect(papers.getByRole('button', {name: '查看全部'})).toHaveCount(0);
  await papers.getByRole('button', {name: '搜索试卷', exact: true}).click();
  await papers.getByRole('textbox', {name: '搜索试卷', exact: true}).fill('历史失败');
  await expect(papers.locator('.exam-task')).toHaveCount(0);
  await expect(papers).toContainText('没有找到相关试卷');
  await page.reload();
  await expect(papers.locator('.exam-task')).toHaveCount(1);
  await expect(papers).not.toContainText('历史失败');
  expect(state.errors).toEqual([]);
});

test('background failure removes the pending card and stays absent after refresh', async ({page}) => {
  const state = await setup(page, [storedTask('exam-1', 'running', '正在生成的试卷')]);
  const papers = page.getByRole('region', {name: '我的试卷'});
  await expect(papers.getByRole('button', {name: '查看进度'})).toBeVisible();
  state.update({status: 'failed', message: '生成失败'});
  await expect(papers.locator('.exam-task')).toHaveCount(0);
  await expect(papers.getByRole('heading')).toHaveText('我的试卷 0');
  await expect(papers).toContainText('还没有试卷');
  await page.reload();
  await expect(papers).toContainText('还没有试卷');
  await expect(papers.locator('.exam-task')).toHaveCount(0);
  expect(state.errors).toEqual([]);
});

test('source-based title is searchable and consistent in the list and progress dialog', async ({page}) => {
  const title = '数据结构期末 · 模拟试卷';
  const task = {...storedTask('exam-1', 'running', '保持原卷题型、题数和考点，生成一套新的模拟试卷。'), job_id: 'job-1', title};
  const state = await setup(page, [task]);
  const papers = page.getByRole('region', {name: '我的试卷'});
  await expect(papers.getByRole('heading', {name: title, exact: true})).toBeVisible();
  await papers.getByRole('button', {name: '搜索试卷', exact: true}).click();
  await papers.getByRole('textbox', {name: '搜索试卷', exact: true}).fill('数据结构期末');
  await expect(papers.locator('.exam-task')).toHaveCount(1);
  await papers.getByRole('button', {name: '查看进度'}).click();
  const dialog = page.getByRole('dialog', {name: '试卷准备'});
  await expect(dialog.locator('.sl-prep-goal')).toHaveText(title);
  state.replace([{...task, status: 'succeeded'}]);
  await expect(dialog.locator('.art-done')).toBeVisible();
  await dialog.getByRole('button', {name: '关闭', exact: true}).click();
  await expect(papers).toContainText(title);
  await expect(papers).not.toContainText(task.requirement);
  await page.reload();
  await expect(papers).toContainText(title);
  expect(state.errors).toEqual([]);
});

test('submission errors stop the animation', async ({page}) => {
  const state = await setup(page);
  state.rejectCreate();
  await page.getByRole('button', {name: '生成模拟试卷', exact: true}).click();
  const dialog = page.getByRole('dialog', {name: '试卷准备'});
  await expect(dialog.locator('.art-stopped')).toBeVisible();
  await expect(dialog.getByRole('status')).toContainText('提交失败');
  await expect(dialog.getByRole('button', {name: '查看试卷'})).toHaveCount(0);
  expect(state.errors).toEqual([]);
});
