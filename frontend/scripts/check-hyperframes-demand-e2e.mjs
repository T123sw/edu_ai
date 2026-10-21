import {chromium} from 'playwright';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const evidence='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-18-hyperframes-demand-e2e';
const privateDir='/tmp/edu-hyperframes-demand-e2e';
const output='/home/zxqs_ep/data/main-review/hyperframes-demand-e2e';
for(const d of [evidence,output])await mkdir(d,{recursive:true});await mkdir(privateDir,{recursive:true,mode:0o700});
const credentials=JSON.parse(await readFile('/tmp/edu-hyperframes-online/credentials.json','utf8'));
const base='http://127.0.0.1';
const goal='我是一名初中生，会读平面直角坐标图，但不理解一次函数 y=2x+b 中 b 的作用。请为我制作一节中文微课，只安排一个知识点：截距如何让直线上下平移。学习总时长约 3 分钟，其中动画讲解约 60—90 秒，配中文语音。请在同一坐标系中动态展示 b=0、b=2、b=-2，解释与 y 轴交点怎样变化、为什么斜率始终是 2。最后保留一份简短讲义和两道检查理解的练习。不要扩展到神经网络或其他章节。生成后保存课程，方便我反复观看。';
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000},...(process.env.HF_RESUME==='1'?{storageState:`${privateDir}/browser-state.json`}:{})});
const page=await context.newPage();
const errors=[],failures=[],events=[];
const sanitize=s=>String(s).replace(/(\/hyperframes\/projects\/)[^/]+/g,'$1[ticket]');
page.on('pageerror',e=>errors.push(sanitize(e.message)));
page.on('response',r=>{if(r.status()>=400)failures.push({path:sanitize(new URL(r.url()).pathname),status:r.status()})});
const save=async(name,data)=>writeFile(`${evidence}/${name}.json`,JSON.stringify(data,null,2));
let task;
try{
 await page.goto(base+'/',{waitUntil:'domcontentloaded'});
 if(process.env.HF_RESUME!=='1'){await page.getByLabel('账号',{exact:true}).fill(credentials.username);await page.getByLabel('密码',{exact:true}).fill(credentials.password);await page.getByRole('button',{name:/^登\s*录$/}).click();}
 await page.getByLabel('学习知识点与目标').waitFor({timeout:60000});
 const auth=await page.evaluate(()=>JSON.parse(localStorage.getItem('edu-ai-auth')));await writeFile(`${privateDir}/auth.json`,JSON.stringify(auth),{mode:0o600});
 const headers={Authorization:`Bearer ${auth.token}`};
 if(process.env.HF_RESUME==='1'){
  task=JSON.parse(await readFile(`${evidence}/accepted.json`,'utf8'));const retry=page.getByRole('button',{name:/^(继续重试|补齐未完成内容)$/});await retry.waitFor({timeout:30000});await page.screenshot({path:`${evidence}/resume-before-retry.png`});const pending=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/'+task.preparation_id+'/retry'));await retry.click();const retried=await pending;assert.ok(retried.ok());task=await retried.json();await save('retry-accepted',task);console.log(JSON.stringify({phase:'retried-from-frontend',attempt:task.attempt_no}));
 }else{
  await page.getByLabel('学习知识点与目标').fill(goal);assert.equal(await page.getByRole('switch',{name:'生成 AI 课堂'}).getAttribute('aria-checked'),'true');
  await page.screenshot({path:`${evidence}/01-demand.png`});
  const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/backend/api/course-preparations');
  await page.getByRole('button',{name:'开始学习',exact:true}).click();const response=await pending;assert.equal(response.status(),202);task=await response.json();await save('request',response.request().postDataJSON());await save('accepted',task);await writeFile(`${output}/需求.txt`,goal+'\n');
  await page.screenshot({path:`${evidence}/02-accepted.png`});console.log(JSON.stringify({phase:'submitted-from-frontend',preparation_id:task.preparation_id}));
 }
 let last='';const deadline=Date.now()+3600000;
 while(Date.now()<deadline){
  const r=await context.request.get(`${base}/backend/api/course-preparations/${task.preparation_id}`,{headers});assert.equal(r.status(),200);task=await r.json();await save('status',task);
  const signature=JSON.stringify([task.status,task.stage,task.error_code]);
  if(signature!==last){const e={at:new Date().toISOString(),status:task.status,stage:task.stage,error_code:task.error_code};events.push(e);await save('events',events);console.log(JSON.stringify(e));await page.screenshot({path:`${evidence}/stage-${events.length}-${task.stage}.png`});last=signature;}
  if(['succeeded','failed','canceled'].includes(task.status))break;
  await page.waitForTimeout(10000);
 }
 const r=await context.request.get(`${base}/backend/api/course-preparations/${task.preparation_id}/intermediates`,{headers});if(r.ok())await save('intermediates',await r.json());
 await page.screenshot({path:`${evidence}/03-generation-result.png`});
 assert.equal(task.status,'succeeded',JSON.stringify({status:task.status,stage:task.stage,error_code:task.error_code,result_ref:task.result_ref}));assert.equal(task.result_ref.course_ready,true);
 await page.getByRole('button',{name:'进入课堂',exact:true}).click({timeout:30000});await page.waitForTimeout(3000);await page.screenshot({path:`${evidence}/04-entered-course.png`});
 const course=task.result_ref.course_id;const roomResponse=await context.request.get(`${base}/backend/api/self-learning/courses/${course}`,{headers});assert.equal(roomResponse.status(),200);await save('room',await roomResponse.json());
 await save('generation-complete',{status:'passed',course_id:course,preparation_id:task.preparation_id,url:page.url(),errors,failures});console.log(JSON.stringify({status:'generation-complete',course_id:course,url:page.url()}));
}catch(e){await page.screenshot({path:`${evidence}/failure.png`}).catch(()=>{});await save('failure',{message:sanitize(e.message),errors,failures});console.error(sanitize(e.message));process.exitCode=1;}
finally{await save('browser-events',{errors,failures});await context.storageState({path:`${privateDir}/browser-state.json`});await browser.close();}
