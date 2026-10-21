import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const root='/home/zxqs_ep/Edu_AI';
const [name, expectedText, label=name]=process.argv.slice(2);
const expected=Number(expectedText), source=root+'/.runtime/exam-multi-pdf-20261018/'+name+'.pdf';
const out=root+'/docs/acceptance/2026-10-18-exam-multi-pdf/'+label;fs.mkdirSync(out,{recursive:true});
const auth=JSON.parse(fs.readFileSync(root+'/.runtime/exam-real-paper-e2e/auth.json'));
const base='http://127.0.0.1',api=base+'/backend/api',tag='多PDF验收 '+label+' '+Date.now();
const summary={boundary:'Production browser upload, real authentication, Nginx, durable worker, MinerU and DeepTutor',tag,startedAt:new Date().toISOString(),calls:[],transitions:[],errors:[],generations:[],retries:0};
const save=()=>fs.writeFileSync(out+'/online-browser.json',JSON.stringify(summary,null,2));
const browser=await chromium.launch({headless:true});
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(a=>localStorage.setItem('edu-ai-auth',JSON.stringify(a)),{token:auth.token,user:{username:auth.username,role:'student'}});
 const request=async path=>{const r=await context.request.get(api+path,{headers:{Authorization:'Bearer '+auth.token}});assert.equal(r.status(),200);return r.json();};
 const page=await context.newPage();page.on('pageerror',e=>{summary.errors.push(e.message);save();});
 page.on('response',async r=>{if(r.request().method()==='POST'&&(r.url().includes('/exam-generations')||r.url().includes('/retry'))){summary.calls.push({path:new URL(r.url()).pathname,status:r.status()});save();}});
 await page.goto(base+'/#/exam');
 await page.getByRole('heading',{name:'用你的资料，准备下一场考试'}).waitFor({timeout:30000});
 await page.locator('input[type=file]').setInputFiles(source);
 await page.getByText(name+'.pdf',{exact:true}).waitFor();
 await page.getByRole('textbox',{name:'出题要求'}).fill(tag+'：依据整份原卷生成新的数据结构模拟试卷，保持原题顺序、题型和对应考点，保留子题结构；不把考场信息、签名、考试说明当成知识考题，使用新的有效数据，不照抄原题。');
 const submission=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/api/exam-generations'));
 await page.getByRole('button',{name:'生成模拟试卷',exact:true}).click();
 const submitted=await submission;assert.equal(submitted.status(),202);let gid=(await submitted.json()).generation_id;
 await page.reload();await page.locator('.exam-task').filter({hasText:tag}).first().waitFor();summary.refresh_recovery=true;
 for(let attempt=0;attempt<2;attempt++) {
  summary.generations.push(gid);delete summary.completed;save();let last='';const started=Date.now();
  while(Date.now()-started<1900000){
   const status=await request('/exam-generations/'+gid);const signature=status.status+':'+status.message;
   if(signature!==last){summary.transitions.push({at:new Date().toISOString(),attempt,...status});save();last=signature;console.log(attempt,status.status,status.message);}
   if(['succeeded','failed','canceled'].includes(status.status)){summary.completed=status.status==='succeeded';break;}
   await page.waitForTimeout(5000);
  }
  assert.notEqual(summary.completed,undefined,'Generation did not reach terminal status');
  if(summary.completed||attempt===1)break;
  await page.reload();const card=page.locator('.exam-task').filter({hasText:tag}).first();
  const retryResponse=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/retry'));
  await card.getByRole('button',{name:'重试生成'}).click();const response=await retryResponse;assert.equal(response.status(),202);
  const job=(await response.json()).edu_job_id;summary.pending_job_id=job;summary.retries++;delete summary.completed;save();
  let found=false;for(let i=0;i<2400;i++){const history=await request('/exam-generations');const next=history.items.find(x=>x.job_id===job);if(next){gid=next.generation_id;found=true;break;}await page.waitForTimeout(500);}
  assert.ok(found,'Retry generation not materialized');
 }
 await page.reload();const card=page.locator('.exam-task').filter({hasText:tag}).first();await card.waitFor();
 if(summary.completed){await card.getByRole('button',{name:'查看试卷'}).click();await page.getByRole('region',{name:'试卷预览'}).waitFor();summary.questions=await page.locator('section[aria-label="试卷预览"] > article').count();assert.equal(summary.questions,expected);}
 summary.viewports=[];
 for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});await page.screenshot({path:out+`/online-${width}.png`,fullPage:true});const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);summary.viewports.push({width,overflow});assert.equal(overflow,false);}
 summary.expected_questions=expected;summary.source=name;summary.finishedAt=new Date().toISOString();save();assert.deepEqual(summary.errors,[]);console.log('Finished',summary.completed,summary.questions);
} catch(e){summary.failure=String(e);save();throw e;} finally {await browser.close();}
