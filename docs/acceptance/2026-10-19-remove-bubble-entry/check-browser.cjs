const { chromium, expect } = require('/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const [base, label] = process.argv.slice(2);
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'home_check', role: 'student' } })));
      await page.route('**/api/**', async route => {
        const pathname = new URL(route.request().url()).pathname.replace(/^\/backend/, '');
        let json = { items: [] };
        if (pathname.endsWith('/auth/verify')) json = { valid: true, user: { username: 'home_check', role: 'student' } };
        if (pathname.endsWith('/self-learning/state')) json = { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] };
        if (pathname === '/api/practice') json = { items: [{ id: 'lab_saved', topic: '已保存的摩擦力实验', status: 'succeeded' }] };
        if (pathname === '/api/pbl') json = { items: [{ exerciseId: 'pbl_saved', topic: '已保存的编程项目', status: 'ready', jobId: 'job_saved' }] };
        await route.fulfill({ json });
      });
      await page.goto(`${base}/#/practice`);
      await expect(page.getByRole('heading', { name: '已保存的摩擦力实验' })).toBeVisible();
      await expect(page.getByRole('heading', { name: '已保存的编程项目' })).toBeVisible();
      await expect(page.getByRole('button', { name: '生成互动实验', exact: true })).toBeVisible();
      await expect(page.locator('.sl-bubble-entry')).toHaveCount(0);
      await expect(page.getByText('冒泡排序 · 分步体验')).toHaveCount(0);
      await page.screenshot({ path: path.join(__dirname, `${label}-${width}.png`), fullPage: true });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.getByRole('combobox', { name: '实践方式', exact: true }).click();
      await page.getByRole('option', { name: '编程练习（PBL）' }).click();
      await expect(page.getByRole('button', { name: '生成项目', exact: true })).toBeVisible();
      await page.reload();
      await expect(page.getByRole('button', { name: '生成互动实验', exact: true })).toBeVisible();
      await expect(page.locator('.sl-bubble-entry')).toHaveCount(0);
      expect(errors).toEqual([]);
      results.push({ width, removed: true, listsVisible: true, modeSwitch: true, refresh: true, errors });
      await page.close();
    }
    fs.writeFileSync(path.join(__dirname, `${label}-results.json`), JSON.stringify({ base, api: 'fixtures', results }, null, 2) + '\n');
    console.log(JSON.stringify(results));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
