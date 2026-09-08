import { expect, test } from './fixtures/teacherApp';

const markdown = [
  '# 备课说明', '', '第一段包含**重点**、*强调*和~~删除内容~~。', '', '第二段独立呈现。', '',
  '## 教学步骤', '', '3. 准备材料', '', '   这是第一项中的第二段。', '',
  '   - 嵌套要点', '   - 第二个要点', '', '4. 开展活动', '',
  '> 引用说明', '>', '> 引用中的第二段。', '',
  '- [x] 已完成', '- [ ] 待完成', '',
  '## 对比表格', '', '| 方式 | 优点 | 示例 |', '| :--- | ---: | :---: |', '| 讨论 | 充分表达 | 小组交流 |', '| 练习 | 巩固知识 | 独立作答 |', '',
  '### 示例代码', '', '```python', 'def example():', '    return "' + 'long_code_'.repeat(35) + '"', '', 'print(example())', '```', '',
  '行内代码 `items[0]` 与公式 $x^2$。', '', '$$', '\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}', '$$', '',
  '查看[课程说明][guide]。', '', '[guide]: https://example.com/course', '', '---', '', '结束说明。',
].join('\n');

for (const withSources of [false, true]) {
  test(`answer preserves complete Markdown structure with sources=${withSources}`, async ({ teacherPage: page }) => {
    await page.route('**/api/chat/v2/stream', route => {
      const payload = { message: { role: 'assistant', content: markdown }, conversation: { conversation_id: 'markdown-test' },
        action: { name: 'chat' }, artifacts: [], sources: withSources ? [{ source: '教学参考.pdf', content: '这是第一项中的第二段。' }, { source: '补充参考.pdf', content: '' }] : [], trace: { path: 'fast' } };
      return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'delta', payload: { content: markdown.slice(0, 80) } })}\n\ndata: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: {} })}\n\n` });
    });
    await page.goto('/#ai?course_id=course-physics');
    const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
    await input.fill('展示备课说明');
    await input.press('Enter');
    const answer = page.locator('.answer-markdown').last();
    await expect(answer.getByText('结束说明。')).toBeVisible();
    await expect(answer.getByRole('heading', { name: '备课说明', level: 1 })).toBeVisible();
    await expect(answer.locator('ol')).toHaveAttribute('start', '3');
    await expect(answer.locator('ol > li')).toHaveCount(2);
    await expect(answer.locator('ol > li').first().locator('p')).toHaveCount(2);
    await expect(answer.locator('ol ul > li')).toHaveCount(2);
    await expect(answer.locator('blockquote p')).toHaveCount(2);
    await expect(answer.getByRole('link', { name: '课程说明' })).toHaveAttribute('href', 'https://example.com/course');
    await expect(answer.locator('table tr')).toHaveCount(3);
    await expect(answer.locator('table th').nth(1)).toHaveAttribute('style', /text-align: right/);
    await expect(answer.locator('pre code')).toContainText('    return');
    await expect(answer.locator('.katex-display')).toHaveCount(1);
    await expect(answer.getByRole('checkbox')).toHaveCount(2);
    await expect(answer.locator('strong')).toHaveText('重点');
    await expect(answer.locator('del')).toHaveText('删除内容');
    expect(await answer.locator('p').first().evaluate(el => parseFloat(getComputedStyle(el).marginBottom))).toBeGreaterThan(10);
    expect(await answer.locator('ul').first().evaluate(el => getComputedStyle(el).listStyleType)).toBe('disc');
    expect(await answer.locator('pre').evaluate(el => el.scrollWidth > el.clientWidth && getComputedStyle(el).overflowX === 'auto')).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (withSources) {
      await expect(answer.getByRole('button', { name: /文本来源 1/ })).toBeVisible();
      await expect(answer.getByRole('button', { name: /文本来源 2/ })).toBeVisible();
      await answer.getByRole('button', { name: /文本来源 1/ }).hover();
      await expect(page.getByRole('tooltip')).toContainText('这是第一项中的第二段');
    }
  });
}
