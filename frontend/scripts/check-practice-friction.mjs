// Numerical acceptance of one real generated example, not a validator for all topics.
import {chromium} from 'playwright';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const artifact=JSON.parse(fs.readFileSync(process.argv[2] || '/tmp/edu-practice-generated.json','utf8'));
const browser=await chromium.launch();
try {
 const page=await browser.newPage();
 await page.setContent('<iframe sandbox="allow-scripts" style="width:100%;height:900px"></iframe>');
 await page.locator('iframe').evaluate((el,html)=>el.srcdoc=html,artifact.html);
 await page.waitForTimeout(500);
 const frame=page.frames()[1];
 const cases=[];
 for(const [v0,mu] of [[4,.2],[8,.2],[4,.4]]){
  await frame.locator('[data-param="v0"]').fill(String(v0));
  await frame.locator('[data-param="mu"]').fill(String(mu));
  await page.waitForTimeout(200);
  const state=await frame.evaluate(()=>window.EduPractice.snapshot());
  const distance=state.results['理论停止距离(m)'],expected=v0*v0/(2*mu*9.8);
  assert.ok(Math.abs(distance-expected)<.002);
  cases.push({v0,mu,expected,reported:distance});
 }
 fs.writeFileSync('../docs/acceptance/2026-10-13-interactive-practice/numerical-check.json',JSON.stringify({scope:'one-generated-friction-example',formula:'s=v0^2/(2*mu*9.8)',cases},null,2));
 console.log(JSON.stringify(cases));
} finally {await browser.close()}
