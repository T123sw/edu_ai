// Frozen real metadata; no user progress writes or generation requests.
import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from 'playwright';
const base=process.env.SLOTS_BASE||'http://127.0.0.1:18093',out=process.env.SLOTS_OUTPUT||'/tmp/resource-slots-check';fs.mkdirSync(out,{recursive:true});
const auth=JSON.parse(fs.readFileSync('/tmp/hf-demo-course-auth/auth.json','utf8')),course='learn-a9c1d026075f47b3aaa7fbc0862a7692';
const fetched=await fetch(base+'/backend/api/self-learning/courses/'+course,{headers:{Authorization:'Bearer '+auth.token}});assert.equal(fetched.status,200);const original=await fetched.json();
const browser=await chromium.launch({headless:true,executablePath:'/home/zxqs_ep/.cache/hyperframes/chrome/chrome-headless-shell/linux-152.0.7977.30/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox']});const result={mode:'frozen real course metadata; empty and partial delivery',cases:[],errors:[]};
try{for(const empty of [true,false]){
 const room={...structuredClone(original),agentRuntime:false,sessionPersistence:false,progressPersistence:false,messages:[],progress:{},understanding:{}};
 if(empty){room.chapters=room.chapters.map(c=>({...c,generationState:'queued',pendingResourceTypes:['classroom','report','quiz'],resources:[{id:'pending:'+c.id,title:c.title,topic:c.title,kind:'video',ready:false,minutes:0,createdAt:0,live:true}]}));room.selectedId=room.chapters[0].resources[0].id;}
 const ctx=await browser.newContext({viewport:{width:1440,height:1000},storageState:{cookies:[],origins:[{origin:base,localStorage:[{name:'edu-ai-auth',value:JSON.stringify(auth)}]}]}});const page=await ctx.newPage();page.on('pageerror',e=>result.errors.push(e.message));
 await page.route('**/backend/api/**',async route=>{const req=route.request(),path=new URL(req.url()).pathname;
 if(path.endsWith('/auth/verify')||path.endsWith('/playback'))return route.continue();
 if(path==='/backend/api/self-learning/state')return route.fulfill({json:{version:1,rooms:[room],resources:[],jobs:[],serverJobs:[],shared:[]}});
 if(path==='/backend/api/self-learning/courses/'+course&&req.method()==='GET')return route.fulfill({json:room});
 if(!['GET','HEAD','OPTIONS'].includes(req.method()))return route.fulfill({json:{}});return route.continue();});
 await page.goto(base+'/#/classroom/'+course);await page.waitForFunction(()=>document.querySelectorAll('.sl-resource-row').length===12,null,{timeout:45000});
 const labels=await page.locator('.sl-resource-row > span:first-of-type').allTextContents();for(const label of ['视频讲解','学习报告','巩固练习'])assert.equal(labels.filter(t=>t.startsWith(label)).length,4);
 const pending=page.locator('.sl-resource-row').filter({has:page.locator('small')});assert.ok(await pending.count()>0);await pending.last().click();await page.getByRole('heading',{name:'本节内容尚未就绪',exact:true}).waitFor();assert.equal(await page.locator('.sl-live-material').count(),0);await page.waitForTimeout(1500);assert.equal(await page.locator('.sl-live-error').count(),0);
 await page.screenshot({path:out+(empty?'/empty.png':'/partial.png'),fullPage:true});await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:out+(empty?'/empty-mobile.png':'/partial-mobile.png'),fullPage:true});result.cases.push({empty,slots:12,pending:await pending.count(),passed:true});await ctx.close();
}assert.deepEqual(result.errors,[]);result.passed=true;}finally{fs.writeFileSync(out+'/result.json',JSON.stringify(result,null,2));await browser.close();}console.log(JSON.stringify(result));
