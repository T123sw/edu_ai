import { expect, test } from './fixtures/teacherApp';

test.beforeEach(async ({ teacherPage: page }) => {
  await page.route('**/api/courses/course-physics/classrooms?*', route => route.fulfill({ json: [] }));
});

test('shared overview, visible classroom review and teacher practice', async ({ teacherPage: page }) => {
  await page.goto('/#classroom-studio?course_id=course-physics');
  await expect(page.locator('.curriculum-overview-hero')).toBeVisible({ timeout: 20000 });
  await expect(page.locator('.curriculum-resource-card')).toHaveCount(0);
  await page.screenshot({ path: 'test-results/classroom-overview.png' });
  const tree = page.getByRole('tree', { name: '课程目录' });
  await tree.getByRole('treeitem', { name: /1\.1 力与运动/ }).getByRole('button').click();
  await expect(page.locator('.curriculum-overview-hero')).toContainText('1.1 力与运动');
  await expect(page.locator('.curriculum-resource-card')).toHaveCount(0);
  await page.screenshot({ path: 'test-results/classroom-node.png' });
  await tree.getByRole('treeitem', { name: /力学互动课堂/ }).getByRole('button').click();
  const publish = page.getByRole('button', { name: '批准并发布' });
  await expect(publish).toBeInViewport();
  await expect(page.getByText(/正在围绕/)).toHaveCount(0);
  await page.screenshot({ path: 'test-results/classroom-review.png' });
  await tree.getByRole('treeitem', { name: /力学巩固练习/ }).getByRole('button').click();
  await page.getByRole('textbox', { name: '第 1 题答案' }).fill('静止或匀速直线运动');
  await page.getByRole('button', { name: '提交试答' }).click();
  await expect(page.getByText('试答已完成，可对照参考答案检查题目质量。')).toBeVisible();
  await page.screenshot({ path: 'test-results/classroom-practice.png' });
});

test('subtitles follow individual sentences through playback and replay', async ({ teacherPage: page }) => {
  await page.addInitScript(() => {
    window.speechSynthesis.getVoices = () => [];
    let timer: ReturnType<typeof setTimeout>;
    window.speechSynthesis.cancel = () => clearTimeout(timer);
    window.speechSynthesis.speak = (utterance) => {
      timer = setTimeout(() => utterance.onend?.(new Event('end') as never), 1600);
    };
  });
  await page.route('**/api/courses/course-physics/classrooms/standard-mechanics-classroom?*', async route => {
    // Independent scene fixture: no backend or audio provider needed.
    await route.fulfill({ json: { material_id: 'standard-mechanics-classroom', title: '力学互动课堂', version: 1,
      scenes: [{ id: 'slide-1', type: 'slide', content: { type: 'slide', canvas: { id: 'canvas-1', viewportSize: 1000, viewportRatio: 0.5625, elements: [] } }, actions: [{ id: 'speech-1', type: 'speech', text: '这是第一句。接着讲第二句。' }] }] } });
  });
  await page.goto('/#classroom-studio?course_id=course-physics');
  const tree = page.getByRole('tree', { name: '课程目录' });
  await tree.getByRole('treeitem', { name: /1\.1 力与运动/ }).getByRole('button').click();
  await tree.getByRole('treeitem', { name: /力学互动课堂/ }).getByRole('button').click();
  await page.getByRole('button', { name: '播放当前页', exact: true }).click();
  await expect(page.locator('.classroom-subtitle')).toHaveText('这是第一句。');
  await expect(page.locator('.classroom-subtitle')).toHaveText('接着讲第二句。');
  await expect(page.locator('.classroom-subtitle')).toHaveCount(0);
  await page.getByRole('button', { name: '重播当前页', exact: true }).click();
  await expect(page.locator('.classroom-subtitle')).toHaveText('这是第一句。');
});

test('student practice submits letter keys and multiple selections against the published version', async ({ teacherPage: page }) => {
  await page.addInitScript(() => window.localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'student-fixture-token', user: { username: 'student-a', role: 'student' } })));
  await page.route('**/api/auth/verify', route => route.fulfill({ json: { valid: true, user: { username: 'student-a', role: 'student' } } }));
  await page.route('**/api/auth/me', route => route.fulfill({ json: { username: 'student-a', role: 'student' } }));

  const resource = { material_id: 'practice-student', standard_kind: 'practice', material_type: 'quiz', review_status: 'approved', current_version: 3, approved_version: 2,
    resource: { material_id: 'practice-student', title: '学生练习', content: { questions: [
      { id: 'single', type: 'single_choice', stem: '请选择正确状态', options: ['静止', '加速'], required: true },
      { id: 'multi', type: 'multiple_choice', stem: '请选择全部正确项', options: ['第一项', '第二项', '第三项'], required: true },
      { id: 'text', type: 'short_answer', stem: '说明理由', required: true },
    ] } } };
  await page.route('**/api/courses/course-physics/classroom-catalog', route => route.fulfill({ json: {
    course_id: 'course-physics', mode: 'learn', leaves: [{ leaf_id: 'practice-node', title: '练习小节', path_titles: ['第一章', '练习小节'], chapter_id: 'chapter', chapter_title: '第一章', resources: [resource] }],
  } }));
  let submitted: Record<string, unknown> | null = null;
  await page.route('**/resources/practice-student/versions/2/learning/questions:submit', async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ json: { status: 'completed', completion_basis: 'required_questions_submitted', correct_count_latest: 3, answered_question_count: 3, required_question_count: 3 } });
  });
  await page.goto('/#student-classroom?course_id=course-physics&node_id=practice-node&resource_id=practice-student');
  await expect(page.getByRole('heading', { name: '学生练习' })).toBeVisible({ timeout: 25000 });
  await expect(page.getByRole('button', { name: '提交答案' })).toBeDisabled();
  await page.getByRole('radio', { name: 'A. 静止' }).check();
  await page.getByRole('checkbox', { name: 'A. 第一项' }).check();
  await page.getByRole('checkbox', { name: 'C. 第三项' }).check();
  await page.getByRole('textbox', { name: '第 3 题答案' }).fill('合力为零');
  await page.getByRole('button', { name: '提交答案' }).click();
  await expect(page.getByText('已完成 · 最新答对 3 题')).toBeVisible();
  expect(submitted).toMatchObject({ answers: { single: 'A', multi: ['A', 'C'], text: '合力为零' } });
  await expect(page.getByRole('button', { name: '批准并发布' })).toHaveCount(0);
});
