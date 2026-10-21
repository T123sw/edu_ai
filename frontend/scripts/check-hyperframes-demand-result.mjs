import {chromium} from 'playwright';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const ev='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-18-hyperframes-demand-e2e';
const out='/home/zxqs_ep/data/main-review/hyperframes-demand-e2e';
const priv='/tmp/edu-hyperframes-demand-e2e';const base='http://127.0.0.1';
const task=JSON.parse(await readFile(`${ev}/status.json`,'utf8'));assert.equal(task.status,'succeeded');
const auth=JSON.parse(await readFile(`${priv}/auth.json`,'utf8'));const headers={Authorization:`Bearer ${auth.token}`};
const course=task.result_ref.course_id;await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true});const context=await browser.newContext({storageState:`${priv}/browser-state.json`,viewport:{width:1440,height:1000}});
const errors=[],failures=[];const sanitize=s=>String(s).replace(/(\/hyperframes\/projects\/)[^/]+/g,'$1[ticket]');
context.on('page',p=>{p.on('pageerror',e=>errors.push(sanitize(e.message)));p.on('response',r=>{if(r.status()>=400)failures.push({path:sanitize(new URL(r.url()).pathname),status:r.status()})})});
await context.addInitScript(()=>{window.audioMeters=[];const original=AudioNode.prototype.connect;AudioNode.prototype.connect=function(dest,...args){if(dest===this.context.destination){const m=this.context.createAnalyser();window.audioMeters.push(m);original.call(m,dest);return original.call(this,m,...args)}return original.call(this,dest,...args)}});
const p=await context.newPage();const checks=[],downloads=[],materials=[];
const save=async(name,data)=>writeFile(`${ev}/${name}.json`,JSON.stringify(data,null,2));
const check=(name,data={})=>{checks.push({name,...data});console.log(JSON.stringify({name,...data}))};
try{
 const r=await context.request.get(`${base}/backend/api/self-learning/courses/${course}`,{headers});assert.equal(r.status(),200);const room=await r.json();await save('room',room);
 await p.goto(`${base}/#/classroom/${course}`);await p.locator('.sl-resource-row').first().waitFor({timeout:60000});await p.screenshot({path:`${ev}/05-course-library.png`});
 for(const chapter of room.chapters){
  for(const resource of chapter.resources.filter(r=>r.ready&&r.remote)){
   const ref=resource.remote;const response=await context.request.get(`${base}/backend/api/self-learning/courses/${course}/materials/${ref.materialType}/${ref.materialId}/versions/${ref.version}`,{headers});assert.equal(response.status(),200);const m=await response.json();materials.push({chapter,resource,material:m});
   await save(`material-${ref.materialType}-${ref.materialId}`,m);await writeFile(`${out}/${ref.materialType}-${ref.materialId}.json`,JSON.stringify(m,null,2));
   await p.locator('.sl-resource-row').nth(room.chapters.flatMap(c=>c.resources).findIndex(r=>r.id===resource.id)).click();await p.waitForTimeout(1200);await p.screenshot({path:`${ev}/resource-${ref.materialType}-${ref.materialId}.png`});
   check('saved-resource-opened',{type:ref.materialType,title:resource.title,version:ref.version});
   if(ref.materialType==='report'){
    const text=typeof m.content==='string'?m.content:m.content?.markdown||m.markdown||JSON.stringify(m.content,null,2);await writeFile(`${out}/讲义.md`,text+'\n');
   }
  }
 }
 const classrooms=materials.filter(x=>x.resource.remote.materialType==='classroom');assert.ok(classrooms.length>0,'fresh classroom is required');
 for(let n=0;n<classrooms.length;n++){
  const {resource,material,chapter}=classrooms[n];const content=material.content;assert.equal(content.format,'hyperframes/v1');const suffix=classrooms.length>1?`-${n+1}`:'';
  await p.locator('.sl-resource-row').nth(room.chapters.flatMap(c=>c.resources).findIndex(r=>r.id===resource.id)).click();const frame=p.frameLocator('iframe').first();const player=frame.locator('hyperframes-player');await player.waitFor({timeout:60000});
  await player.evaluate(async p=>{const end=Date.now()+60000;while(!p.ready||!p.assetsReady){if(Date.now()>end)throw Error('native classroom not ready');await new Promise(r=>setTimeout(r,100))}});await p.waitForTimeout(600);
  await writeFile(`${out}/讲稿与时间轴${suffix}.json`,JSON.stringify(content.timeline,null,2));
  await player.evaluate(p=>{p.pause();p.seek(0)});await p.waitForTimeout(400);await player.locator('button').first().click();
  const native=p.frames().find(f=>f.url().includes('/api/hyperframes/projects/')&&f.url().includes('/index.html'));assert.ok(native);
  const a=await native.waitForFunction(()=>{const ms=window.audioMeters.map(m=>{const d=new Float32Array(m.fftSize);m.getFloatTimeDomainData(d);return{state:m.context.state,rms:Math.sqrt(d.reduce((sum,v)=>sum+v*v,0)/d.length)}});return ms.some(m=>m.state==='running'&&m.rms>.0001)?ms:false},{},{timeout:15000});check('new-video-audio-signal',{duration:content.timeline.duration,audio:await a.jsonValue()});
  await p.screenshot({path:`${ev}/new-video-playing${suffix}.png`});await player.evaluate(p=>p.pause());
  for(const [label,name] of [['下载 MP4',`lesson${suffix}.mp4`],['下载 SRT',`lesson${suffix}.srt`],['下载 HTML 项目 ZIP',`project${suffix}.zip`]]){
   const wait=p.waitForEvent('download');await frame.getByRole('link',{name:label,exact:true}).click();const d=await wait;assert.equal(await d.failure(),null);await d.saveAs(`${out}/${name}`);const bytes=await readFile(`${out}/${name}`);downloads.push({file:name,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});
  }
  for(let i=0;i<content.timeline.segments.length;i++){
   const segment=content.timeline.segments[i];const at=(segment.start+segment.end)/2;
   await player.evaluate((p,t)=>{p.pause();p.seek(t)},at);await p.waitForTimeout(400);await player.locator('button').first().click();
   const signal=await native.waitForFunction(()=>{let max=0;for(const m of window.audioMeters){const d=new Float32Array(m.fftSize);m.getFloatTimeDomainData(d);max=Math.max(max,Math.sqrt(d.reduce((s,v)=>s+v*v,0)/d.length))}return max>.0001?max:false},{},{timeout:10000});
   check('segment-audio-and-picture',{segment:segment.id,seconds:await player.evaluate(p=>p.currentTime),rms:await signal.jsonValue()});
   await player.evaluate(p=>p.pause());await p.waitForTimeout(400);await p.screenshot({path:`${ev}/new-segment${suffix}-${i+1}.png`});
  }
  check('new-project-browser-downloads',{segments:content.timeline.segments.length});
  const target=content.timeline.segments[Math.min(1,content.timeline.segments.length-1)];await player.evaluate((p,t)=>p.seek(t),target.start+Math.min(3,(target.end-target.start)/2));await p.waitForTimeout(400);await player.locator('button').first().click();await p.waitForTimeout(900);
  const question='结合我当前播放到的讲解，为什么 b 变大时直线向上移动，但斜率还是 2？请用一个 x 的取值解释，并引用当前片段。';
  await p.getByRole('textbox',{name:'向学习 Agent 提问'}).fill(question);const pending=p.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/agent-turns'));await p.getByRole('button',{name:'发送问题',exact:true}).click();const body=(await pending).postDataJSON();assert.equal(body.reading_context.locator.content_hash,content.project.digest);assert.equal(await player.evaluate(p=>p.paused),true);await save('new-question',body);
  let answer;const until=Date.now()+180000;while(Date.now()<until){const resp=await context.request.get(`${base}/backend/api/self-learning/courses/${course}/topics/${chapter.id}/agent-turns`,{headers});assert.equal(resp.status(),200);answer=(await resp.json()).find(a=>a.request_id===body.request_id);if(answer&&['succeeded','failed','canceled'].includes(answer.status))break;await p.waitForTimeout(1500)}assert.equal(answer?.status,'succeeded');await save('new-answer',answer);await writeFile(`${out}/课堂问答.md`,question+'\n\n'+answer.result.answer_markdown+'\n');
  const cite=answer.result.citations.find(c=>c.locator?.kind==='hyperframes');assert.ok(cite);assert.equal(cite.locator.seconds,body.reading_context.locator.seconds);check('fresh-course-question-and-citation',{seconds:cite.locator.seconds,segment:cite.locator.segment_id});await p.waitForTimeout(1200);await p.screenshot({path:`${ev}/new-answer.png`});
  await p.getByRole('button',{name:'继续课堂',exact:true}).click();await p.waitForTimeout(600);assert.equal(await player.evaluate(p=>p.paused),false);await player.evaluate(p=>p.pause());
  const position=await player.evaluate(p=>p.currentTime);await p.reload();await player.waitFor({timeout:60000});await player.evaluate(async p=>{const end=Date.now()+60000;while(!p.ready||!p.assetsReady){if(Date.now()>end)throw Error('restore timeout');await new Promise(r=>setTimeout(r,100))}});await p.waitForTimeout(600);const restored=await player.evaluate(p=>p.currentTime);assert.ok(Math.abs(restored-position)<.2);check('new-course-refresh-restores',{position,restored});
  await p.setViewportSize({width:390,height:850});await p.screenshot({path:`${ev}/new-mobile.png`});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 }
 assert.equal(errors.length,0,JSON.stringify(errors));assert.equal(failures.length,0,JSON.stringify(failures));await save('result',{status:'passed',course_id:course,checks,downloads,errors,failures});console.log(JSON.stringify({status:'passed',course_id:course,downloads}));
}catch(e){await p.screenshot({path:`${ev}/result-failure.png`}).catch(()=>{});await save('result-failure',{message:sanitize(e.message),checks,downloads,errors,failures});console.error(sanitize(e.message));process.exitCode=1;}finally{await browser.close()}
