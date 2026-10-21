import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const root='/home/zxqs_ep/Edu_AI',out=root+'/docs/acceptance/2026-10-17-exam-quality-online';
const auth=JSON.parse(fs.readFileSync(root+'/.runtime/exam-real-paper-e2e/auth.json'));
const summary={boundary:'Production Nginx, real authentication, browser upload, API, durable worker, MinerU and DeepTutor. Dedicated test account.',startedAt:new Date().toISOString(),calls:[],transitions:[],errors:[],retries:0};
const save=()=>fs.writeFileSync(out+'/browser.json',JSON.stringify(summary,null,2));
const browser=await chromium.launch({headless:true});
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(a=>localStorage.setItem('edu-ai-auth',JSON.stringify(a)),{token:auth.token,user:{username:auth.username,role:'student'}});
 const page=await context.newPage();
 page.on('pageerror',e=>{summary.errors.push(e.message);save();});
 page.on('response',async r=>{
  if(!r.url().includes('/api/exam-generations')&&!r.url().includes('/retry'))return;
  const entry={path:new URL(r.url()).pathname,status:r.status(),method:r.request().method()};
  if(entry.method==='POST'&&r.ok()) {try {const d=await r.json();entry.generation_id=d.generation_id;entry.job_id=d.edu_job_id;}catch{}}
  summary.calls.push(entry);save();
 });
 await page.goto('http://127.0.0.1/#/exam');
 await page.getByRole('heading',{name:'用你的资料，准备下一场考试'}).waitFor({timeout:30000});
 await page.locator('input[type=file]').setInputFiles(root+'/.runtime/exam-real-paper-e2e/source.pdf');
 await page.getByText('source.pdf',{exact:true}).waitFor();
 await page.getByRole('textbox',{name:'出题要求'}).fill('性能与质量上线复测：依据整份原卷生成新的数据结构模拟试卷，保持原题顺序、题型和对应考点，保留子题结构，使用新的有效数据，不照抄原题。');
 await page.getByRole('button',{name:'生成模拟试卷',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('.exam-task')?.textContent.includes('性能与质量上线复测'),{},{timeout:30000});
 await page.screenshot({path:out+'/submitted.png',fullPage:true});
 await page.reload();summary.refresh_recovery=true;save();
 for(let attempt=0;attempt<2;attempt++) {
  const start=Date.now();let last='';
  while(Date.now()-start<1800000) {
   const card=page.locator('.exam-task').first();const txt=await card.innerText();
   if(txt!==last){summary.transitions.push({at:new Date().toISOString(),attempt,text:txt});last=txt;save();console.log(attempt,txt.replaceAll('\n',' ').slice(-150));}
   if(await card.getByRole('button',{name:'查看试卷'}).count()){
    await card.getByRole('button',{name:'查看试卷'}).click();summary.completed=true;break;
   }
   if(await card.getByRole('button',{name:'重试生成'}).count()){
    if(attempt===1){summary.completed=false;break;}
    await card.getByRole('button',{name:'重试生成'}).click();summary.retries++;save();await page.waitForTimeout(5000);break;
   }
   await page.waitForTimeout(3000);
  }
  if(summary.completed!==undefined)break;
 }
 if(summary.completed){
  await page.getByRole('region',{name:'试卷预览'}).waitFor({timeout:15000});
  summary.questions=await page.locator('section[aria-label="试卷预览"] > article').count();assert.equal(summary.questions,32);
 }
 summary.viewports=[];
 for(const width of [1440,390,320]){
  await page.setViewportSize({width,height:1000});await page.screenshot({path:out+`/browser-${width}.png`,fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);summary.viewports.push({width,overflow});assert.equal(overflow,false);
 }
 summary.finishedAt=new Date().toISOString();save();assert.deepEqual(summary.errors,[]);console.log('Finished',summary.completed,summary.questions);
}catch(e){summary.failure=String(e);save();throw e;}finally{await browser.close();}
