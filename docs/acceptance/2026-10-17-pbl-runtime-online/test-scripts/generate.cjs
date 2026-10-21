const {chromium,request}=require('/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright');
const fs=require('fs'),crypto=require('crypto'),assert=require('assert/strict');
const dir='/tmp/pbl-runtime-online-private',evidence='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-runtime-online';
const topics=[
 ['vanilla-live','使用原生 HTML、CSS 和 JavaScript 做一个本地温度换算器，不使用 React 或其他框架，分两步：第一步输入摄氏温度点击换算后显示华氏温度，0 摄氏显示 32；第二步增加重置按钮恢复空输入和空结果。输入与转换逻辑拆到不同文件，不用外部 API。','vanilla'],
 ['node-live','使用 Node.js 和 Express 做一个无请求体的 HTTP 查询服务，分两步：第一步 GET /health 返回 JSON {status:"ok"}；第二步 GET /square?n=数字 返回 JSON {result:平方值}，缺少 n 或不是有效数字时返回 400 和 JSON {error:"invalid n"}。只使用 GET，不用 POST、数据库或网络，计算函数与路由分文件。','node'],
 ['vue-live','使用 Vue 3 做一个本地活动报名页，不使用 React，分两步：第一步姓名为空或仅空格时禁用报名按钮；第二步提交有效姓名后显示报名成功和姓名，点击重新填写清空输入与结果。不要网络和后端。','vue'],
 ['ts-live','使用 React 和 TypeScript 做一个本地打字统计器，分两步：第一步输入文本即时显示包含空格的字符数，初始 0；第二步增加清空按钮，清空后输入为空、数量为 0。统计逻辑拆成独立 TypeScript 文件，不要网络。','react-ts'],
];
(async()=>{
 const api=await request.newContext({baseURL:'http://127.0.0.1'});
 const credentials={username:'pbl_runtime_online_'+Date.now(),password:crypto.randomBytes(24).toString('hex'),role:'student'};
 let r=await api.post('/backend/api/auth/register',{data:credentials});assert.ok(r.ok(),'register '+r.status());
 r=await api.post('/backend/api/auth/login',{data:credentials});assert.ok(r.ok(),'login '+r.status());const auth=await r.json();
 fs.writeFileSync(dir+'/credentials.json',JSON.stringify(credentials),{mode:0o600});fs.writeFileSync(dir+'/auth.json',JSON.stringify(auth),{mode:0o600});
 const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000}});await context.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),auth);
 const results=[];let cursor=0;
 try{await Promise.all(Array.from({length:2},async()=>{
  while(cursor<topics.length){const [name,topic,template]=topics[cursor++];const page=await context.newPage();
   try{
    await page.goto('http://127.0.0.1/#/practice/code');await page.getByPlaceholder('描述你想完成的网页项目、需要的功能，以及希望练习的知识').fill(topic);
    const response=page.waitForResponse(r=>r.url().endsWith('/api/pbl')&&r.request().method()==='POST');await page.getByRole('button',{name:'生成项目',exact:true}).click();const created=await(await response).json();const start=Date.now();console.log(name,'submitted',created.exerciseId);let detail;
    for(let i=0;i<300;i++){
     const response=await api.get('/backend/api/pbl/'+created.exerciseId,{headers:{Authorization:'Bearer '+auth.token}});assert.ok(response.ok(),'detail '+response.status());detail=await response.json();
     if(detail.artifact||['failed','canceled','cancelled'].includes(detail.job?.status))break;
     if(i%6===0)console.log(name,detail.job?.status,detail.job?.message);
     await page.waitForTimeout(5000);
    }
    const row={name,id:created.exerciseId,seconds:Math.round((Date.now()-start)/1000),success:!!detail.artifact,template:detail.artifact?.runtime?.template,status:detail.job?.status,error:detail.job?.error_message||detail.job?.error,steps:detail.artifact?.tasks.length,checks:detail.artifact?.checks.length};
    results.push(row);fs.writeFileSync(evidence+'/generation.json',JSON.stringify(results,null,2));fs.writeFileSync(dir+'/'+name+'-detail.json',JSON.stringify(detail),{mode:0o600});
    if(detail.artifact){assert.equal(detail.artifact.runtime.template,template);assert.ok(!JSON.stringify(detail).includes('referenceFiles'));fs.writeFileSync(dir+'/'+name+'-artifact.json',JSON.stringify(detail.artifact),{mode:0o600});await page.goto('http://127.0.0.1/#/practice/code/'+created.exerciseId);await page.getByRole('heading',{name:detail.artifact.tasks[0].title,exact:true}).waitFor({timeout:30000});}
    await page.screenshot({path:evidence+'/'+name+'-generated.png',fullPage:true});console.log(JSON.stringify(row));
   }finally{await page.close()}
  }
 }))}finally{await browser.close();await api.dispose()}
 if(results.length!==topics.length||results.some(r=>!r.success))process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
