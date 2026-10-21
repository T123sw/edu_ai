import { test, expect } from 'playwright/test';

const url = '/?learningPlayer=1#ai?course_id=course&material_id=quiz&material_type=quiz&version=1';
const user = { username: 'alice', role: 'student' };
const questions = [
  { id: 'q0', type: 'single_choice', stem: '快速排序采用哪一种思想？', options: ['分治', '贪心'], answer: 'A' },
  { id: 'q1', type: 'short_answer', stem: '为什么快速排序通常不需要额外的合并步骤？', answer: '划分后两侧已经满足大小关系。' },
];
const material = { course_id: 'course', material_id: 'quiz', material_type: 'quiz', version: 1, title: '快速排序 · 巩固练习', questions };

for (const width of [1440, 390]) {
  test(`simplified quiz restores skipped questions, grades answers and preserves references at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.addInitScript(user => {
      localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user }));
      window.addEventListener('message', event => {
        if (event.data?.type === 'learning-context-request') window.postMessage({ type: 'learning-context-init', channel_id: 'quiz-test', can_reference: true,
          resource_ref: { course_id: 'course', material_type: 'quiz', material_id: 'quiz', version: 1 } }, location.origin);
      });
    }, user);
    type Attempt = { attempt_id: string; status: string; option_ids: string[]; text: string; correct: boolean | null; feedback: string; evaluator: string | null };
    const items = questions.map((q, i) => ({ check_id: `check-${i}`, question_version: 1, source_available: true,
      public_question: { form: i ? 'short_answer' : 'choice', stem: q.stem, options: (q.options || []).map((text, n) => ({ id: n ? 'b' : 'a', text })) },
      teaching: { enabled: !i, revision: 3, feedback: null },
      attempts: (i ? [] : [{ attempt_id: 'old-skip', status: 'skipped', option_ids: [], text: '', correct: null, feedback: '', evaluator: null }]) as Attempt[],
    }));
    const operations: string[] = [];
    await page.route('**/api/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user } });
      if (path.includes('/materials/')) return route.fulfill({ json: material });
      if (path.endsWith('/mode')) return route.fulfill({ json: { checks_enabled: true, owner: 'alice' } });
      if (path.endsWith('/practice/quiz/checks')) return route.fulfill({ json: { topic_id: 'topic', items } });
      const index = Number(path.match(/check-(\d)/)?.[1]);
      const item = items[index];
      if (item && path.endsWith('/teaching')) {
        operations.push('disable-auto');
        expect(route.request().postDataJSON()).toEqual({ enabled: false, expected_revision: 3 });
        item.teaching.enabled = false; item.teaching.revision++;
        return route.fulfill({ json: item.teaching });
      }
      if (item && path.endsWith('/attempts')) {
        const body = route.request().postDataJSON();
        expect(body.skipped).toBe(false);
        expect(item.teaching.enabled).toBe(false);
        operations.push(`submit-${index}`);
        item.attempts = [{ attempt_id: `attempt-${index}`, status: index ? 'evaluation_failed' : 'graded', option_ids: body.option_ids, text: body.text,
          correct: index ? null : true, feedback: index ? '答案已保存，评价暂不可用，可稍后重试。' : '分治将问题拆成较小的子问题，递归处理。', evaluator: index ? null : 'deterministic' }];
        return route.fulfill({ json: item.attempts[0] });
      }
      if (item && path.endsWith('/evaluate')) {
        item.attempts[0] = { ...item.attempts[0], status: 'graded', correct: true, evaluator: 'model', feedback: '已说明划分建立的大小关系，关键要点符合。' };
        return route.fulfill({ json: item.attempts[0] });
      }
      return route.fulfill({ json: item || {} });
    });
    await page.goto(url);
    const first = page.locator('[data-quiz-question="0"]'), second = page.locator('[data-quiz-question="1"]');
    await expect(first.getByRole('radio')).toHaveCount(2);
    for (const text of ['暂时跳过', '再试一次', '作答后继续辅导', '问这题', '给我提示', '解释我的答案', '完整解析']) await expect(page.getByText(text, { exact: true })).toHaveCount(0);
    await expect(first.locator('.quiz-help-actions button')).toHaveText(['提示', '讲解']);
    await first.getByRole('radio', { name: '分治', exact: true }).check();
    await first.getByRole('button', { name: '提交答案' }).click();
    await expect(first.getByText('回答正确', { exact: true })).toBeVisible();
    expect(operations).toEqual(['disable-auto', 'submit-0']);
    await expect(first.getByRole('button', { name: '提交答案' })).toHaveCount(0);
    const reference = page.evaluate(() => new Promise<{ practice: { attempt_id: string }; question_prompt: string }>(resolve => window.addEventListener('message', event => {
      if (event.data?.type === 'learning-reading-context' && event.data.intent === 'ask') resolve(event.data);
    })));
    await first.getByRole('button', { name: '讲解', exact: true }).click();
    const savedContext = await reference;
    expect(savedContext.practice.attempt_id).toBe('attempt-0');
    expect(savedContext.question_prompt).toContain('我这次已提交的答案');
    await second.getByRole('textbox').fill('划分后，左侧都不大于基准值，右侧都不小于它，所以排序后直接拼接即可。');
    await second.getByRole('button', { name: '提交答案' }).click();
    await expect(second.getByRole('group', { name: '已保存的作答' })).toContainText('直接拼接即可');
    await expect(second.getByText('回答有误', { exact: true })).toHaveCount(0);
    await second.getByRole('button', { name: '重新评价' }).click();
    await expect(second.getByText('AI 参考评价', { exact: true })).toBeVisible();
    await expect(second.getByText('要点符合', { exact: true })).toBeVisible();
    await expect(page.getByText('客观批改 · 建议回顾本题', { exact: true })).toHaveCount(0);
    await page.reload();
    await expect(first.getByRole('group', { name: '已保存的作答' }).getByRole('radio', { name: '分治', exact: true })).toBeChecked();
    await expect(second.getByRole('group', { name: '已保存的作答' })).toContainText('直接拼接即可');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (process.env.QUIZ_SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.QUIZ_SCREENSHOT_DIR}/quiz-${width}.png`, fullPage: true });
  });
}
