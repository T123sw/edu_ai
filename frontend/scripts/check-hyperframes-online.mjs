import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
const root=process.env.HF_ONLINE_STATE || '/tmp/edu-hyperframes-online';
const evidence=process.env.HF_ONLINE_EVIDENCE || '/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-hyperframes-online';
const base=process.env.HF_ONLINE_URL || 'http://127.0.0.1';
const state=JSON.parse(await readFile(`${root}/${process.env.HF_STUDENT === '1' ? 'student' : 'credentials'}.json`,'utf8'));
await mkdir(evidence,{recursive:true});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage();
const errors=[],failed=[],requests=[];
const sanitize=s=>s.replace(/(\/hyperframes\/projects\/)[^/]+/g,'$1[ticket]');
page.on('pageerror',e=>errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')errors.push(sanitize(m.text()))});
page.on('response',r=>{if(r.status()>=400)failed.push({url:sanitize(r.url()),status:r.status()})});
page.on('request',r=>{requests.push({url:sanitize(r.url()),method:r.method()})});
await page.addInitScript(({token,user})=>{
 if(window===window.top)localStorage.setItem('edu-ai-auth',JSON.stringify({token,user}));
 window.audioMeters=[]; const original=AudioNode.prototype.connect;
 AudioNode.prototype.connect=function(dest,...args){if(dest===this.context.destination){const m=this.context.createAnalyser();window.audioMeters.push(m);original.call(m,dest);return original.call(this,m,...args)}return original.call(this,dest,...args)};
},state);
try {
 await page.goto(base+'/',{waitUntil:'networkidle'});
 await page.screenshot({path:`${evidence}/online-home.png`});
 assert.equal(errors.length,0,JSON.stringify(errors));
 assert.equal(failed.length,0,JSON.stringify(failed));
 if(process.env.HF_SMOKE_ONLY==='1'){
  await writeFile(`${evidence}/home-smoke.json`,JSON.stringify({base,errors,failed,requests},null,2));
  console.log('Production authenticated homepage passed');
 } else {
 const material=JSON.parse(await readFile(`${root}/published-material.json`,'utf8')).material;
 const content=material.content;
 await page.goto(`${base}/#/classroom/${state.course_id}`,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>document.querySelector('iframe')!==null);
 const frame=page.frameLocator('iframe').first();
 const player=frame.locator('hyperframes-player');
 await player.waitFor({timeout:60000});
 await player.evaluate(async p=>{const deadline=Date.now()+60000;while(!p.ready){if(Date.now()>deadline)throw Error('native player never ready');await new Promise(r=>setTimeout(r,150))}});
 await player.evaluate(p=>p.seek(0));
 await page.waitForTimeout(300);
 await player.locator('button').first().click();
 await page.waitForTimeout(2200);
 const native=page.frames().find(f=>f.url().includes('/api/hyperframes/projects/')&&f.url().includes('/index.html'));
 assert.ok(native,'native project frame');
 await native.waitForFunction(()=>window.audioMeters?.some(m=>{
  const a=new Float32Array(m.fftSize);m.getFloatTimeDomainData(a);
  return m.context.state==='running'&&Math.sqrt(a.reduce((s,v)=>s+v*v,0)/a.length)>0.0001;
 }),{},{timeout:8000});
 const audio=await native.evaluate(()=>window.audioMeters.map(m=>{const a=new Float32Array(m.fftSize);m.getFloatTimeDomainData(a);return {state:m.context.state,rms:Math.sqrt(a.reduce((s,v)=>s+v*v,0)/a.length)}}));
 assert.ok(audio.some(m=>m.state==='running'&&m.rms>0.0001),JSON.stringify(audio));
 await page.screenshot({path:`${evidence}/online-playing.png`});
 const target=content.timeline.segments[1].start+4;
 await player.evaluate((p,t)=>{p.pause();p.seek(t)},target);
 await page.waitForTimeout(600);
 await player.locator('button').first().click();
 await page.waitForTimeout(500);
 assert.equal(await player.evaluate(p=>p.paused),false);
 const submitted=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/agent-turns'));
 await page.getByRole('textbox',{name:'向学习 Agent 提问'}).fill('刚才风扇的例子里，为什么改变偏置就能改变启动温度？请结合我当前看到的画面解释。');
 const questionTime=await player.evaluate(p=>p.currentTime);
 await page.getByRole('button',{name:'发送问题',exact:true}).click();
 const body=(await submitted).postDataJSON();
 assert.equal(body.reading_context.locator.kind,'hyperframes');
 assert.equal(body.reading_context.locator.segment_id,content.timeline.segments[1].id);
 assert.ok(Math.abs(body.reading_context.locator.seconds-questionTime)<1);
 assert.equal(body.reading_context.locator.content_hash,content.project.digest);
 assert.equal(await player.evaluate(p=>p.paused),true);
 await writeFile(`${evidence}/question-request.json`,JSON.stringify(body,null,2));
 await page.screenshot({path:`${evidence}/online-question.png`});
 console.log(JSON.stringify({phase:'question-submitted',audio,seconds:target}));
 let answer;const deadline=Date.now()+180000;
 while(Date.now()<deadline){
  const r=await page.request.get(`${base}/backend/api/self-learning/courses/${state.course_id}/topics/bias/agent-turns`,{headers:{Authorization:`Bearer ${state.token}`}});
  assert.equal(r.status(),200);const turns=await r.json();answer=turns.find(t=>t.request_id===body.request_id);
  if(answer&&['succeeded','failed','canceled'].includes(answer.status))break;
  await page.waitForTimeout(2000);
 }
 assert.equal(answer?.status,'succeeded',JSON.stringify(answer));
 await page.waitForTimeout(1800);
 await page.screenshot({path:`${evidence}/online-answer.png`});
 const links=await page.locator('.sl-agent a').evaluateAll(es=>es.map(e=>({text:e.textContent,href:e.getAttribute('href')})));
 assert.ok(links.some(l=>l.href?.includes('seconds=')), 'answer must cite exact timeline');
 const cited=links.find(l=>l.href?.includes('seconds='));
 const citationPage=await page.context().newPage();
 await citationPage.goto(new URL(cited.href,base).href);
 const citedPlayer=citationPage.locator('hyperframes-player');
 await citedPlayer.waitFor({timeout:60000});
 await citedPlayer.evaluate(async p=>{const deadline=Date.now()+60000;while(!p.ready){if(Date.now()>deadline)throw Error('citation not ready');await new Promise(r=>setTimeout(r,150))}});
 const citedSeconds=Number(new URLSearchParams(cited.href.split('#ai?')[1]).get('seconds'));
 assert.ok(Math.abs(await citedPlayer.evaluate(p=>p.currentTime)-citedSeconds)<.5);
 await citationPage.screenshot({path:`${evidence}/online-citation.png`});await citationPage.close();
 await page.getByRole('button',{name:'继续课堂',exact:true}).click();
 await page.waitForTimeout(800);
 assert.equal(await player.evaluate(p=>p.paused),false);
 await player.evaluate(p=>p.pause());
 await page.setViewportSize({width:390,height:850});await page.screenshot({path:`${evidence}/online-mobile.png`});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(errors.length,0,JSON.stringify(errors));assert.equal(failed.length,0,JSON.stringify(failed));
 await writeFile(`${evidence}/browser.json`,JSON.stringify({kind:'Production APIs and database; real model/TTS/native player; no request mocks',base,course_id:state.course_id,audio,question:body,answer,citationLinks:links,errors,failed,requests},null,2));
 console.log(JSON.stringify({status:'passed',audio,answerStatus:answer.status,citationLinks:links}));
 }
} catch(e) {
 await page.screenshot({path:`${evidence}/online-failure.png`}).catch(()=>{});
 await writeFile(`${evidence}/browser-failure.json`,JSON.stringify({error:e.message,errors,failed,requests},null,2));
 console.error(sanitize(e.message));process.exitCode=1;
} finally{await browser.close()}
