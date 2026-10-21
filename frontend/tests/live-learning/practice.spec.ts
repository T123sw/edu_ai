import {test,expect} from 'playwright/test';

for (const width of [1440,390]) test(`topic to interactive lab, observed state and persisted guidance (${width})`,async({page})=>{
 await page.setViewportSize({width,height:1000});
 await page.addInitScript(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'test',user:{username:'alice',role:'student'}})));
 let created=0, asked=0, observations:object[]=[], messages:object[]=[];
 const html=`<!DOCTYPE html><html><head></head><body><label>速度<input data-param="speed" aria-label="速度" type="range" min="1" max="10" value="2"></label><p id="out"></p><button id="run">运行</button><script>function update(){const speed=+document.querySelector('input').value;document.querySelector('#out').textContent='距离 '+speed*speed;parent.postMessage({type:'edu-practice-state',state:{parameters:{speed},results:{distance:speed*speed}}},'*')}document.querySelector('#run').onclick=update;update()</script></body></html>`;
 await page.route('**/api/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname.replace(/^\/backend/,'');
  if(path.endsWith('/auth/verify'))return route.fulfill({json:{valid:true,user:{username:'alice',role:'student'}}});
  if(path.endsWith('/self-learning/state'))return route.fulfill({json:{version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]}});
  if(path==='/api/practice'&&req.method()==='POST'){created++;expect(req.postDataJSON().topic).toBe('摩擦力');return route.fulfill({json:{id:'lab'}})}
  if(path==='/api/practice')return route.fulfill({json:{items:[]}});
  if(path.endsWith('/observations')){observations.push({...req.postDataJSON(),created_at:Date.now()/1000});return route.fulfill({json:{observations,messages}})}
  if(path.endsWith('/ask')){asked++;expect(req.postDataJSON().state.results.distance).toBe(25);expect(req.postDataJSON().step).toBe(1);messages=[{role:'user',content:req.postDataJSON().question},{role:'assistant',content:'试着减小速度，再比较距离。'}];return route.fulfill({json:{observations,messages}})}
  if(path==='/api/practice/lab')return route.fulfill({json:{id:'lab',job:{status:'succeeded'},artifact:{html,plan:{concept_name:'摩擦力实验',concept_overview:'操作并观察',steps:[{title:'观察速度',instruction:'调整速度后运行',question:'距离怎么变化？'},{title:'比较结果',instruction:'记录两次结果',question:'什么关系？'},{title:'解释',instruction:'解释观察',question:'为什么？'}]}},journal:{observations,messages}}});
  return route.fulfill({json:{items:[]}});
 });
 await page.goto('/#/practice');await page.getByLabel('实验主题与目标').fill('摩擦力');await page.getByRole('button',{name:'生成互动实验',exact:true}).click();
  await page.getByRole('button',{name:'进入实验',exact:true}).click();
 await expect(page.getByRole('heading',{name:'摩擦力实验',exact:true,includeHidden:true})).toHaveText('摩擦力实验');expect(created).toBe(1);
 await expect(page.locator('.practice-intro-message')).toHaveCount(1);
 await expect(page.locator('.practice-messages .practice-message').first()).toContainText('操作并观察');
 await expect(page.locator('.practice-detail > .practice-heading')).toHaveCount(0);
 await expect(page.locator('.practice-step-navigation,.practice-overview')).toHaveCount(0);
 const frame=page.frameLocator('iframe[title="互动实验"]');await frame.getByLabel('速度').fill('5');await frame.getByRole('button',{name:'运行',exact:true}).click();
 await expect(page.locator('.practice-state')).toContainText('distance');await expect(page.locator('.practice-state dd')).toHaveText('25');
 await page.getByRole('button',{name:'专注实验',exact:true}).click();await expect(page.locator('.practice-guide')).toBeHidden();await expect(frame.getByLabel('速度')).toHaveValue('5');
 await page.keyboard.press('Escape');
 if(width===390) await page.getByRole('navigation',{name:'实验工作区视图'}).getByRole('button',{name:'步骤',exact:true}).click();
 else await expect(page.locator('.practice-guide')).toBeVisible();
 await page.getByRole('navigation',{name:'探索路线'}).getByRole('button',{name:/比较结果/}).click();await expect(frame.getByLabel('速度')).toHaveValue('5');
 await page.getByRole('button',{name:'观察记录',exact:true}).click();
 await page.getByLabel('记录你的发现').fill('速度增大，距离增大');
 await page.getByRole('button',{name:'交互实验',exact:true}).click();await expect(frame.getByLabel('速度')).toHaveValue('5');
 await page.getByRole('button',{name:'观察记录',exact:true}).click();await expect(page.getByLabel('记录你的发现')).toHaveValue('速度增大，距离增大');
 await page.getByRole('button',{name:'保存本次观察',exact:true}).click();
 await expect(page.locator('.practice-history')).toContainText('速度增大，距离增大');
 expect(asked).toBe(0); // Layout, navigation and saving do not start agent turns.
 if(width===390) await page.getByRole('navigation',{name:'实验工作区视图'}).getByRole('button',{name:'问答',exact:true}).click();
 await page.getByRole('button',{name:'给我一个操作提示',exact:true}).click();await expect(page.locator('.practice-messages')).toContainText('试着减小速度');expect(asked).toBe(1);
 await page.reload();await expect(page.locator('.practice-intro-message')).toHaveCount(1);await expect(page.locator('.practice-history')).toContainText('速度增大，距离增大');await expect(page.locator('.practice-messages')).toContainText('试着减小速度');expect(created).toBe(1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth && document.documentElement.scrollHeight<=innerHeight+2)).toBe(true);
 expect(await page.locator('iframe').getAttribute('sandbox')).toBe('allow-scripts');
 await page.screenshot({path:`test-results/practice-${width}.png`,fullPage:true});
});

test('real generated experiment fits three columns and survives panel changes',async({page})=>{
 const fs=await import('node:fs');
 const artifactPath=process.env.PRACTICE_UI_ARTIFACT;
 test.skip(!artifactPath,'Set PRACTICE_UI_ARTIFACT to inspect a real generated artifact.');
 const artifact=JSON.parse(fs.readFileSync(artifactPath!,'utf8'));
 await page.addInitScript(()=>{localStorage.setItem('stitch-theme','ocean');localStorage.setItem('edu-ai-auth',JSON.stringify({token:'test',user:{username:'alice',role:'student'}}))});
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/auth/verify'))return route.fulfill({json:{valid:true,user:{username:'alice',role:'student'}}});
  if(path.endsWith('/self-learning/state'))return route.fulfill({json:{version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]}});
  if(path.endsWith('/practice/real-preview'))return route.fulfill({json:{id:'real-preview',job:{status:'succeeded'},artifact,journal:{observations:[],messages:[]}}});
  return route.fulfill({json:{items:[]}});
 });
 for(const width of [1920,1440,390]){
  await page.setViewportSize({width,height:1000});
  await page.goto('/#/practice/real-preview');
  await expect(page.getByRole('heading',{name:artifact.plan.concept_name,exact:true,includeHidden:true})).toHaveText(artifact.plan.concept_name);
  const embedded=page.frameLocator('iframe[title="互动实验"]');
  await expect(embedded.locator('body')).toBeVisible();
  await expect.poll(async()=>embedded.locator('body').evaluate(el=>Math.ceil(el.scrollHeight)-innerHeight)).toBeLessThanOrEqual(3);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth && document.documentElement.scrollHeight<=innerHeight+2)).toBe(true);
  if(width>1000){
   const boxes=await Promise.all(['.practice-directory','.practice-main','.practice-guide'].map(selector=>page.locator(selector).boundingBox()));
   expect(boxes[0]!.x+boxes[0]!.width).toBeCloseTo(boxes[1]!.x,0);
   expect(boxes[1]!.x+boxes[1]!.width).toBeCloseTo(boxes[2]!.x,0);
   const composer=await page.getByLabel('向实验伙伴提问').boundingBox();
   expect(composer!.y+composer!.height).toBeLessThanOrEqual(1000);
  }
  const height=await page.locator('iframe').evaluate(el=>el.clientHeight);
  await page.evaluate(()=>window.postMessage({type:'edu-practice-size',height:3999},'*'));
  await expect(page.locator('iframe')).toHaveJSProperty('clientHeight',height);
  if(width===1920){
   const range=embedded.locator('input[type="range"]').first();
   await range.fill('10');const value=await range.inputValue();
   await page.getByRole('button',{name:'专注实验',exact:true}).click();
   await expect(range).toHaveValue(value);
   await range.focus();await page.keyboard.press('Escape');
   await expect(page.locator('.practice-guide')).toBeVisible();await expect(range).toHaveValue(value);
  }
  await page.screenshot({path:`test-results/practice-directory-${width}.png`,fullPage:true});
  if(width===390){
   const panels=page.getByRole('navigation',{name:'实验工作区视图'});
   const range=embedded.locator('input[type="range"]').first();
   const value=await range.inputValue();
   await panels.getByRole('button',{name:'步骤',exact:true}).click();
   await expect(page.locator('.practice-directory')).toBeVisible();
   await page.screenshot({path:'test-results/practice-directory-mobile-steps.png'});
   await panels.getByRole('button',{name:'问答',exact:true}).click();
   await expect(page.getByLabel('向实验伙伴提问')).toBeVisible();
   await page.getByLabel('向实验伙伴提问').fill('为什么分区后基准在中间？');
   await page.screenshot({path:'test-results/practice-directory-mobile-chat.png'});
   await panels.getByRole('button',{name:'实验',exact:true}).click();
   await expect(range).toHaveValue(value);
   await expect.poll(async()=>embedded.locator('body').evaluate(el=>Math.ceil(el.scrollHeight)-innerHeight)).toBeLessThanOrEqual(3);
   await panels.getByRole('button',{name:'问答',exact:true}).click();
   await expect(page.getByLabel('向实验伙伴提问')).toHaveValue('为什么分区后基准在中间？');
  }
 }
});
