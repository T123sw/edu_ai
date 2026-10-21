const {chromium,request,expect}=require('/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root='/tmp/pbl-matrix-20261017',out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-e2e-matrix';
const API='http://127.0.0.1:8027';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const save=(p,d)=>fs.writeFileSync(p,JSON.stringify(d,null,2));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function enter(page){
 const stage=page.locator('.pbl-workbench-stage');await stage.waitFor();
 if(Math.abs((await stage.boundingBox()).y)>2)await page.getByRole('button',{name:'展开工作区',exact:true}).click();
 await expect(stage).toHaveAttribute('data-focused','true');
}
async function edit(page,file,code){
 await page.getByRole('button',{name:file.split('/').pop(),exact:true}).click();
 const editor=page.locator('.cm-content[contenteditable=true]');await editor.click();
 await page.keyboard.press('ControlOrMeta+A');await page.keyboard.insertText(code);await page.keyboard.press('ControlOrMeta+Home');
 await expect(page.getByTestId('save-status')).toHaveText('已保存',{timeout:20000});
}
async function run(browser,name){
 const dataRoot=path.join(root,'matrix_'+name),detail=read(path.join(dataRoot,'detail.json'));
 if(!detail.artifact)return {name,skipped:true,reason:'generation failed'};
 const a=detail.artifact,privateData=read(path.join(dataRoot,'private.json')).candidate_private,auth=read(path.join(dataRoot,'auth.json'));
 const client=await request.newContext({baseURL:API,extraHTTPHeaders:{Authorization:'Bearer '+auth.token},timeout:120000});
 const p='/api/pbl/'+a.exerciseId;
 const before=await(await client.get(p+'/workspace')).json();
 const reset=await client.put(p+'/workspace',{data:{artifactVersion:a.artifactVersion,expectedRevision:before.revision,mutationId:crypto.randomUUID(),files:a.starterFiles,activeTaskId:a.tasks[0].id,customInputText:''}});expect(reset.ok()).toBeTruthy();
 const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
 await context.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),auth);
 const page=await context.newPage();page.setDefaultTimeout(30000);const errors=[],failures=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('requestfailed',r=>failures.push({url:r.url().split('?')[0],error:r.failure()?.errorText}));
 await page.route('**/api/**',async route=>{
  const u=new URL(route.request().url());const target=API+u.pathname.replace(/^\/backend/,'')+u.search;
  try{const response=await route.fetch({url:target,timeout:120000});await route.fulfill({response});}
  catch(e){await route.abort();}
 });
 const report={name,exerciseId:a.exerciseId,steps:[],checks:a.checks.length,errors,requestFailures:failures};
 try{
  await page.goto('http://127.0.0.1/#/practice/code/'+a.exerciseId);await enter(page);
  await page.getByRole('button',{name:'检查本步',exact:true}).click();
  await expect(page.getByTestId('task-status')).toHaveText('还需要调整',{timeout:120000});report.emptyStarterRejected=true;
  for(let i=0;i<a.tasks.length;i++){
   const task=a.tasks[i],files=privateData.completed[i].candidate.referenceFiles;
   await expect(page.locator('.pbl-brief-intro h2')).toHaveText(task.title);
   for(const [f,c] of Object.entries(files))await edit(page,f,c);
   await page.getByRole('button',{name:'检查本步',exact:true}).click();
   await expect(page.getByTestId('task-status')).toHaveText('本步检查通过',{timeout:120000});
   const ws=await(await client.get(p+'/workspace')).json();expect(ws.files).toEqual(files);
   report.steps.push({id:task.id,passed:true,cumulative:task.cumulativeCheckIds.length});console.log(name,'UI_STEP',i+1,task.id);
   if(i<a.tasks.length-1){await page.getByRole('button',{name:'下一步 →',exact:true}).click();await expect(page.locator('.pbl-brief-intro h2')).toHaveText(a.tasks[i+1].title);const ws2=await(await client.get(p+'/workspace')).json();expect(ws2.files).toEqual(files);}
  }
  await expect(page.getByText('项目全部功能已在当前代码中通过检查。')).toBeVisible();
  await page.getByRole('button',{name:'页面预览',exact:true}).click();
  const preview=page.frameLocator('.sp-preview iframe');
  await expect(preview.locator('#root')).not.toBeEmpty({timeout:90000});
  if(name==='layout')await expect(preview.getByRole('heading',{name:'我的作品',exact:true})).toBeVisible({timeout:90000});
  else if(name==='score')await expect(preview.getByText('红队',{exact:true})).toBeVisible({timeout:90000});
  else await expect(preview.getByRole('textbox').first()).toBeVisible({timeout:90000});
  report.previewText=await preview.locator('body').innerText();report.previewRendered=true;
  report.previewControls=await preview.locator('button,input,select').evaluateAll(els=>els.map(e=>({tag:e.tagName,text:e.textContent,label:e.getAttribute('aria-label'),testId:e.getAttribute('data-testid'),type:e.getAttribute('type')})));
  await page.screenshot({path:path.join(out,name+'-desktop.png'),fullPage:true});
  const final=privateData.completed.at(-1).candidate.referenceFiles;
  await edit(page,'/src/App.jsx',final['/src/App.jsx']+'\n// matrix refresh proof');
  await expect(page.getByTestId('task-status')).toHaveText('代码已修改，需重新检查');
  await page.reload();await enter(page);await page.getByRole('button',{name:'App.jsx',exact:true}).click();
  await page.locator('.cm-content').click();await page.keyboard.press('ControlOrMeta+End');await expect(page.locator('.cm-content')).toContainText('matrix refresh proof');await expect(page.locator('.pbl-brief-intro h2')).toHaveText(a.tasks.at(-1).title);report.refreshPreservesCodeAndStep=true;
  for(const [f,c] of Object.entries(a.starterFiles))await edit(page,f,c);
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('还需要调整',{timeout:120000});report.regressionRejected=true;
  for(const [f,c] of Object.entries(final))await edit(page,f,c);
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('本步检查通过',{timeout:120000});report.repairedCodePasses=true;
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'预览与验收',exact:true}).click();await page.getByRole('button',{name:'页面预览',exact:true}).click();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  await page.screenshot({path:path.join(out,name+'-mobile.png'),fullPage:true});report.mobileNoPageOverflow=true;
  const publicDetail=await(await client.get(p)).json();expect(JSON.stringify(publicDetail)).not.toContain('referenceFiles');report.privateAnswersExcluded=true;
  report.passed=true;
 }catch(e){report.passed=false;report.error=e.stack;await page.screenshot({path:path.join(out,name+'-failure.png'),fullPage:true}).catch(()=>{});fs.writeFileSync(path.join(root,name+'-browser-body.txt'),await page.locator('body').innerText().catch(()=>''));}
 finally{save(path.join(out,name+'-browser.json'),report);await context.close();await client.dispose();}
 console.log(name,'BROWSER',report.passed,report.error?.slice(0,200));return report;
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});const pending=new Set(['shop_a','shop_b','form','layout','score']),results=[];const end=Date.now()+20*60*1000;
 try{while(pending.size&&Date.now()<end){
  const ready=[...pending].find(n=>fs.existsSync(path.join(root,'matrix_'+n,'private.json')));
  if(!ready){await sleep(2000);continue;}
  pending.delete(ready);results.push(await run(browser,ready));save(path.join(out,'browser-summary.json'),results.map(({name,passed,skipped,reason,error})=>({name,passed,skipped,reason,error})));
 }}finally{await browser.close();}
 console.log('BROWSER_COMPLETE',JSON.stringify(results.map(r=>({name:r.name,passed:r.passed,skipped:r.skipped}))));
})().catch(e=>{console.error(e);process.exitCode=1;});
