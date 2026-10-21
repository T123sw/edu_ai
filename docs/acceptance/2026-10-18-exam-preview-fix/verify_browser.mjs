import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import assert from 'node:assert/strict';

const root = '/home/zxqs_ep/Edu_AI';
const out = root + '/docs/acceptance/2026-10-18-exam-preview-fix';
const base = process.argv[2] || 'http://127.0.0.1';
const phase = base === 'http://127.0.0.1' ? 'online' : 'preview';
const auth = JSON.parse(fs.readFileSync(root + '/.runtime/exam-real-paper-e2e/auth.json'));
const report = {phase, startedAt: new Date().toISOString(), boundary: 'Read-only browser replay of three existing real-model papers; no new generation', papers: [], errors: []};
const browser = await chromium.launch({headless:true});
try {
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  await context.addInitScript(a => localStorage.setItem('edu-ai-auth', JSON.stringify(a)), {token:auth.token,user:{username:auth.username,role:'student'}});
  if (phase === 'preview') await context.route('**/backend/**', async route => {
    const url = new URL(route.request().url());
    const response = await route.fetch({url:'http://127.0.0.1' + url.pathname + url.search});
    await route.fulfill({response});
  });
  const page = await context.newPage();
  page.on('pageerror', error => report.errors.push(error.message));
  await page.goto(base + '/#/exam');
  for (const label of ['kentucky-0013','kentucky-0014','kentucky-0014-repeat']) {
    const old = JSON.parse(fs.readFileSync(root + '/docs/acceptance/2026-10-18-exam-multi-pdf/' + label + '/online-browser.json'));
    await page.locator('.exam-task').filter({hasText:old.tag}).first().getByRole('button',{name:'查看试卷'}).click();
    const preview = page.getByRole('region',{name:'试卷预览'});
    await preview.waitFor();
    const roots = preview.locator(':scope > article');
    assert.equal(await roots.count(),4);
    assert.equal(await roots.locator(':scope > article').count(),17);
    if (label === 'kentucky-0013') {
      const first = await roots.first().textContent();
      assert.equal(first.split('双向链表中每个结点有').length - 1,1,'duplicated question still visible');
      assert.ok(first.includes('newNode->next = insertPlace;'),'code was lost');
      assert.ok(first.includes('链表前端（表头）'),'child options were lost');
      assert.ok((await roots.nth(1).textContent()).includes('本题四个小问相互独立'),'shared instructions were lost');
    }
    const viewports = [];
    for (const width of [1440,390,320]) {
      await page.setViewportSize({width,height:1000});
      await roots.first().evaluate(element => element.scrollIntoView({block:'start'}));
      await page.screenshot({path:out + `/${phase}-${label}-${width}.png`});
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      assert.equal(overflow,false);
      viewports.push({width,overflow});
    }
    report.papers.push({label,questions:4,children:17,viewports});
    await preview.getByRole('button',{name:'关闭预览'}).click();
    await preview.waitFor({state:'hidden'});
  }
  assert.deepEqual(report.errors,[]);
  report.passed = true;
} catch (error) {
  report.failure = String(error);
  throw error;
} finally {
  report.finishedAt = new Date().toISOString();
  fs.writeFileSync(out + '/' + phase + '-browser.json',JSON.stringify(report,null,2) + '\n');
  await browser.close();
}
console.log(phase + ': three papers, 4 parents / 17 children each, 3 viewport widths passed');
