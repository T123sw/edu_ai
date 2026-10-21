import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';import assert from 'node:assert/strict';
const root='/home/zxqs_ep/Edu_AI', [label,expectedText]=process.argv.slice(2), expected=Number(expectedText),out=root+'/docs/acceptance/2026-10-18-exam-multi-pdf/'+label;
const auth=JSON.parse(fs.readFileSync(root+'/.runtime/exam-real-paper-e2e/auth.json'));
const summary=JSON.parse(fs.readFileSync(out+'/online-browser.json')),tag=summary.tag;
summary.resume_startedAt=new Date().toISOString();delete summary.completed;delete summary.failure;
const save=()=>fs.writeFileSync(out+'/online-browser.json',JSON.stringify(summary,null,2));
const browser=await chromium.launch({headless:true});
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}});await context.addInitScript(a=>localStorage.setItem('edu-ai-auth',JSON.stringify(a)),{token:auth.token,user:{username:auth.username,role:'student'}});
 const page=await context.newPage();page.on('pageerror',e=>summary.errors.push(e.message));
 const get=async path=>{const r=await context.request.get('http://127.0.0.1/backend/api'+path,{headers:{Authorization:'Bearer '+auth.token}});assert.equal(r.status(),200);return r.json();};
 let gid=summary.generations.at(-1);
 // A completed upstream turn can finish replay after the bridge restarts.
 let prior;for(let i=0;i<180;i++){prior=await get('/exam-generations/'+gid);if(['failed','succeeded','canceled'].includes(prior.status))break;await page.waitForTimeout(1000);}
 assert.ok(['failed','succeeded'].includes(prior.status),'Prior interrupted task did not settle');
 for(let attempt=0;attempt<2;attempt++){
  if(prior.status!=='succeeded'){
   await page.goto('http://127.0.0.1/#/exam');const card=page.locator('.exam-task').filter({hasText:tag}).first();await card.waitFor();
   const promise=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/retry'));
   await card.getByRole('button',{name:'重试生成'}).click();const response=await promise;assert.equal(response.status(),202);const job=(await response.json()).edu_job_id;summary.pending_job_id=job;save();
   summary.calls.push({path:new URL(response.url()).pathname,status:response.status()});summary.retries++;let found=false;
   for(let i=0;i<2400;i++){const h=await get('/exam-generations');const next=h.items.find(x=>x.job_id===job);if(next){gid=next.generation_id;found=true;break;}await page.waitForTimeout(500);}
   assert.ok(found);summary.generations.push(gid);save();await page.reload();await page.locator('.exam-task').filter({hasText:tag}).first().waitFor();
  }
  let last='';delete summary.completed;const start=Date.now();
  while(Date.now()-start<1900000){const s=await get('/exam-generations/'+gid);const key=s.status+':'+s.message;if(key!==last){summary.transitions.push({at:new Date().toISOString(),resume_attempt:attempt,...s});last=key;save();console.log(label,s.status,s.message);}if(['succeeded','failed','canceled'].includes(s.status)){summary.completed=s.status==='succeeded';prior=s;break;}await page.waitForTimeout(5000);}
  assert.notEqual(summary.completed,undefined,'No terminal status');if(summary.completed)break;
 }
 await page.goto('http://127.0.0.1/#/exam');const latest=page.locator('.exam-task').filter({hasText:tag}).first();await latest.waitFor();
 if(summary.completed){await latest.getByRole('button',{name:'查看试卷'}).click();await page.getByRole('region',{name:'试卷预览'}).waitFor();summary.questions=await page.locator('section[aria-label="试卷预览"] > article').count();assert.equal(summary.questions,expected);}
 summary.viewports=[];for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});await page.screenshot({path:out+`/online-${width}.png`,fullPage:true});const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);summary.viewports.push({width,overflow});assert.equal(overflow,false);}
 summary.expected_questions=expected;summary.finishedAt=new Date().toISOString();save();assert.deepEqual(summary.errors,[]);console.log('Finished',label,summary.completed,summary.questions);
}catch(e){summary.failure=String(e);save();throw e;}finally{await browser.close();}
