import { test, expect, type Page } from 'playwright/test';

type Payload = {mode: string; requirement: string; num_questions?: number; question_types?: string[]; per_type_counts?: Record<string, number>; sources: {document_id: string; role: string}[]};

async function setup(page: Page, filenames: string[] = []) {
  const posts: Payload[] = [];
  const errors: string[] = [];
  let uploaded = 0;
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({token: 'fixture', user: {username: 'alice', role: 'student'}})));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/verify')) return route.fulfill({json: {valid: true, user: {username: 'alice', role: 'student'}}});
    if (path.endsWith('/self-learning/state')) return route.fulfill({json: {version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: []}});
    if (path.endsWith('/exam-generations/documents')) {
      const filename = filenames[uploaded++];
      return route.fulfill({status: 201, json: {document_id: `doc-${uploaded}`, filename}});
    }
    if (path.endsWith('/exam-generations') && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON() as Payload;
      posts.push(payload);
      return route.fulfill({status: 202, json: {generation_id: 'exam-1', job_id: 'job-1', status: 'queued', progress: 0, message: '正在排队', requirement: payload.requirement}});
    }
    return route.fulfill({json: {items: []}});
  });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/#/exam');
  return {posts, errors};
}

async function upload(page: Page, names: string[]) {
  await page.getByLabel('上传资料（单文件最多 30 MB）').setInputFiles(names.map(name => ({
    name, mimeType: name.endsWith('.pdf') ? 'application/pdf' : 'text/plain', buffer: Buffer.from('fixture material'),
  })));
  for (const name of names) await expect(page.getByText(name, {exact: true})).toBeVisible();
}

for (const width of [1440, 390, 320]) test(`direct generation defaults and mode prompts at ${width}px`, async ({page}) => {
  await page.setViewportSize({width, height: 900});
  const {posts, errors} = await setup(page);
  const input = page.getByRole('textbox', {name: '考试范围与目标'});
  await expect(page.getByLabel('出题方式')).toHaveValue('custom');
  await expect(input).toHaveValue('');
  await expect(input).toHaveAttribute('placeholder', /可以直接描述范围，也可上传资料/);
  await expect(page.getByRole('spinbutton', {name: '选择题', exact: true})).toHaveValue('10');
  await expect(page.getByRole('spinbutton', {name: '填空题', exact: true})).toHaveValue('5');
  await expect(page.getByRole('spinbutton', {name: '简答题', exact: true})).toHaveValue('5');
  await expect(page.getByRole('button', {name: '生成习题', exact: true})).toBeDisabled();
  await page.screenshot({path: `../.runtime/exam-defaults/prompt-custom-${width}.png`});
  await input.fill('数据结构：树与图，中等难度');
  await page.getByLabel('出题方式').selectOption('mimic');
  await expect(input).toHaveValue('');
  await expect(input).toHaveAttribute('placeholder', /第一份材料请上传参考试卷/);
  await page.screenshot({path: `../.runtime/exam-defaults/prompt-mimic-${width}.png`});
  await expect(page.getByRole('button', {name: '生成模拟试卷', exact: true})).toBeDisabled();
  await input.fill('保留原卷难度，加强综合题');
  await page.getByLabel('出题方式').selectOption('custom');
  await expect(input).toHaveValue('数据结构：树与图，中等难度');
  await expect(input).toHaveAttribute('placeholder', /可以直接描述范围，也可上传资料/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  await page.screenshot({path: `../.runtime/exam-defaults/defaults-${width}.png`});
  await page.getByRole('button', {name: '生成习题', exact: true}).click();
  await expect.poll(() => posts.length).toBe(1);
  expect(posts[0]).toMatchObject({mode: 'custom', requirement: '数据结构：树与图，中等难度', sources: [], num_questions: 20,
    question_types: ['choice', 'fill_in_blank', 'short_answer'], per_type_counts: {choice: 10, fill_in_blank: 5, short_answer: 5}});
  await expect(page.getByRole('dialog', {name: '试卷准备'}).locator('.art-produce')).toBeVisible();
  expect(errors).toEqual([]);
});

test('learning materials including PDFs use custom quotas without typing', async ({page}) => {
  const {posts} = await setup(page, ['notes.txt', 'chapter.pdf']);
  await upload(page, ['notes.txt', 'chapter.pdf']);
  await page.getByRole('button', {name: '生成习题', exact: true}).click();
  await expect.poll(() => posts.length).toBe(1);
  expect(posts[0]).toMatchObject({mode: 'custom', num_questions: 20, per_type_counts: {choice: 10, fill_in_blank: 5, short_answer: 5},
    sources: [{document_id: 'doc-1', role: 'context'}, {document_id: 'doc-2', role: 'context'}]});
  expect(posts[0].requirement).toContain('上传的学习资料');
});

test('mimic always uses the first remaining material and leaves quotas to the reference', async ({page}) => {
  const {posts} = await setup(page, ['notes.txt', 'paper.pdf', 'extra.pdf']);
  await upload(page, ['notes.txt', 'paper.pdf', 'extra.pdf']);
  await page.getByLabel('出题方式').selectOption('mimic');
  const create = page.getByRole('button', {name: '生成模拟试卷', exact: true});
  await expect(create).toBeDisabled();
  await expect(page.getByRole('alert')).toContainText('第一份材料须为参考试卷 PDF');
  await page.getByRole('button', {name: '移除 notes.txt', exact: true}).click();
  await expect(page.locator('.exam-files li').first()).toContainText('paper.pdf');
  await expect(page.locator('.exam-files li').first()).toContainText('参考试卷');
  await expect(page.locator('.exam-files li').nth(1)).toContainText('补充资料');
  await expect(create).toBeEnabled();
  await create.click();
  await expect.poll(() => posts.length).toBe(1);
  expect(posts[0]).toMatchObject({mode: 'mimic', sources: [{document_id: 'doc-2', role: 'template'}, {document_id: 'doc-3', role: 'context'}]});
  expect(posts[0].num_questions).toBeUndefined();
  expect(posts[0].per_type_counts).toBeUndefined();
});

test('editable quotas enforce valid totals and omit zero-count types', async ({page}) => {
  const {posts} = await setup(page);
  await page.getByRole('textbox', {name: '考试范围与目标'}).fill('Python 循环');
  const create = page.getByRole('button', {name: '生成习题', exact: true});
  await page.getByRole('spinbutton', {name: '选择题', exact: true}).fill('100');
  await expect(create).toBeDisabled();
  await page.getByRole('spinbutton', {name: '选择题', exact: true}).fill('0');
  await page.getByRole('spinbutton', {name: '填空题', exact: true}).fill('0');
  await page.getByRole('spinbutton', {name: '简答题', exact: true}).fill('0');
  await expect(create).toBeDisabled();
  await page.getByRole('spinbutton', {name: '简答题', exact: true}).fill('2.5');
  await expect(create).toBeDisabled();
  await page.getByRole('spinbutton', {name: '简答题', exact: true}).fill('2');
  await create.click();
  await expect.poll(() => posts.length).toBe(1);
  expect(posts[0]).toMatchObject({num_questions: 2, question_types: ['short_answer'], per_type_counts: {short_answer: 2}});
});
