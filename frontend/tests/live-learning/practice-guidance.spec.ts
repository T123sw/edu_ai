import { test, expect } from 'playwright/test';
import fs from 'node:fs';
import { createSession, reduceSession } from '../../src/practice/guidance/model';

for (const width of [1440, 390]) test(`guided operations, feedback, persistence and exploration (${width})`, async ({ page }) => {
  const artifact = JSON.parse(fs.readFileSync(process.env.PRACTICE_GUIDANCE_ARTIFACT || '../.runtime/practice-guidance-acceptance/quicksort-fixture.json','utf8'));
  const manifest = artifact.guidance;
  let saved = { session_id:'test-session', revision:manifest.revision, saved_seq:0, state:createSession(manifest) };
  const receipts = new Map<string, typeof saved>();
  const observations: unknown[] = []; const messages: unknown[] = [];
  const errors: string[]=[]; page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width,height:1000});
  await page.addInitScript(()=>{if(window===top)localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'guided-fixture',role:'student'}}));});
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname.replace(/^\/backend/,'');
    if (!path.startsWith('/api/')) return route.continue();
    if(path.endsWith('/auth/verify'))return route.fulfill({json:{valid:true,user:{username:'guided-fixture',role:'student'}}});
    if(path.endsWith('/self-learning/state'))return route.fulfill({json:{version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]}});
    if(path.endsWith('/events')) {
      const batch=route.request().postDataJSON();
      if(receipts.has(batch.batch_id))return route.fulfill({json:receipts.get(batch.batch_id)});
      if(batch.expected_seq!==saved.saved_seq)return route.fulfill({status:409,json:{detail:'保存冲突'}});
      for(const command of batch.commands)saved={...saved,state:reduceSession(manifest,saved.state,command)};
      saved={...saved,saved_seq:saved.state.seq}; receipts.set(batch.batch_id,structuredClone(saved));return route.fulfill({json:saved});
    }
    if(path.includes('/sessions'))return route.fulfill({json:saved});
    if(path.endsWith('/observations')){observations.push({...route.request().postDataJSON(),created_at:Date.now()/1000});return route.fulfill({json:{observations,messages}});}
    if(path.endsWith('/ask')){const payload=route.request().postDataJSON();messages.push({...payload,role:'user',content:payload.question},{...payload,role:'assistant',content:'比较当前元素与基准，观察实际变化。'});return route.fulfill({json:{observations,messages}});}
    if(path.endsWith('/practice/guided'))return route.fulfill({json:{id:'guided',job:{status:'succeeded'},artifact,journal:{observations,messages}}});
    return route.fulfill({json:{items:[]}});
  });
  await page.goto('/#/practice/guided');
  const frame=page.frameLocator('iframe');
  await expect(frame.getByRole('button',{name:'确认基准',exact:true})).toBeVisible();
  await expect(frame.locator('[data-guidance-array]')).toHaveCount(0);
  await frame.locator('[data-guidance-action="select"]').first().click();
  await expect(frame.locator('[data-guidance-feedback]')).toContainText('已选择');
  await frame.getByRole('button',{name:'确认基准',exact:true}).click();
  await frame.getByRole('button',{name:'进入下一步',exact:true}).click();
  await frame.getByRole('button',{name:'小于等于基准',exact:true}).click();
  await expect(frame.locator('[data-guidance-feedback]')).toContainText('这次判断没有改变数组');
  const state=()=>frame.locator('body').evaluate(()=>window.EduGuidance.inspect()!);
  for(let i=0;i<30;i++) {const s=await state(),a=s.attempts[s.active];if(a.complete)break;await frame.locator(`[data-guidance-action="${a.model.phase==='scan'?(a.model.array[a.model.scan]<=a.model.pivot?'left':'right'):'advance'}"]`).click();}
  await expect(frame.locator('[data-guidance-controls]')).toContainText('本步操作已完成');
  await frame.getByRole('button',{name:'进入下一步',exact:true}).click();
  await frame.getByRole('button',{name:'单步执行',exact:true}).click();
  const before=await state();
  await expect(page.locator('.practice-sync>span').first()).toHaveText('已保存');
  await page.reload();
  await expect(frame.getByRole('button',{name:'单步执行',exact:true})).toBeVisible();
  expect((await state()).attempts.recurse.model).toEqual(before.attempts.recurse.model);
  await page.getByRole('button',{name:/^观察记录/}).click();
  await page.getByLabel('记录你的发现').fill('基准归位后，两侧仍需分区。');
  await page.getByRole('button',{name:'保存本次观察',exact:true}).click();
  await expect(page.locator('.practice-history')).toContainText('基准归位后');
  await page.getByRole('button',{name:'交互实验',exact:true}).click();
  if(width<=1000)await page.getByRole('navigation',{name:'实验工作区视图'}).getByRole('button',{name:'步骤',exact:true}).click();
  await page.getByRole('navigation',{name:'探索路线'}).getByRole('button',{name:/完整实验/}).click();
  await expect(frame.locator('[data-guidance-array]')).toBeVisible();
  await frame.locator('[data-guidance-array]').fill('3, -1, 3, 0');await frame.getByRole('button',{name:'应用数组',exact:true}).click();
  await expect(frame.locator('[data-guidance-feedback]')).toContainText('初始数组已更新');
  if(width<=1000)await page.getByRole('navigation',{name:'实验工作区视图'}).getByRole('button',{name:'问答',exact:true}).click();
  await page.getByLabel('向实验伙伴提问').fill('这一步如何继续？');await page.getByRole('button',{name:'发送问题',exact:true}).click();
  await expect(page.locator('.practice-messages')).toContainText('观察实际变化');
  if(width<=1000)await page.getByRole('navigation',{name:'实验工作区视图'}).getByRole('button',{name:'步骤',exact:true}).click();
  await page.getByRole('navigation',{name:'探索路线'}).getByRole('button',{name:/处理子区间/}).click();
  expect((await state()).attempts.recurse.model).toEqual(before.attempts.recurse.model);
  await expect(page.locator('.practice-messages')).not.toContainText('观察实际变化');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  expect(errors).toEqual([]);
  await page.screenshot({path:`test-results/guidance-${width}.png`});
});

test('lost save reply is retried once, offline actions survive reload and conflicting tab is explicit', async ({ page }) => {
  const artifact=JSON.parse(fs.readFileSync('../.runtime/practice-guidance-acceptance/quicksort-fixture.json','utf8')),manifest=artifact.guidance;
  let saved={session_id:'resilience',revision:manifest.revision,saved_seq:0,state:createSession(manifest)};
  const receipts=new Map<string,typeof saved>();let drop=true,offline=false;let writes=0;
  await page.addInitScript(()=>{if(window===top)localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'resilience',role:'student'}}));});
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname.replace(/^\/backend/,'');
    if(!path.startsWith('/api/'))return route.continue();
    if(path.endsWith('/auth/verify'))return route.fulfill({json:{valid:true,user:{username:'resilience',role:'student'}}});
    if(path.endsWith('/self-learning/state'))return route.fulfill({json:{version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]}});
    if(path.endsWith('/events')) {
      if(offline)return route.abort('failed');
      const batch=route.request().postDataJSON();
      if(receipts.has(batch.batch_id))return route.fulfill({json:receipts.get(batch.batch_id)});
      if(batch.expected_seq!==saved.saved_seq)return route.fulfill({status:409,json:{detail:'实验已在其他页面更新'}});
      for(const command of batch.commands){saved={...saved,state:reduceSession(manifest,saved.state,command)};writes++;}
      saved={...saved,saved_seq:saved.state.seq};receipts.set(batch.batch_id,structuredClone(saved));
      if(drop){drop=false;return route.abort('failed');}return route.fulfill({json:saved});
    }
    if(path.includes('/sessions'))return route.fulfill({json:saved});
    if(path.endsWith('/practice/resilience'))return route.fulfill({json:{id:'resilience',job:{status:'succeeded'},artifact,journal:{observations:[],messages:[]}}});
    return route.fulfill({json:{items:[]}});
  });
  await page.goto('/#/practice/resilience');const frame=page.frameLocator('iframe');
  await frame.locator('[data-guidance-action="select"]').first().click();
  await expect(page.locator('.practice-sync')).toContainText('Failed to fetch');
  await page.reload();await expect(page.locator('.practice-sync>span').first()).toHaveText('已保存');
  await expect(frame.locator('[data-guidance-action="confirm"]')).toBeEnabled();expect(writes).toBe(1);
  offline=true;await frame.locator('[data-guidance-action="confirm"]').click();
  await expect(page.locator('.practice-sync')).toContainText('Failed to fetch');
  await page.reload();await expect(frame.locator('[data-guidance-controls]')).toContainText('本步操作已完成');
  offline=false;await page.getByRole('button',{name:'重新同步',exact:true}).click();await expect(page.locator('.practice-sync>span').first()).toHaveText('已保存');expect(writes).toBe(2);
  // Another tab advances the server while this tab retains its own local state.
  saved={...saved,state:reduceSession(manifest,saved.state,{id:'other-tab',type:'enter',step:'explore'})};saved.saved_seq=saved.state.seq;
  await frame.getByRole('button',{name:'进入下一步',exact:true}).click();
  await expect(page.locator('.practice-sync')).toContainText('保存冲突');
  await expect(frame.getByRole('button',{name:'小于等于基准',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'读取已保存进度',exact:true}).click();
  await expect(frame.locator('[data-guidance-array]')).toBeVisible();
});
