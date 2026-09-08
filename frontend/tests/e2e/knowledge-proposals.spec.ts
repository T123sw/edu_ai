import { expect, test } from './fixtures/teacherApp';
import { installCourseKnowledgeBuildRoutes } from './fixtures/courseKnowledgeBuild';
import type { KnowledgeGraphNode } from '../../src/stitch/api/types';

for (const supplement of [false, true]) {
  test(`knowledge proposals select, revise and confirm mode=${supplement ? 'supplement' : 'create'}`, async ({ teacherPage: page }, testInfo) => {
    const fixture = await installCourseKnowledgeBuildRoutes(page, { existingGraph: supplement });
    let selected: { option_id?: string; item_ids?: string[] } = {};
    const root: KnowledgeGraphNode = { id: 'root', label: '大学物理', data: { type: 'course', summary: '基础课程' }, children: [
      { id: 'module', label: '力学', data: { type: 'knowledge_module', summary: '力学基础' }, children: [
        { id: 'point', label: '牛顿定律', children: [], data: { type: 'knowledge_point', summary: '理解运动定律' } },
      ] },
    ] };
    if (supplement) fixture.build().baseline_graph = root;
    await page.route('**/knowledge-builds/*/proposal', route => {
      const build = fixture.build();
      build.revision += 1;
      build.knowledge_proposal = { mode: supplement ? 'supplement' : 'create', summary: '依据课程目标进行规划', requirements: route.request().postDataJSON().requirements,
        options: ['brief','standard','complete'].map(level => ({ id: level, level: level as 'brief', description: '展示实际课程目录及取舍', root, metrics: { leaf_count: 1 } })),
        items: [ { id: 'one', kind: 'materials', target_id: 'point', title: '牛顿定律', reason: '根据已有资料推断需要补充练习', materials: ['边界练习'], evidence_document_ids: [] },
          { id: 'two', kind: 'materials', target_id: 'point', title: '运动分析', reason: '缺少案例', materials: ['案例'], evidence_document_ids: [] } ] };
      build.graph_draft = null;
      return route.fulfill({ json: build });
    });
    await page.route('**/knowledge-builds/*/proposal/select', route => {
      selected = route.request().postDataJSON();
      const build = fixture.build();
      build.graph_draft = root; build.revision += 1;
      return route.fulfill({ json: build });
    });
    await page.goto('/#knowledge?course_id=course-physics');
    await page.getByRole('button', { name: '更新知识库', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('radiogroup')).toHaveCount(0);
    await dialog.locator('textarea').fill('面向一年级学生，重点补充练习');
    await dialog.getByRole('button', { name: supplement ? '分析补充建议' : '生成三份大纲', exact: true }).click();
    await expect(dialog.getByRole('heading', { name: supplement ? '确认本次补充内容' : '比较课程大纲' })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('proposal.png'), fullPage: true });
    if (supplement) {
      await dialog.getByRole('checkbox').nth(1).uncheck();
      await dialog.getByRole('button', { name: '检查目录并继续（1 项）' }).click();
      expect(selected.item_ids).toEqual(['one']);
    } else {
      await expect(dialog.getByText('牛顿定律', { exact: true }).first()).toBeVisible();
      await dialog.getByText('力学', { exact: true }).first().click();
      await expect(dialog.getByText('牛顿定律', { exact: true }).first()).toBeHidden();
      await dialog.getByText('力学', { exact: true }).first().click();
      await expect(dialog.getByText('牛顿定律', { exact: true }).first()).toBeVisible();
      await dialog.getByRole('button', { name: '选择标准大纲' }).click();
      expect(selected.option_id).toBe('standard');
    }
    await expect(dialog.getByRole('button', { name: '确认并更新知识库' })).toBeDisabled();
    expect(fixture.events).not.toContain('build:start');
    await dialog.getByRole('checkbox', { name: '我已检查课程目录和本次更新内容' }).check();
    await dialog.getByRole('button', { name: '确认并更新知识库' }).click();
    await expect.poll(() => fixture.events.includes('graph:confirm')).toBe(true);
    await expect(dialog).not.toBeVisible();
  });
}
