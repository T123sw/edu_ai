const {chromium,expect,request}=require('/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test'),fs=require('node:fs');
const root='/tmp/pbl-restart-20261017/matrix_retry',out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-restart-e2e';
(async()=>{
 const client=await request.newContext({baseURL:'http://127.0.0.1:8027'});
 const auth=await(await client.post('/api/auth/login',{data:{username:'matrix_retry',password:'matrix-isolated-only'}})).json();
 fs.writeFileSync(root+'/auth.json',JSON.stringify(auth));
 const seed=JSON.parse(fs.readFileSync(root+'/seed.json'));
 const before=fs.readdirSync(root).filter(x=>x.startsWith('input-')).length;
 const browser=await chromium.launch({headless:true});const page=await browser.newPage();const api=[];
 try{
  await page.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),auth);
  await page.route('**/api/**',async route=>{const u=new URL(route.request().url());const response=await route.fetch({url:'http://127.0.0.1:8027'+u.pathname.replace(/^\/backend/,'')+u.search,timeout:120000});api.push({method:route.request().method(),path:u.pathname,status:response.status()});await route.fulfill({response});});
  const url='http://127.0.0.1/#/practice/code/'+seed.exerciseId;
  await page.goto(url);
  await expect(page.getByRole('button',{name:'重试生成',exact:true})).toBeVisible({timeout:60000});
  const responsePromise=page.waitForResponse(r=>r.url().endsWith('/retry')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'重试生成',exact:true}).click();const response=await responsePromise,job=await response.json();
  await expect(page).toHaveURL(url);await expect(page.getByRole('button',{name:'取消生成',exact:true})).toBeVisible();
  await page.reload();await expect(page.getByRole('button',{name:'取消生成',exact:true})).toBeVisible({timeout:60000});
  const result={...seed,retryJobId:job.edu_job_id,retryOfJobId:job.retry_of_job_id,retryHttpStatus:response.status(),sameResourceAfterRetry:true,refreshFollowsRetry:true};
  fs.writeFileSync(out+'/ui-retry-routing.json',JSON.stringify(result,null,2));
  await expect(page.locator('.pbl-workbench-stage')).toBeVisible({timeout:600000});
  result.ready=true;result.resourceLookup404=api.filter(r=>r.path.includes('/pbl/')&&r.status===404);expect(result.resourceLookup404).toEqual([]);
  result.modelCalls=fs.readdirSync(root).filter(x=>x.startsWith('input-')).length-before;
  expect(result.modelCalls).toBeGreaterThan(0);
  const phases=fs.readdirSync(root).filter(x=>x.startsWith('input-')).sort().slice(before).map(f=>JSON.parse(fs.readFileSync(root+'/'+f)).phase);
  expect(phases).not.toContain('plan');result.phases=phases;
  const first=JSON.parse(fs.readFileSync(root+'/input-'+String(before+1).padStart(3,'0')+'.json'));expect(first.data.previousChecks.length).toBeGreaterThan(0);
  result.preservedPreviousCheckCount=first.data.previousChecks.length;
  fs.writeFileSync(out+'/ui-retry-routing.json',JSON.stringify(result,null,2));await page.screenshot({path:out+'/ui-retry-routing.png',fullPage:true});console.log(JSON.stringify(result));
 }finally{await browser.close();await client.dispose();}
})().catch(e=>{console.error(e);process.exitCode=1;});
