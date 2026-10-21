import { test, expect } from 'playwright/test';

const stem = '阅读代码，计算输出：\n\n```python\nprint(2 + 3)\n```\n\n复杂度为 $O(1)$。';
const questions = Array.from({ length: 3 }, (_, i) => ({ id: `q${i}`, stem: i ? `第 ${i + 1} 道题` : stem, options: ['5', '6'], type: 'single_choice', answer: 'A', explanation: '相加得到 5' }));
const material = { course_id: 'course', material_id: 'quiz', material_type: 'quiz', version: 1, title: '练习', questions };
const fixture = () => questions.map((q, i) => ({ check_id: `check-${i}`, question_version: 1, public_question: { form: 'choice', stem: q.stem, options: [{ id: 'a', text: '5' }, { id: 'b', text: '6' }] }, attempts: [] as object[], source_available: true, teaching: null }));
const url = '/?learningPlayer=1#ai?course_id=course&material_id=quiz&material_type=quiz&version=1&visibility=private';

test('pending records show one loader; complete cards appear once without per-question reloads', async ({ page }) => {
  const items = fixture(); let gets = 0; let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'alice', role: 'student' } })));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname; let data: unknown = {};
    if (path.endsWith('/auth/verify')) data = { valid: true, user: { username: 'alice', role: 'student' } };
    else if (path.includes('/materials/')) data = material;
    else if (path.endsWith('/mode')) data = { checks_enabled: true, owner: 'alice' };
    else if (path.endsWith('/practice/quiz/checks')) { await gate; data = { topic_id: 'topic', items }; }
    else if (path.endsWith('/check-0/attempts')) { items[0].attempts = [{ attempt_id: 'attempt-1', status: 'graded', option_ids: ['a'], text: '', correct: true, feedback: '答案正确', evaluator: 'rule' }]; data = items[0].attempts[0]; }
    else if (path.includes('/checks/check-')) { gets++; data = items[Number(path.split('-').pop())]; }
    return route.fulfill({ json: data });
  });
  await page.goto(url);
  await expect(page.getByRole('status')).toHaveText('正在加载习题…');
  await expect(page.locator('.sl-quiz-preview, [data-quiz-question]')).toHaveCount(0);
  await expect(page.getByRole('radio')).toHaveCount(0);
  await expect(page.locator('pre')).toHaveCount(0);
  await expect(page.getByText('相加得到 5', { exact: true })).toHaveCount(0);
  release();
  await expect(page.locator('[data-quiz-question]')).toHaveCount(3);
  await expect(page.locator('.quiz-loading, .sl-quiz-preview')).toHaveCount(0);
  await expect(page.locator('pre')).toContainText('print(2 + 3)');
  await expect(page.locator('.katex').first()).toBeVisible();
  for (const card of await page.locator('[data-quiz-question]').all()) await expect(card.getByRole('radio')).toHaveCount(2);
  expect(gets).toBe(0);
  const first = page.locator('[data-quiz-question="0"]');
  await first.getByRole('radio', { name: '5', exact: true }).check();
  await first.getByRole('button', { name: '提交答案' }).click();
  await expect(first.getByRole('group', { name: '已保存的作答' })).toBeVisible();
  expect(gets).toBe(1);
  await page.reload();
  await expect(first.getByRole('group', { name: '已保存的作答' }).getByRole('radio', { name: '5', exact: true })).toBeChecked();
  expect(gets).toBe(1);
});

test('failed records show a retry state without incomplete questions on narrow screens', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); let failed = true;
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'alice', role: 'student' } })));
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
    if (path.includes('/materials/')) return route.fulfill({ json: material });
    if (path.endsWith('/mode')) return route.fulfill({ json: { checks_enabled: true, owner: 'alice' } });
    if (path.endsWith('/practice/quiz/checks')) return failed ? route.fulfill({ status: 503, json: { detail: 'unavailable' } }) : route.fulfill({ json: { topic_id: 'topic', items: fixture() } });
    return route.fulfill({ json: {} });
  });
  await page.goto(url);
  await expect(page.getByRole('button', { name: '重新加载' })).toBeVisible();
  await expect(page.locator('.sl-quiz-preview, [data-quiz-question]')).toHaveCount(0);
  failed = false;
  await page.getByRole('button', { name: '重新加载' }).click();
  await expect(page.locator('[data-quiz-question]')).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('each question uses its actual type; literal code, options and saved answers keep their layout', async ({ page }) => {
  const rawCode = 'function f(a) {\n    return a < 3 ? "<br>" : 4;\n}';
  const types = ['single_choice', 'multiple_choice', 'true_false', 'short_answer'];
  const qs = types.map((type, i) => ({ id: `q${i}`, type, stem: i === 0 ? `代码题：\n\n\`\`\`\n${rawCode}\n\`\`\`\n\n公式 \\(n^2\\)` : `问题 ${i + 1}`, options: i < 2 ? ['第一项', '第二项'] : [] }));
  const checks = qs.map((q, i) => ({ check_id: `check-${i}`, question_version: 1, public_question: { form: i < 2 ? 'choice' : 'short_answer', stem: q.stem, options: q.options.map((text, n) => ({ id: `option_${n}`, text })) }, attempts: [] as object[] }));
  let submitted: { text: string; option_ids: string[] } | undefined;
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'alice', role: 'student' } })));
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname; let data: unknown = {};
    if (path.endsWith('/auth/verify')) data = { valid: true, user: { username: 'alice', role: 'student' } };
    else if (path.includes('/materials/')) data = { ...material, questions: qs };
    else if (path.endsWith('/mode')) data = { checks_enabled: true, owner: 'alice' };
    else if (path.endsWith('/practice/quiz/checks')) data = { topic_id: 'topic', items: checks };
    else if (path.endsWith('/check-2/attempts')) { submitted = route.request().postDataJSON(); checks[2].attempts = [{ attempt_id: 'saved', status: 'graded', ...submitted, correct: true, evaluator: 'rule', feedback: '判断正确。\n\n```\ntrue\n```' }]; data = checks[2].attempts[0]; }
    else if (path.endsWith('/checks/check-2')) data = checks[2];
    return route.fulfill({ json: data });
  });
  await page.goto(url);
  const cards = page.locator('[data-quiz-question]'); await expect(cards).toHaveCount(4);
  await expect(cards.nth(0).getByRole('radio')).toHaveCount(2);
  await cards.nth(0).getByRole('radio', { name: '第一项' }).check();
  await cards.nth(0).getByRole('radio', { name: '第二项' }).check();
  await expect(cards.nth(0).locator('input:checked')).toHaveCount(1);
  await expect(cards.nth(0).locator('.quiz-option-letter')).toHaveText(['A.', 'B.']);
  expect(await cards.nth(0).locator('pre > code').textContent()).toBe(rawCode + '\n');
  const style = await cards.nth(0).locator('pre').evaluate(e => ({ whiteSpace: getComputedStyle(e).whiteSpace, overflow: getComputedStyle(e).overflowX }));
  expect(style).toEqual({ whiteSpace: 'pre', overflow: 'auto' });
  await expect(cards.nth(0).locator('.katex')).toBeVisible();
  for (const input of await cards.nth(1).getByRole('checkbox').all()) await input.check();
  await expect(cards.nth(1).locator('input:checked')).toHaveCount(2);
  await expect(cards.nth(2).getByRole('textbox')).toHaveCount(0);
  await cards.nth(2).getByRole('radio', { name: '正确', exact: true }).check();
  await cards.nth(2).getByRole('button', { name: '提交答案' }).click();
  await expect(cards.nth(2).getByRole('group', { name: '已保存的作答' })).toContainText('正确');
  expect(submitted?.text).toBe('正确'); expect(submitted?.option_ids).toEqual([]);
  await expect(cards.nth(2).locator('pre code')).toHaveText('true');
  await expect(cards.nth(3).getByRole('textbox')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('legacy quiz uses the same Markdown renderer and preserves answer serialization', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'alice', role: 'student' } })));
  let answers: Record<string, string> = {};
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname; let data: unknown = {};
    if (path.endsWith('/auth/verify')) data = { valid: true, user: { username: 'alice', role: 'student' } };
    else if (path.includes('/materials/')) data = material;
    else if (path.endsWith('/mode')) data = { checks_enabled: false, owner: 'alice' };
    else if (path.endsWith('/practice/quiz')) {
      if (route.request().method() === 'POST') answers = route.request().postDataJSON().answers;
      data = { version: 1, answers, correct: 1, graded: 1, feedback: [] };
    }
    return route.fulfill({ json: data });
  });
  await page.goto(url); const first = page.locator('[data-quiz-question="0"]');
  await expect(first.locator('pre > code')).toContainText('print(2 + 3)');
  await expect(first.locator('.katex')).toBeVisible();
  await first.getByRole('radio', { name: '5', exact: true }).check();
  await page.getByRole('button', { name: '提交练习', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('已保存');
  expect(answers.q0).toBe('A');
});

test('question footer contains only submission, hint and explanation; quiz loads no player bundle', async ({ page }) => {
  const assets: string[] = [];
  page.on('request', request => { if (request.url().includes('/assets/')) assets.push(request.url()); });
  await page.addInitScript(() => {
    localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'alice', role: 'student' } }));
    window.addEventListener('message', event => {
      if (event.data?.type === 'learning-context-request') window.postMessage({ type: 'learning-context-init', channel_id: 'quiz-test', can_reference: true,
        resource_ref: { course_id: 'course', material_type: 'quiz', material_id: 'quiz', version: 1 } }, location.origin);
    });
  });
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname; let data: unknown = {};
    if (path.endsWith('/auth/verify')) data = { valid: true, user: { username: 'alice', role: 'student' } };
    else if (path.includes('/materials/')) data = material;
    else if (path.endsWith('/mode')) data = { checks_enabled: true, owner: 'alice' };
    else if (path.endsWith('/practice/quiz/checks')) data = { topic_id: 'topic', items: fixture().map(check => ({ ...check, teaching: { enabled: false, revision: 0, feedback: null } })) };
    return route.fulfill({ json: data });
  });
  await page.goto(url); const first = page.locator('[data-quiz-question="0"]');
  await expect(first.getByRole('button', { name: '提交答案', exact: true })).toBeVisible();
  await expect(first.getByRole('button', { name: '暂时跳过', exact: true })).toHaveCount(0);
  await expect(first.getByRole('button', { name: '提示', exact: true })).toBeVisible();
  await expect(first.getByRole('button', { name: '讲解', exact: true })).toBeVisible();
  await expect(first.getByRole('checkbox', { name: '作答后继续辅导', exact: true })).toHaveCount(0);
  await expect(first.locator('.quiz-help-actions button')).toHaveCount(2);
  const asked = page.evaluate(() => new Promise<{ question_prompt: string }>(resolve => window.addEventListener('message', event => { if (event.data?.type === 'learning-reading-context' && event.data.intent === 'ask') resolve(event.data); })));
  await first.getByRole('button', { name: '提示', exact: true }).click();
  expect((await asked).question_prompt).toContain('只给下一步提示');
  expect(assets.some(url => /SlidePlayer|ClassroomPlaybackSurface|MindMapCanvas/.test(url))).toBe(false);
  const style = await first.locator('.quiz-submit').evaluate(e => ({ background: getComputedStyle(e).backgroundColor, border: getComputedStyle(e).borderColor }));
  expect(style.background).toBe(style.border);
});


test('material and saved legacy answers share one loading surface until the form is ready', async ({ page }) => {
  let releaseMaterial!: () => void, releaseAnswers!: () => void;
  const materialGate = new Promise<void>(resolve => { releaseMaterial = resolve; });
  const answersGate = new Promise<void>(resolve => { releaseAnswers = resolve; });
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'alice', role: 'student' } })));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
    if (path.includes('/materials/')) { await materialGate; return route.fulfill({ json: material }); }
    if (path.endsWith('/mode')) return route.fulfill({ json: { checks_enabled: false, owner: 'alice' } });
    if (path.endsWith('/practice/quiz')) { await answersGate; return route.fulfill({ json: { version: 1, answers: { q0: 'B' }, correct: 0, graded: 1, feedback: [] } }); }
    return route.fulfill({ json: {} });
  });
  await page.goto(url);
  await expect(page.getByRole('status')).toHaveText('正在加载习题…');
  await expect(page.getByRole('radio')).toHaveCount(0);
  const before = await page.locator('.quiz-loading').boundingBox();
  const answersStarted = page.waitForRequest(request => request.url().endsWith('/practice/quiz'));
  releaseMaterial(); await answersStarted;
  await expect(page.getByRole('status')).toHaveText('正在加载习题…');
  await expect(page.locator('.sl-quiz-preview, [data-quiz-question]')).toHaveCount(0);
  expect(await page.locator('.quiz-loading').boundingBox()).toEqual(before);
  releaseAnswers();
  const first = page.locator('[data-quiz-question="0"]');
  await expect(first.getByRole('radio', { name: '6', exact: true })).toBeChecked();
  await expect(page.locator('.quiz-loading')).toHaveCount(0);
});
