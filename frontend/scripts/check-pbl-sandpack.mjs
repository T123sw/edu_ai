import {performance} from 'node:perf_hooks';
import {isDeepStrictEqual} from 'node:util';
import {browserHost} from './pbl-browser-host.mjs';
import {checkNativeProject} from './check-pbl-native.mjs';
import {runUiCheck} from './pbl-ui-check.mjs';
class RuntimeUnavailable extends Error {}
export async function checkSandpackProject({files,checks,runtime}){
 const started=performance.now();
 if(!files||!Object.keys(files).length||Object.keys(files).length>32||Object.values(files).some(x=>typeof x!=='string')||Buffer.byteLength(JSON.stringify(files))>1048576||!Array.isArray(checks)||!checks.length||checks.length>64)throw new Error('Invalid project input');
 if(!['react','react-ts','vanilla','vanilla-ts','vue','svelte','static','node'].includes(runtime.template)||!Object.hasOwn(files,runtime.entry))throw new Error('Invalid runtime');
 const host=await browserHost('src/pbl/runtime/SandpackPreviewHarness.tsx'),results=[];
 const fail=(id,message)=>({caseId:id,status:'failed',message:String(message).slice(0,2000)});
 const native=checks.filter(c=>c.engine==='sandpack-jest');
 async function launchOnce(check={}){
  const context=await host.newContext({bypassCSP:check.engine==='http',viewport:check.viewport==='mobile'?{width:390,height:844}:{width:1280,height:800}});
  const page=await context.newPage();context.setDefaultTimeout(1800);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));if(process.env.PBL_RUNTIME_TRACE){page.on('requestfailed',r=>console.error('request failed',r.url().split('?')[0],r.failure()?.errorText));page.on('console',m=>{if(m.type()==='error'||m.text().startsWith('PBL_RUNTIME:'))console.error(m.text().slice(0,1200))});}page.on('dialog',d=>void d.dismiss());
  try{
   await page.goto(host.origin,{timeout:10000});await page.evaluate(input=>window.startPblPreview(input),{files,runtime});
   await page.waitForFunction(()=>window.pblPreviewState?.status==='timeout'||window.pblPreviewState?.error||(window.pblPreviewState?.clients.length&&window.pblPreviewState.clients.every(x=>x==='done')),undefined,{timeout:75000});
   const state=await page.evaluate(()=>window.pblPreviewState);if(state.status==='timeout'||/Failed to get shell by ID/.test(state.error||''))throw new RuntimeUnavailable('Sandpack 运行环境暂未连接成功，请重试');if(state.error)throw new Error(state.error);
   const handle=await page.locator('.sp-preview iframe:not(.sp-bridge-frame)').elementHandle(),frame=await handle.contentFrame();
   if(!frame||frame.url()==='about:blank')throw new Error('预览尚未启动');
   await frame.waitForLoadState('domcontentloaded',{timeout:10000});return{context,page,frame,errors};
  }catch(error){if(process.env.PBL_RUNTIME_TRACE)console.error('preview failure',await page.evaluate(()=>({state:window.pblPreviewState,body:document.body.innerText})));await context.close();if(error.name==='TimeoutError')throw new RuntimeUnavailable('Sandpack 运行环境启动超时，请重试');throw error}
 }
 async function launch(check={}){
  try{return await launchOnce(check)}
  catch(error){
   if(!(error instanceof RuntimeUnavailable))throw error;
   // Retry only an unavailable sandbox, with a new context and unchanged code.
   // Compilation or assertion failures never take this path or spend model calls.
   return launchOnce(check);
  }
 }
 try{
  if(native.length){
   let instance;
   try{instance=await launch();if(instance.errors.length)throw new Error(instance.errors.join('\n'))}
   catch(error){if(error instanceof RuntimeUnavailable)throw error;return{passed:false,results:checks.map(c=>fail(c.id,'工程未能运行：'+error.message)),durationMs:performance.now()-started}}
   finally{await instance?.context.close()}
   const report=await checkNativeProject({files,checks:native,runtime});results.push(...report.results);
  }
  const scenarios=checks.filter(c=>c.engine!=='sandpack-jest');let cursor=0;
  const executions=await Promise.allSettled(Array.from({length:Math.min(2,scenarios.length)},async()=>{
   while(cursor<scenarios.length){const check=scenarios[cursor++];
   let instance;
   try{
    instance=await launch(check);
    if(check.engine==='http'){
     if(runtime.template!=='node')throw new Error('HTTP 验收需要 Node 模板');
     if(check.requests.some(request=>request.body!=null))throw new Error('当前 Nodebox 的请求体传输不可用，暂不支持带请求体的 HTTP 验收（上游 sandpack#1190）。');
     const trace=[];
     for(const req of check.requests){
      if(!req.path.startsWith('/')||req.path.startsWith('//')||req.path.includes('\\'))throw new Error('请求只能访问当前服务');
      const response=await instance.frame.evaluate(async input=>{
       const url=new URL(input.path,location.origin);if(url.origin!==location.origin)throw new Error('禁止跨服务请求');
       const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
       try{const response=await fetch(url,{method:input.method,redirect:'error',headers:input.body==null?{}:{'content-type':'application/json'},...(input.body==null?{}:{body:JSON.stringify(input.body)}),signal:controller.signal});const text=await response.text();return{status:response.status,text:text.slice(0,65536)}}finally{clearTimeout(timer)}
      },req);
      trace.push(`${req.method} ${req.path} → ${response.status}`);
      if(response.status!==req.status)throw new Error(trace.join('\n')+`\n预期状态 ${req.status}`);
      if(req.text!=null&&response.text!==req.text)throw new Error(trace.join('\n')+`\n预期文本 ${JSON.stringify(req.text)}，实际 ${JSON.stringify(response.text)}`);
      if(req.jsonBody!=null){let value;try{value=JSON.parse(response.text)}catch{throw new Error('响应不是 JSON：'+response.text)}if(!isDeepStrictEqual(value,req.jsonBody))throw new Error(trace.join('\n')+`\n预期 JSON ${JSON.stringify(req.jsonBody)}，实际 ${JSON.stringify(value)}`)}
     }
     results.push({caseId:check.id,status:'passed',message:trace.join('\n').slice(0,2000)});
    }else results.push(await runUiCheck(instance.frame,check,async()=>{},instance.errors));
   }catch(error){if(error instanceof RuntimeUnavailable)throw error;results.push(fail(check.id,error.message))}
   finally{await instance?.context.close()}
  }
  }));
  const unavailable=executions.find(result=>result.status==='rejected');if(unavailable)throw unavailable.reason;
  const ordered=checks.map(c=>results.find(r=>r.caseId===c.id)||fail(c.id,'未执行检查'));
  return{passed:ordered.every(r=>r.status==='passed'),results:ordered,durationMs:performance.now()-started};
 }finally{await host.close()}
}
