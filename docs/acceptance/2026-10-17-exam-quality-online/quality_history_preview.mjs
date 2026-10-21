import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';import assert from 'node:assert/strict';
const root='/home/zxqs_ep/Edu_AI',out=root+'/docs/acceptance/2026-10-17-exam-quality-online/history-preview';
const a=JSON.parse(fs.readFileSync(root+'/.runtime/exam-real-paper-e2e/auth.json'));const b=await chromium.launch({headless:true});
try {
 const c=await b.newContext({viewport:{width:1440,height:1000}});
 await c.addInitScript(a=>localStorage.setItem('edu-ai-auth',JSON.stringify(a)),{token:a.token,user:{username:a.username,role:'student'}});
 const p=await c.newPage(),errors=[],results=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto('http://127.0.0.1/#/exam');await p.locator('.exam-task').filter({has:p.getByRole('button',{name:'查看试卷'})}).first().getByRole('button',{name:'查看试卷'}).click();await p.getByRole('region',{name:'试卷预览'}).waitFor();
 assert.equal(await p.locator('section[aria-label="试卷预览"] > article').count(),32);
 assert.equal(await p.locator('section[aria-label="试卷预览"] > article').nth(6).locator(':scope > .exam-option').count(),4);
 for(const width of [1440,390,320]){
  await p.setViewportSize({width,height:1000});
  const overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  results.push({width,overflow});assert.equal(overflow,false);
  await p.screenshot({path:out+`/final-${width}.png`,fullPage:true});
 }
 await p.locator('section[aria-label="试卷预览"] > article').nth(6).scrollIntoViewIfNeeded();
 await p.screenshot({path:out+'/final-mobile-detail.png'});
 assert.deepEqual(errors,[]);fs.writeFileSync(out+'/preview-final.json',JSON.stringify({questions:32,errors,viewports:results,model_calls:0,boundary:'Read-only existing historical 32-question paper on production; not the newly generated paper'},null,2));console.log('Final preview passed',results);
}finally{await b.close();}
