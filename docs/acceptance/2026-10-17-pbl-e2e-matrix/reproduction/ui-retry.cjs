const {chromium,expect}=require('/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test'),fs=require('node:fs');
const root='/tmp/pbl-matrix-20261017/matrix_shop_b',out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-e2e-matrix';
(async()=>{
 const auth=JSON.parse(fs.readFileSync(root+'/auth.json')),created=JSON.parse(fs.readFileSync(root+'/created.json'));
 const browser=await chromium.launch({headless:true});const page=await browser.newPage();const api=[];
 try{
  await page.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),auth);
  await page.route('**/api/**',async route=>{const u=new URL(route.request().url());const response=await route.fetch({url:'http://127.0.0.1:8027'+u.pathname.replace(/^\/backend/,'')+u.search,timeout:120000});api.push({method:route.request().method(),path:u.pathname,status:response.status()});await route.fulfill({response});});
  await page.goto('http://127.0.0.1/#/practice/code/'+created.exerciseId);
  await expect(page.getByRole('button',{name:'重试生成',exact:true})).toBeVisible({timeout:120000});
  const responsePromise=page.waitForResponse(r=>r.url().endsWith('/retry')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'重试生成',exact:true}).click();const response=await responsePromise,job=await response.json();
  await page.waitForURL('**/practice/code/'+job.edu_job_id);
  await expect.poll(()=>api.some(r=>r.path.endsWith('/api/pbl/'+job.edu_job_id)&&r.status===404),{timeout:30000}).toBeTruthy();
  const result={exerciseId:created.exerciseId,retryJobId:job.edu_job_id,url:page.url(),retryHttpStatus:response.status(),wrongResourceNavigation:page.url().endsWith('/'+job.edu_job_id),resourceLookup404:api.filter(r=>r.status===404),visibleText:await page.locator('body').innerText(),reproduced:true};
  fs.writeFileSync(out+'/ui-retry-routing.json',JSON.stringify(result,null,2));await page.screenshot({path:out+'/ui-retry-routing.png',fullPage:true});console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
