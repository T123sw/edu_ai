import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.env.HF_ONLINE_STATE||'/tmp/edu-hyperframes-online';
const evidence=process.env.HF_ONLINE_EVIDENCE||'/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-18-hyperframes-e2e-rounds';
const base=process.env.HF_ONLINE_URL||'http://127.0.0.1';
const state=JSON.parse(await readFile(`${root}/student.json`,'utf8'));
const material=JSON.parse(await readFile(`${root}/published-material.json`,'utf8')).material;
const content=material.content;
const sanitize=s=>String(s).replace(/(\/hyperframes\/projects\/)[^/]+/g,'$1[ticket]');
await mkdir(evidence,{recursive:true});
const browser=await chromium.launch({headless:true});
const scenarios=[
 {id:'01-continuous-audio',seconds:6,segment:0,question:'只看我当前停下的直线画面：w 保持 1，b 从 0 变为 2，斜率会变成 3 吗？请解释直线具体怎样变化，并引用当前位置。'},
 {id:'02-controls-downloads',seconds:24,segment:1,question:'根据当前风扇例子的 T−30+b>0，如果 b=-2，温度恰好 32°C 时启动吗？多少度才启动？请区分等于与大于，并引用当前片段。'},
 {id:'03-mobile-refresh',seconds:18,segment:1,mobile:true,question:'我现在看到风扇这一段。温度是 29°C，b=0 和 b=2 时风扇分别会不会启动？请代入条件算一次并引用我暂停的位置。'},
];
const all=[];
for(const scenario of scenarios){
 if(process.env.HF_ROUND&&!scenario.id.startsWith(process.env.HF_ROUND))continue;
 const dir=`${evidence}/${scenario.id}`;await mkdir(dir,{recursive:true});
 const context=await browser.newContext({viewport:scenario.mobile?{width:390,height:850}:{width:1440,height:1000},isMobile:!!scenario.mobile,hasTouch:!!scenario.mobile});
 await context.addInitScript(({token,user})=>{
  // New popup initial documents may have an opaque origin before navigation.
  if(window===window.top && /^https?:$/.test(location.protocol))localStorage.setItem('edu-ai-auth',JSON.stringify({token,user}));
  window.audioMeters=[];const connect=AudioNode.prototype.connect;
  AudioNode.prototype.connect=function(dest,...args){if(dest===this.context.destination){const a=this.context.createAnalyser();window.audioMeters.push(a);connect.call(a,dest);return connect.call(this,a,...args)}return connect.call(this,dest,...args)};
 },state);
 const errors=[],httpFailures=[],requestsFailed=[];
 const watch=p=>{p.on('pageerror',e=>errors.push(sanitize(e.stack||e.message)));p.on('console',m=>{if(m.type()==='error')errors.push(sanitize(m.text()))});p.on('response',r=>{if(r.status()>=400)httpFailures.push({status:r.status(),url:sanitize(r.url())})});p.on('requestfailed',r=>{const reason=r.failure()?.errorText;if(reason!=='net::ERR_ABORTED')requestsFailed.push({url:sanitize(r.url()),reason})});};
 context.on('page',watch);
 const page=await context.newPage();
 const result={scenario:scenario.id,started:new Date().toISOString(),base,course:state.course_id,material_id:material.material_id,version:material.version,digest:content.project.digest,checks:[],errors,httpFailures,requestsFailed};
 const checked=(name,data={})=>{result.checks.push({name,...data});console.log(JSON.stringify({round:scenario.id,check:name,...data}));};
 let frame,player;
 const ready=async()=>{frame=page.frameLocator('iframe').first();player=frame.locator('hyperframes-player');await player.waitFor({timeout:60000});await player.evaluate(async p=>{const end=Date.now()+60000;while(!p.ready){if(Date.now()>end)throw Error('player ready timeout');await new Promise(r=>setTimeout(r,100))}});await page.waitForTimeout(400);};
 const seek=async t=>{await player.evaluate((p,t)=>{p.pause();p.seek(t)},t);await page.waitForTimeout(400);assert.ok(Math.abs(await player.evaluate(p=>p.currentTime)-t)<.15)};
 const play=async()=>{assert.equal(await player.evaluate(p=>p.paused),true);await player.locator('button').first().click();await page.waitForTimeout(400);assert.equal(await player.evaluate(p=>p.paused),false)};
 const audio=async label=>{const native=page.frames().find(f=>f.url().includes('/api/hyperframes/projects/')&&f.url().includes('/index.html'));assert.ok(native);const value=await native.waitForFunction(()=>{const meters=window.audioMeters?.map(m=>{const a=new Float32Array(m.fftSize);m.getFloatTimeDomainData(a);return {state:m.context.state,rms:Math.sqrt(a.reduce((s,v)=>s+v*v,0)/a.length)}});return meters?.some(m=>m.state==='running'&&m.rms>.0001)?meters:false},{},{timeout:9000});checked(label,{audio:await value.jsonValue(),seconds:await player.evaluate(p=>p.currentTime)});};
 try{
  await page.goto(`${base}/#/classroom/${state.course_id}`,{waitUntil:'domcontentloaded'});await ready();checked('production-player-ready');
  if(scenario.id.startsWith('01')){
   await seek(0);await play();await audio('first-segment-audible');
   await player.evaluate(p=>{window.hfEnded=false;p.addEventListener('ended',()=>window.hfEnded=true,{once:true})});
   await player.evaluate(async(p,b)=>{while(p.currentTime<b+1){await new Promise(r=>setTimeout(r,100))}},content.timeline.segments[1].start);
   await audio('second-segment-audible-after-natural-transition');await page.screenshot({path:`${dir}/playing-second-scene.png`});
   await player.evaluate(async p=>{const end=Date.now()+40000;while(!window.hfEnded){if(Date.now()>end)throw Error('playback did not end');await new Promise(r=>setTimeout(r,100))}});
   const ended=await player.evaluate(p=>({time:p.currentTime,paused:p.paused,ended:window.hfEnded}));assert.ok(ended.ended);assert.ok(Math.abs(ended.time-content.timeline.duration)<.2);checked('entire-lesson-played-to-end',ended);
  }
  if(scenario.id.startsWith('02')){
   await seek(4);await frame.getByLabel('播放速度').selectOption('2');assert.equal(await player.evaluate(p=>p.playbackRate),2);await play();const t=await player.evaluate(p=>p.currentTime);await page.waitForTimeout(1300);const delta=await player.evaluate(p=>p.currentTime)-t;assert.ok(delta>2&&delta<3.6);checked('double-speed-advances-clock',{delta});
   await player.evaluate(p=>p.pause());const paused=await player.evaluate(p=>p.currentTime);await page.waitForTimeout(900);assert.ok(Math.abs(await player.evaluate(p=>p.currentTime)-paused)<.08);checked('pause-freezes-clock');
   await frame.getByLabel('播放速度').selectOption('1');
   const volume=frame.getByLabel('音量');await volume.fill('0');assert.equal(await player.evaluate(p=>p.muted),true);await volume.fill('0.65');assert.equal(await player.evaluate(p=>p.muted),false);assert.equal(await player.evaluate(p=>p.volume),.65);checked('mute-and-volume-restoration');
   await frame.getByRole('navigation',{name:'课堂章节'}).getByRole('button').nth(1).click();await page.waitForTimeout(300);assert.ok(Math.abs(await player.evaluate(p=>p.currentTime)-content.timeline.segments[1].start)<.15);
   await frame.locator('summary').filter({hasText:'讲解全文'}).click();await frame.locator('.hf-transcript button').first().click();await page.waitForTimeout(300);assert.ok(await player.evaluate(p=>p.currentTime)<.15);checked('chapter-and-transcript-seek');
   const downloads=[];
   for(const name of ['下载 MP4','下载 SRT','下载 HTML 项目 ZIP']){
    const pending=page.waitForEvent('download');await frame.getByRole('link',{name,exact:true}).click();const d=await pending;assert.equal(await d.failure(),null);const data=await readFile(await d.path());assert.ok(data.length>100);downloads.push({name,filename:d.suggestedFilename(),bytes:data.length,sha256:createHash('sha256').update(data).digest('hex')});
   }
   checked('three-real-browser-downloads',{downloads});
  }
  if(scenario.mobile){
   await seek(9.5);await play();await audio('mobile-chromium-audible');await player.evaluate(p=>p.pause());const saved=await player.evaluate(p=>p.currentTime);await page.waitForTimeout(400);await page.reload({waitUntil:'domcontentloaded'});await ready();const restored=await player.evaluate(p=>p.currentTime);assert.ok(Math.abs(saved-restored)<.2,`refresh ${saved} -> ${restored}`);assert.equal(await player.evaluate(p=>p.paused),true);checked('refresh-restores-time-without-autoplay',{saved,restored});
   await page.setViewportSize({width:320,height:780});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:`${dir}/mobile-320.png`});await page.setViewportSize({width:390,height:850});
   await page.getByRole('navigation',{name:'课堂面板'}).getByRole('button',{name:'目录',exact:true}).click();await page.getByRole('navigation',{name:'课堂面板'}).getByRole('button',{name:'学习',exact:true}).click();checked('mobile-directory-and-learning-panels');
  }
  await seek(scenario.seconds);await play();await audio('audio-before-question');
  if(scenario.mobile)await page.getByRole('navigation',{name:'课堂面板'}).getByRole('button',{name:'Agent',exact:true}).click();
  await page.getByRole('textbox',{name:'向学习 Agent 提问'}).fill(scenario.question);
  const questionTime=await player.evaluate(p=>p.currentTime);
  const pending=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/agent-turns'));
  await page.getByRole('button',{name:'发送问题',exact:true}).click();const body=(await pending).postDataJSON();result.question=body;
  const loc=body.reading_context.locator;
  assert.equal(loc.kind,'hyperframes');assert.equal(loc.segment_id,content.timeline.segments[scenario.segment].id);assert.equal(loc.content_hash,content.project.digest);assert.equal(body.reading_context.resource_ref.version,material.version);assert.ok(Math.abs(loc.seconds-questionTime)<.5);assert.equal(await player.evaluate(p=>p.paused),true);checked('question-freezes-exact-current-context',{seconds:loc.seconds,segment:loc.segment_id});
  await page.screenshot({path:`${dir}/question.png`});
  const since=Date.now();let answer;
  while(Date.now()-since<180000){const r=await context.request.get(`${base}/backend/api/self-learning/courses/${state.course_id}/topics/bias/agent-turns`,{headers:{Authorization:`Bearer ${state.token}`}});assert.equal(r.status(),200);answer=(await r.json()).find(t=>t.request_id===body.request_id);if(answer&&['succeeded','failed','canceled'].includes(answer.status))break;await page.waitForTimeout(1500)}
  assert.equal(answer?.status,'succeeded');result.answer=answer;checked('real-model-answer-succeeded',{elapsedSeconds:(Date.now()-since)/1000});
  const citation=answer.result.citations.find(c=>c.locator?.kind==='hyperframes'&&Math.abs(c.locator.seconds-loc.seconds)<.00001);assert.ok(citation,'current answer must cite its own location');assert.deepEqual(citation.resource_ref,body.reading_context.resource_ref);assert.equal(citation.locator.content_hash,content.project.digest);
  await page.waitForFunction(seconds=>[...document.querySelectorAll('.sl-agent a')].some(a=>{try{return Math.abs(Number(new URLSearchParams(a.getAttribute('href').split('#ai?')[1]).get('seconds'))-seconds)<.00001}catch{return false}}),loc.seconds,{timeout:20000});
  const links=await page.locator('.sl-agent a').evaluateAll(es=>es.map(e=>({text:e.textContent,href:e.getAttribute('href')})));
  const cited=links.find(l=>l.href?.includes('seconds=')&&Math.abs(Number(new URLSearchParams(l.href.split('#ai?')[1]).get('seconds'))-loc.seconds)<.00001);assert.ok(cited);result.citation=cited;
  await page.screenshot({path:`${dir}/answer.png`});
  // Click the new answer's exact link; old messages must not satisfy this assertion.
  const newTab=context.waitForEvent('page');await page.locator('.sl-agent a').filter({hasText:cited.text}).evaluateAll((es,href)=>es.find(e=>e.getAttribute('href')===href).click(),cited.href);
  const cp=await newTab;await cp.waitForLoadState('domcontentloaded');const citedPlayer=cp.locator('hyperframes-player');await citedPlayer.waitFor({timeout:60000});await citedPlayer.evaluate(async p=>{const end=Date.now()+60000;while(!p.ready){if(Date.now()>end)throw Error('citation ready timeout');await new Promise(r=>setTimeout(r,100))}});await cp.waitForTimeout(400);
  assert.ok(Math.abs(await citedPlayer.evaluate(p=>p.currentTime)-loc.seconds)<.2);await cp.screenshot({path:`${dir}/citation.png`});
  // A prior saved position must not override an explicit citation on reload.
  await citedPlayer.evaluate(p=>p.seek(2));await cp.waitForTimeout(300);await cp.reload({waitUntil:'domcontentloaded'});await citedPlayer.waitFor({timeout:60000});await citedPlayer.evaluate(async p=>{const end=Date.now()+60000;while(!p.ready){if(Date.now()>end)throw Error('citation reload timeout');await new Promise(r=>setTimeout(r,100))}});await cp.waitForTimeout(400);assert.ok(Math.abs(await citedPlayer.evaluate(p=>p.currentTime)-loc.seconds)<.2);await cp.close();checked('current-answer-citation-jump-and-reload');
  if(scenario.mobile)await page.getByRole('navigation',{name:'课堂面板'}).getByRole('button',{name:'学习',exact:true}).click();
  await page.getByRole('button',{name:'继续课堂',exact:true}).click();await page.waitForTimeout(600);assert.equal(await player.evaluate(p=>p.paused),false);await audio('audio-after-answer-resume');await player.evaluate(p=>p.pause());checked('resume-after-question');
  if(scenario.mobile){await page.reload({waitUntil:'domcontentloaded'});await ready();await page.getByRole('navigation',{name:'课堂面板'}).getByRole('button',{name:'Agent',exact:true}).click();await page.getByText(scenario.question,{exact:true}).last().waitFor();checked('question-history-survives-refresh');}
  assert.equal(errors.length,0,JSON.stringify(errors));assert.equal(httpFailures.length,0,JSON.stringify(httpFailures));assert.equal(requestsFailed.length,0,JSON.stringify(requestsFailed));result.status='passed';
 }catch(e){result.status='failed';result.failure=sanitize(e.stack||e.message);await page.screenshot({path:`${dir}/failure.png`}).catch(()=>{});console.error(JSON.stringify({round:scenario.id,failure:result.failure}));process.exitCode=1;}
 result.finished=new Date().toISOString();await writeFile(`${dir}/result.json`,JSON.stringify(result,null,2));all.push(result);await context.close();console.log(JSON.stringify({round:scenario.id,status:result.status}));
}
await browser.close();await writeFile(`${evidence}/summary${process.env.HF_ROUND?'-'+process.env.HF_ROUND:''}.json`,JSON.stringify(all.map(({scenario,status,checks,failure,started,finished})=>({scenario,status,checks,failure,started,finished})),null,2));
