import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const root='/home/zxqs_ep/Edu_AI',a=JSON.parse(fs.readFileSync(root+'/.runtime/exam-real-paper-e2e/auth.json'));
const browser=await chromium.launch({headless:true});
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),{token:a.token,user:{username:a.username,role:'student'}});
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1/#/exam');await page.getByText('考试模拟即将上线，开放后可在这里查看已生成的考试。').waitFor({timeout:20000});
 await page.screenshot({path:root+'/docs/acceptance/2026-10-17-exam-real-paper-e2e/online-exam.png',fullPage:true});
 const result={url:page.url(),placeholder:true,type_selector_disabled:await page.getByRole('combobox',{name:'考试题型'}).isDisabled(),errors};
 fs.writeFileSync(root+'/docs/acceptance/2026-10-17-exam-real-paper-e2e/page.json',JSON.stringify(result,null,2));console.log(result);
} finally {await browser.close();}
