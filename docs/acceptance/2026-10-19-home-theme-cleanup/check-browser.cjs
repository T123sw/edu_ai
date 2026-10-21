const { chromium, expect } = require('/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const [base, label] = process.argv.slice(2);
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const width of [1440, 390, 320]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'home_check', role: 'student' } })));
      await page.route('**/api/**', async route => {
        const pathname = new URL(route.request().url()).pathname.replace(/^\/backend/, '');
        let json = { items: [] };
        if (pathname.endsWith('/auth/verify')) json = { valid: true, user: { username: 'home_check', role: 'student' } };
        if (pathname.endsWith('/self-learning/state')) json = { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] };
        if (pathname === '/api/practice') json = { items: [{ id: 'lab_saved', topic: '已保存的摩擦力实验', status: 'succeeded' }, { id: 'lab_running', topic: '待完成的实验', status: 'running' }] };
        if (pathname === '/api/pbl') json = { items: [{ exerciseId: 'pbl_saved', topic: '已保存的编程项目', status: 'ready', jobId: 'job_saved' }, { exerciseId: 'pbl_running', topic: '待完成的项目', status: 'queued', jobId: 'job_running' }] };
        await route.fulfill({ json });
      });
      await page.goto(`${base}/#/practice`);
      await expect(page.getByRole('heading', { name: '已保存的摩擦力实验' })).toBeVisible();
      await expect(page.getByRole('heading', { name: '已保存的编程项目' })).toBeVisible();
      await expect(page.getByRole('button', { name: '生成互动实验', exact: true })).toBeVisible();
      await expect(page.locator('.sl-bubble-entry')).toHaveCount(0);
      await expect(page.getByText('冒泡排序 · 分步体验')).toHaveCount(0);
      for (const kind of ['实验', '项目']) {
        const section = page.getByRole('region', { name: `我的${kind}`, exact: true });
        await expect(section.locator('.sl-recent-filters')).toHaveCount(0);
        await expect(section.getByRole('button', { name: /^(生成中|可体验|全部)$/ })).toHaveCount(0);
        await expect(section.getByRole('heading', { name: `待完成的${kind}` })).toBeVisible();
        await section.getByRole('button', { name: `搜索${kind}`, exact: true }).click();
        await section.getByRole('textbox', { name: `搜索${kind}` }).fill('已保存');
        await expect(section.getByRole('heading', { name: `待完成的${kind}` })).toHaveCount(0);
        await section.getByRole('button', { name: `关闭${kind}搜索` }).click();
        await expect(section.getByRole('heading', { name: `待完成的${kind}` })).toBeVisible();
      }
      const trigger = page.getByRole('button', { name: '页面配色', exact: true });
      await expect(trigger.locator('.theme-switcher-palette')).toBeVisible();
      for (const [theme, name] of [['ocean', '雾海蓝'], ['sunset', '暖杏'], ['dark', '石墨夜'], ['system', '跟随系统'], ['forest', '纸间绿']]) {
        await trigger.click();
        const panel = page.getByRole('dialog', { name: '页面配色' });
        const bounds = await panel.boundingBox();
        expect(bounds.x).toBeGreaterThanOrEqual(0);
        expect(bounds.x + bounds.width).toBeLessThanOrEqual(width);
        if (theme === 'ocean') await page.screenshot({ path: path.join(__dirname, `${label}-${width}-palette.png`) });
        await panel.getByRole('button', { name, exact: true }).click();
        await expect(page.locator('html')).toHaveAttribute('data-theme-preference', theme);
        await expect(panel).toHaveCount(0);
        await expect(trigger).toBeFocused();
        expect(await page.evaluate(() => localStorage.getItem('stitch-theme'))).toBe(theme);
        await page.screenshot({ path: path.join(__dirname, `${label}-${width}-${theme}.png`), fullPage: true });
        if (theme === 'ocean') {
          await page.reload();
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'ocean');
        }
      }
      await trigger.click();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog', { name: '页面配色' })).toHaveCount(0);
      await expect(trigger).toBeFocused();
      await trigger.click();
      await page.getByRole('region', { name: '我的实验', exact: true }).getByRole('heading', { name: /^我的实验/ }).click();
      await expect(page.getByRole('dialog', { name: '页面配色' })).toHaveCount(0);
      await page.screenshot({ path: path.join(__dirname, `${label}-${width}.png`), fullPage: true });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.getByRole('combobox', { name: '实践方式', exact: true }).click();
      await page.getByRole('option', { name: '编程练习（PBL）' }).click();
      await expect(page.getByRole('button', { name: '生成项目', exact: true })).toBeVisible();
      await page.reload();
      await expect(page.getByRole('button', { name: '生成互动实验', exact: true })).toBeVisible();
      await expect(page.locator('.sl-bubble-entry')).toHaveCount(0);
      expect(errors).toEqual([]);
      results.push({ width, removed: true, filtersRemoved: true, allStatusesVisible: true, search: true, paletteVisible: true, themes: 5, themePersistence: true, escapeAndOutsideClose: true, listsVisible: true, modeSwitch: true, refresh: true, errors });
      await page.close();
    }
    fs.writeFileSync(path.join(__dirname, `${label}-results.json`), JSON.stringify({ base, api: 'fixtures', results }, null, 2) + '\n');
    console.log(JSON.stringify(results));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
