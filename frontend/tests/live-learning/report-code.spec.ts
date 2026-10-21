import { test, expect } from 'playwright/test';
import { seedState } from '../../src/selfLearning/model';

for (const width of [1440, 390]) {
  test(`report code remains readable at ${width}px`, async ({ page, context }) => {
    await page.setViewportSize({ width, height: 900 });
    const state = seedState();
    const user = { username: 'report-code-fixture', role: 'student' };
    const content = '# 代码示例\n\n行内代码 `value = 42`。\n\n```text\n[1, 2] + [3] = [1, 2, 3]\n```\n\n```python\nprint(42)\n```\n\n```\nplain_code = 42\n```';
    const material = {
      material_id: 'report-code-fixture', material_type: 'report',
      title: '代码示例', studio_title: '代码示例', studio_mode: 'generate',
      origin_type: 'personal', status: 'ready', content, report: content, version: 1,
    };
    await context.addInitScript(user => {
      localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user }));
    }, user);
    await context.route('**/api/**', route => {
      const path = new URL(route.request().url()).pathname;
      const json = path.endsWith('/auth/verify') ? { valid: true, user }
        : path.endsWith('/auth/me') ? user
        : path.endsWith('/self-learning/state') ? { ...state, shared: [], serverJobs: [] }
        : path.endsWith('/personal-studio') ? { resources: [material], jobs: [] }
        : path.includes('/personal-studio/resources/report/') ? material
        : path.endsWith('/course-preparations') ? { preparations: [] }
        : path.endsWith('/api/courses') ? [] : { items: [] };
      return route.fulfill({ json });
    });
    await page.goto('/#/my-resources');
    await page.locator('.studio-resource-row').first().click();
    const preview = page.locator('.markdown-document');
    await expect(preview.locator('pre')).toHaveCount(3);
    await expect(preview.locator('pre').nth(0)).toHaveText('[1, 2] + [3] = [1, 2, 3]');
    const samples = await preview.locator('code').evaluateAll(nodes => {
      function luminance(color: string) {
        return color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(value => {
          const channel = value / 255;
          return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4;
        }).reduce((sum, channel, i) => sum + channel * [.2126, .7152, .0722][i], 0);
      }
      return nodes.map(node => {
        const style = getComputedStyle(node);
        let ancestor: Element | null = node;
        let background = 'rgb(255, 255, 255)';
        while (ancestor) {
          const color = getComputedStyle(ancestor).backgroundColor;
          if (color !== 'transparent' && color !== 'rgba(0, 0, 0, 0)') { background = color; break; }
          ancestor = ancestor.parentElement;
        }
        const a = luminance(style.color), b = luminance(background);
        return { text: node.textContent, contrast: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) };
      });
    });
    expect(samples).toHaveLength(4);
    for (const sample of samples) expect(sample.contrast, sample.text || 'code').toBeGreaterThanOrEqual(4.5);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
