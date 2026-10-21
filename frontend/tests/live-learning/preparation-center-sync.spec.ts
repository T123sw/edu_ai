import { test, expect } from '../e2e/fixtures/teacherApp';
import type { PreparationTask } from '../../src/liveLearning/preparationProgress';

for (const width of [1440, 390]) {
  test(`workbench task center stays synchronized with preparation modal ${width}`, async ({ teacherPage: page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    let task: PreparationTask = { preparation_id: 'prep-center', status: 'failed', stage: 'review', revision: 244, error_code: 'STEP_FAILED' };
    let cancelRevision = 0;
    await page.route('**/api/course-preparations**', route => {
      const request = route.request();
      if (request.url().endsWith('/retry')) task = { ...task, status: 'running', revision: 245, error_code: null };
      if (request.url().endsWith('/cancel')) {
        cancelRevision = request.postDataJSON().expected_revision;
        task = { ...task, status: 'canceled', revision: 246 };
      }
      return route.fulfill({ json: request.method() === 'POST' ? task : { preparations: [task] } });
    });
    await page.goto('/?liveWorkbench=1#ai?course_id=course-physics');
    await page.getByRole('button', { name: '任务中心', exact: true }).click();
    const center = page.getByRole('dialog', { name: '任务中心', exact: true });
    await expect(center.getByText('课程准备遇到问题', { exact: true })).toBeVisible();
    await expect(center.getByText('STEP_FAILED', { exact: true })).toHaveCount(0);
    await expect(center.getByLabel('课程准备阶段')).toHaveCount(0);
    await expect(center.getByText(/任务编号/)).toHaveCount(0);
    await expect(center.getByLabel(/任务进度/)).toHaveCount(0);
    await page.screenshot({ path: `test-results/preparation-progress/center-${width}.png` });
    await center.getByRole('button', { name: '查看准备进度' }).click();
    const progress = page.getByRole('dialog', { name: '课程准备', exact: true });
    await expect(center).toHaveCount(0);
    await expect(progress.getByRole('heading', { name: '课程暂未准备完成' })).toBeVisible();
    expect(await progress.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.screenshot({ path: `test-results/preparation-progress/center-modal-${width}.png` });
    await progress.getByRole('button', { name: '继续重试' }).click();
    await expect(progress.getByRole('heading', { name: '检查课程质量' })).toBeVisible();
    await progress.getByRole('button', { name: '先去浏览' }).click();
    await page.getByRole('button', { name: '任务中心，1 个进行中', exact: true }).click();
    await expect(center.getByRole('heading', { name: '检查课程质量' })).toBeVisible();
    await expect(center.getByText('STEP_FAILED')).toHaveCount(0);
    if (width === 1440) {
      task = { ...task, status: 'succeeded', stage: 'commit', revision: 246, result_ref: { course_ready: true, course_id: 'new-ready-course' } };
      await expect(center.getByRole('heading', { name: '你的课程已准备好' })).toBeVisible();
      await center.getByRole('button', { name: '查看准备进度' }).click();
      await expect(progress.getByRole('button', { name: '进入课堂' })).toBeVisible();
      await progress.getByRole('button', { name: '关闭', exact: true }).click();
      await page.reload();
      await page.getByRole('button', { name: '任务中心', exact: true }).click();
      await expect(center.getByRole('heading', { name: '你的课程已准备好' })).toBeVisible();
      expect(errors).toEqual([]);
      return;
    }
    await center.getByRole('button', { name: '查看准备进度' }).click();
    await progress.getByRole('button', { name: '取消任务', exact: true }).click();
    await progress.getByRole('button', { name: '确认取消' }).click();
    await expect(progress.getByRole('heading', { name: '课程准备已取消' })).toBeVisible();
    expect(cancelRevision).toBe(245);
    await progress.getByRole('button', { name: '关闭', exact: true }).click();
    await page.getByRole('button', { name: '任务中心', exact: true }).click();
    await expect(center.getByRole('heading', { name: '课程准备已取消' })).toBeVisible();
    await page.reload();
    await page.getByRole('button', { name: '任务中心', exact: true }).click();
    await expect(center.getByRole('heading', { name: '课程准备已取消' })).toBeVisible();
    expect(errors).toEqual([]);
  });
}
