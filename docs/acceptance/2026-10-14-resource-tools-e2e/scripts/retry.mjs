import fs from 'node:fs';
import assert from 'node:assert/strict';
import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
const account=JSON.parse(fs.readFileSync('/tmp/edu-resource-e2e-account.json'));
const out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-14-resource-tools-e2e';
const old=JSON.parse(fs.readFileSync(out+'/job-scenario.json'));
const browser=await chromium.launch();const context=await browser.newContext({viewport:{width:1440,height:1000}});
await context.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),{token:account.token,user:account.user});
const page=await context.newPage();
try{
 await page.goto('http://127.0.0.1/#/my-resources');
 await page.locator('.studio-history summary').click();
 await page.screenshot({path:out+'/scenario-failure.png'});
 const pending=page.waitForResponse(r=>r.url().endsWith(`/api/jobs/${old.edu_job_id}/retry`)&&r.request().method()==='POST');
 await page.locator('.studio-history').getByRole('button',{name:'重试',exact:true}).click();
 const response=await pending;assert(response.ok());let job=await response.json();
 console.log(JSON.stringify({phase:'retry-submitted',jobId:job.edu_job_id,retryOf:job.retry_of_job_id}));
 for(let i=0;i<150;i++){
  const response=await context.request.get(`http://127.0.0.1/backend/api/jobs/${job.edu_job_id}`,{headers:{Authorization:`Bearer ${account.token}`}});assert(response.ok());job=await response.json();
  if(['succeeded','failed','canceled','partially_succeeded'].includes(job.status))break;
  await new Promise(r=>setTimeout(r,2000));
 }
 fs.writeFileSync(out+'/scenario-retry.json',JSON.stringify(job,null,2));
 console.log(JSON.stringify({phase:'retry-complete',jobId:job.edu_job_id,status:job.status,errorCode:job.error_code}));
}finally{await browser.close();}
