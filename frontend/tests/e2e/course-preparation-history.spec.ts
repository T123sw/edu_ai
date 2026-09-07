import { expect, test } from './fixtures/teacherApp';

test('overview retains the preparation topic and resumes it from the primary action', async ({ teacherPage: page }) => {
  await page.addInitScript(() => localStorage.setItem('edu-ai-resume:v1:teacher:teacher-a', JSON.stringify({
    version: 1, courseId: 'course-physics', route: 'ai',
    params: { scopeType: 'knowledge_point', scopeId: 'mechanics' }, visitedAt: '2026-09-07T08:00:00Z',
  })));
  await page.route('**/api/courses/course-physics/materials?**', (route) => {
    const query = new URL(route.request().url()).searchParams;
    expect(query.get('space')).toBe('mine');
    return route.fulfill({ json: [{ material_id: 'recent', material_type: 'report', title: '力学教学报告', updated_at: '2026-09-07T09:00:00Z' }] });
  });
  await page.goto('/#course-detail?course_id=course-physics');
  const history = page.locator('.course-overview__history');
  await expect(history.getByText('力学', { exact: true })).toBeVisible();
  await expect(history.getByText('力学教学报告', { exact: true })).toBeVisible();
  const button = page.locator('.course-overview__continuation').getByRole('link', { name: '开始备课' });
  await expect(button).toHaveAttribute('href', '#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=mechanics');
  expect(await page.locator('.course-overview a').count()).toBe(1);
  await button.click();
  await expect(page).toHaveURL(/#ai\?course_id=course-physics&scopeType=knowledge_point&scopeId=mechanics$/);
});

test('failed material lookup is distinguished from no generated materials', async ({ teacherPage: page }) => {
  await page.route('**/api/courses/course-physics/materials?**', route => route.fulfill({ status: 503, json: { detail: 'unavailable' } }));
  await page.goto('/#course-detail?course_id=course-physics');
  await expect(page.locator('.course-overview__history')).toContainText('暂时无法读取资料');
  await expect(page.locator('.course-overview__history')).not.toContainText('还没有生成资料');
  await expect(page.locator('.course-overview__primary')).toHaveAttribute('href', '#ai?course_id=course-physics');
});
