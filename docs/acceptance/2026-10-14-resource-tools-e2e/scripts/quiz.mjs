import fs from 'node:fs';import assert from 'node:assert/strict';
import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import {expect} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test.mjs';
const account=JSON.parse(fs.readFileSync('/tmp/edu-resource-e2e-account.json'));
const out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-14-resource-tools-e2e';
const browser=await chromium.launch();const context=await browser.newContext({viewport:{width:1440,height:1000}});
await context.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),{token:account.token,user:account.user});
const page=await context.newPage();const record={requests:[],errors:[]};page.on('pageerror',e=>record.errors.push(e.message));
page.on('response',async r=>{if(/\/attempts$/.test(r.url())&&r.request().method()==='POST')record.requests.push({status:r.status(),body:await r.json()});});
try{
 await page.goto('http://127.0.0.1/#/classroom/'+account.courseId);
 await page.locator('.sl-directory .sl-resource-row').filter({hasText:'验收·习题'}).click();
 const frame=page.frameLocator('iframe.sl-live-material');
 await expect(frame.locator('.quiz-question-card')).toHaveCount(4,{timeout:30000});
 record.types=await frame.locator('.quiz-question-card header').allTextContents();
 record.inputs=await frame.locator('.quiz-question-card').evaluateAll(nodes=>nodes.map(n=>({radios:n.querySelectorAll('input[type=radio]').length,checkboxes:n.querySelectorAll('input[type=checkbox]').length,textareas:n.querySelectorAll('textarea').length})));
 await page.screenshot({path:out+'/quiz-before.png'});
 const answers=['B','[1, 2]；[1, 2, 3]','b=a 是两个名字指向同一列表，修改列表会彼此可见。b=a.copy() 新建外层列表，但内部嵌套列表仍共享，修改嵌套列表也会影响原列表。','错误'];
 for(let i=0;i<4;i++){
  const card=frame.locator('.quiz-question-card').nth(i);
  if(i===0)await card.locator('input').nth(1).check();else if(i===3&&await card.getByRole('radio').count())await card.getByRole('radio',{name:'错误'}).check();else await card.getByRole('textbox').fill(answers[i]);
  await card.getByRole('button',{name:'提交答案',exact:true}).click();
  await expect(card.locator('.quiz-feedback')).toBeVisible({timeout:100000});
  record.requests[i]??={};
 }
 await page.screenshot({path:out+'/quiz-after.png'});
 await page.reload();await expect(frame.locator('.quiz-saved-answer')).toHaveCount(4,{timeout:30000});
 record.savedAfterReload=true;
 await page.setViewportSize({width:390,height:1000});await page.screenshot({path:out+'/quiz-mobile.png'});
 record.passed=true;
}catch(e){record.passed=false;record.error=String(e);await page.screenshot({path:out+'/quiz-error.png'}).catch(()=>{});}
finally{await browser.close();fs.writeFileSync(out+'/quiz-answer.json',JSON.stringify(record,null,2));console.log(JSON.stringify(record));}
