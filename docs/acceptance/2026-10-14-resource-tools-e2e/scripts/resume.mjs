import fs from 'node:fs';
import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import {expect} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test.mjs';
const account=JSON.parse(fs.readFileSync('/tmp/edu-resource-e2e-account.json','utf8'));
const out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-14-resource-tools-e2e';
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
await context.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),{token:account.token,user:account.user});
const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const results=JSON.parse(fs.readFileSync(out+'/generation.json','utf8')).results.filter(r=>r.jobId);
const tools=[['report','学习报告','报告主题'],['quiz','习题','习题主题'],['flashcard','闪卡','闪卡标题'],['graph','思维导图','思维导图主题'],['podcast','播客','播客主题'],['scenario','情景案例','案例主题']];
try{
 await page.goto('http://127.0.0.1/#/classroom/'+account.courseId);
 await page.getByRole('button',{name:'打开生成工具',exact:true}).click();
 await expect(page.locator('.studio-tool-grid button')).toHaveCount(6);
 await page.screenshot({path:out+'/tools.png'});
 for(const [kind,label,field] of tools.filter(([kind])=>!results.some(r=>r.kind===kind))){
  const result={kind,label,startedAt:new Date().toISOString()};results.push(result);
  try{
   await page.locator('.studio-tool-grid button').filter({hasText:label}).click();
   const dialog=page.getByRole('dialog');
   await dialog.getByLabel(field,{exact:false}).fill(`验收·${label}·Python 变量绑定与列表浅拷贝`);
   if(kind==='report'){
    await dialog.getByLabel('报告模板').selectOption('brief');
    await dialog.getByText('更多设置',{exact:true}).click();
    await dialog.getByLabel('补充要求（选填）').fill('使用中文，包含一张比较“别名、浅拷贝、重新赋值”的 Markdown 表格，以及一个带 python 语言标记的代码块和输出说明；不需要配图。');
   }
   if(kind==='quiz'){
    await dialog.getByLabel('题目数量').fill('4');
    for(const label of ['选择题','填空题','简答题','判断题'])await dialog.getByRole('checkbox',{name:label,exact:true}).check();
   }
   if(kind==='flashcard')await dialog.getByLabel('卡片数量').fill('3');
   if(kind==='graph')await dialog.getByLabel('层级深度').fill('3');
   if(kind==='podcast')await dialog.getByLabel('目标时长').selectOption('3');
   if(kind==='scenario'){
    await dialog.getByLabel('难度').selectOption('easy');
    await dialog.getByLabel('情景设定').fill('你在排查购物清单被意外修改的问题，需要在直接赋值、浅拷贝和重新赋值之间做选择。');
   }
   await page.screenshot({path:out+`/config-${kind}.png`});
   const responsePromise=page.waitForResponse(r=>r.url().endsWith('/api/personal-studio/generate')&&r.request().method()==='POST');
   await dialog.getByRole('button',{name:'开始生成',exact:true}).click();
   const response=await responsePromise;result.httpStatus=response.status();
   const data=await response.json();
   if(response.status()!==202)throw new Error(JSON.stringify(data));
   result.jobId=data.edu_job_id;result.initialStatus=data.status;
   await expect(dialog.getByText(/任务已开始/)).toBeVisible();
   console.log(JSON.stringify({phase:'submitted',...result}));
  }catch(e){result.error=String(e);console.log(JSON.stringify({phase:'submission-failed',...result}));}
  fs.writeFileSync(out+'/generation.json',JSON.stringify({results,errors},null,2));
  await page.getByRole('button',{name:'全部工具',exact:true}).click();
 }
 const deadline=Date.now()+15*60*1000;
 while(Date.now()<deadline){
  const response=await context.request.get('http://127.0.0.1/backend/api/personal-studio',{headers:{Authorization:`Bearer ${account.token}`}});
  if(!response.ok())throw new Error(`listing ${response.status()}`);
  const data=await response.json();
  for(const result of results.filter(r=>r.jobId&&!r.done)){
   const job=data.jobs.find(j=>j.edu_job_id===result.jobId);
   if(!job)continue;
   const state=`${job.status}:${job.progress}:${job.message}`;
   if(result.lastState!==state){result.lastState=state;console.log(JSON.stringify({phase:'progress',kind:result.kind,status:job.status,progress:job.progress,message:job.message}));}
   if(['succeeded','failed','partially_succeeded','canceled'].includes(job.status)){
    result.done=true;result.status=job.status;result.seconds=Math.round((Date.now()-Date.parse(result.startedAt))/1000);result.errorCode=job.error_code;result.errorMessage=job.error_message;
    result.resource=data.resources.find(r=>r.material_id===result.jobId);
    fs.writeFileSync(out+`/job-${result.kind}.json`,JSON.stringify(job,null,2));
    console.log(JSON.stringify({phase:'completed',kind:result.kind,status:result.status,seconds:result.seconds,errorCode:result.errorCode}));
   }
  }
  fs.writeFileSync(out+'/generation.json',JSON.stringify({results,errors},null,2));
  if(results.every(r=>!r.jobId||r.done))break;
  await new Promise(r=>setTimeout(r,2000));
 }
 await page.screenshot({path:out+'/generated-list.png'});
 console.log(JSON.stringify({phase:'finished',results:results.map(({kind,status,seconds,error})=>({kind,status,seconds,error})),errors}));
}finally{await browser.close();}
