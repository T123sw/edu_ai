import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';import assert from 'node:assert/strict';
const root='/home/zxqs_ep/Edu_AI',out=root+'/docs/acceptance/2026-10-17-exam-evidence-fix';
const auth=JSON.parse(fs.readFileSync(root+'/.runtime/exam-real-paper-e2e/auth.json'));
const previous=JSON.parse(fs.readFileSync(out+'/online-browser.json'));const tag=previous.tag;
const summary={boundary:'Second explicit production page retry; same uploaded PDF and request lineage',tag,startedAt:new Date().toISOString(),transitions:[],errors:[]};
const save=()=>fs.writeFileSync(out+'/online-retry2.json',JSON.stringify(summary,null,2));
const browser=await chromium.launch({headless:true});
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}});await context.addInitScript(a=>localStorage.setItem('edu-ai-auth',JSON.stringify(a)),{token:auth.token,user:{username:auth.username,role:'student'}});
 const page=await context.newPage();page.on('pageerror',e=>summary.errors.push(e.message));
 const get=async path=>{const r=await context.request.get('http://127.0.0.1/backend/api'+path,{headers:{Authorization:'Bearer '+auth.token}});assert.equal(r.status(),200);return r.json();};
 await page.goto('http://127.0.0.1/#/exam');const card=page.locator('.exam-task').filter({hasText:tag}).first();await card.waitFor();
 const promise=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/retry'));await card.getByRole('button',{name:'重试生成'}).click();const response=await promise;summary.retry_http=response.status();assert.equal(response.status(),202);summary.job_id=(await response.json()).edu_job_id;save();
 for(let i=0;i<120;i++){const d=await get('/exam-generations');const row=d.items.find(x=>x.job_id===summary.job_id);if(row){summary.generation_id=row.generation_id;break;}await page.waitForTimeout(500);}
 assert.ok(summary.generation_id);await page.reload();let last='';const start=Date.now();
 while(Date.now()-start<1900000){const s=await get('/exam-generations/'+summary.generation_id);const k=s.status+':'+s.message;if(k!==last){summary.transitions.push({at:new Date().toISOString(),...s});last=k;save();console.log(s.status,s.message);}if(['succeeded','failed','canceled'].includes(s.status)){summary.completed=s.status==='succeeded';break;}await page.waitForTimeout(3000);}
 assert.notEqual(summary.completed,undefined);await page.reload();const latest=page.locator('.exam-task').filter({hasText:tag}).first();await latest.waitFor();
 if(summary.completed){await latest.getByRole('button',{name:'查看试卷'}).click();await page.getByRole('region',{name:'试卷预览'}).waitFor();summary.questions=await page.locator('section[aria-label="试卷预览"] > article').count();assert.equal(summary.questions,32);}
 summary.viewports=[];for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});await page.screenshot({path:out+`/online-retry2-${width}.png`,fullPage:true});const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);summary.viewports.push({width,overflow});assert.equal(overflow,false);}
 summary.finishedAt=new Date().toISOString();save();assert.deepEqual(summary.errors,[]);console.log('Finished',summary.completed,summary.questions);
} catch(e){summary.failure=String(e);save();throw e;} finally {await browser.close();}
