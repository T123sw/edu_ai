import fs from 'node:fs';
import assert from 'node:assert/strict';
import {chromium} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/index.mjs';
import {expect} from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test.mjs';
const account=JSON.parse(fs.readFileSync('/tmp/edu-resource-e2e-account.json'));
const out='/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-14-resource-tools-e2e';
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
await context.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),{token:account.token,user:account.user});
const page=await context.newPage();page.setDefaultTimeout(15000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const results=JSON.parse(fs.readFileSync(out+'/preview.json')).results.filter(r=>r.kind!=='scenario');
async function api(path){const r=await context.request.get('http://127.0.0.1/backend/api'+path,{headers:{Authorization:`Bearer ${account.token}`}});assert.equal(r.status(),200);return r.json();}
async function openResource(kind,label){
 if(await page.getByRole('button',{name:'关闭工具面板'}).count())await page.getByRole('button',{name:'关闭工具面板'}).click();
 await page.goto('http://127.0.0.1/#/my-resources');
 await page.locator('.studio-type-filters button').filter({hasText:label}).click();
 await page.locator('.studio-resource-row').filter({hasText:'验收·'+label+'·'}).first().click();
 const dialog=page.getByRole('dialog');await expect(dialog.locator('.studio-preview-actions')).toBeVisible();return dialog;
}
async function download(button,filename){const pending=page.waitForEvent('download');await button.click();const dl=await pending;await dl.saveAs(`${out}/${filename}`);return fs.readFileSync(`${out}/${filename}`);}
try{
 const listing=await api('/personal-studio');
 for(const [kind,label] of [['scenario','情景案例']]){
  const resource=listing.resources.find(r=>r.material_type===kind);if(!resource){results.push({kind,passed:false,error:'No successful generated resource'});continue;}
  const result={kind,checks:[]};results.push(result);
  try{
   const detail=await api(`/personal-studio/resources/${kind}/${resource.material_id}`);
   fs.writeFileSync(`${out}/material-${kind}.json`,JSON.stringify(detail,null,2));
   const unauth=await fetch(`http://127.0.0.1/backend/api/personal-studio/resources/${kind}/${resource.material_id}`);assert.equal(unauth.status,401);result.checks.push('unauthenticated access denied');
   const dialog=await openResource(kind,label);
   if(kind==='report'){
    await expect(dialog.locator('table')).toHaveCount(1);
    await expect(dialog.locator('pre')).toHaveCount(4);
    const exported=(await download(dialog.getByRole('button',{name:'导出',exact:true}),'export-report.md')).toString();
    assert.equal(exported.trim(),detail.content.trim());result.checks.push('table and code rendered','Markdown export preserves complete saved content');
   }
   if(kind==='quiz'){
    await expect(dialog.locator('.resource-quiz-preview article')).toHaveCount(4);
    const q=detail.content.questions;assert.deepEqual(q.map(x=>x.type),['choice','blank','short','judge']);
    await dialog.locator('.resource-quiz-preview summary').first().click();
    await expect(dialog.locator('.resource-quiz-preview article').first()).toContainText('答案：B');
    const exported=JSON.parse((await download(dialog.getByRole('button',{name:'导出',exact:true}),'export-quiz.json')).toString());assert.deepEqual(exported.questions,q);
    result.checks.push('four requested types generated','answer/explanation expansion','JSON export preserves all questions');
   }
   if(kind==='flashcard'){
    const round=dialog.getByRole('region',{name:'本轮闪卡练习'});
    await round.getByRole('button',{name:'查看答案',exact:true}).click();
    await round.getByRole('button',{name:'还不会，稍后再试',exact:true}).click();
    for(let i=0;i<3;i++){await round.getByRole('button',{name:'查看答案',exact:true}).click();await round.getByRole('button',{name:'会了',exact:true}).click();}
    await expect(round.getByText('本轮完成',{exact:true})).toBeVisible();await expect(round).toContainText('共回忆 4 次');
    await round.getByRole('button',{name:'再练一轮'}).click();await expect(round).toContainText('剩余 3 张');
    const exported=JSON.parse((await download(dialog.getByRole('button',{name:'导出',exact:true}),'export-flashcard.json')).toString());assert.deepEqual(exported.cards,detail.content.cards);
    result.checks.push('unknown returns once to queue','known cards removed','round completion and restart','JSON export');
   }
   if(kind==='graph'){
    const graph=dialog.locator('.balanced-mind-map');
    await graph.getByRole('button',{name:'展开全部',exact:true}).click();
    await expect(graph.getByRole('treeitem')).toHaveCount(13);
    await graph.getByRole('button',{name:'放大',exact:true}).click();await expect(graph).toContainText('110%');
    await graph.getByRole('button',{name:'复位',exact:true}).click();await expect(graph.getByRole('treeitem')).toHaveCount(5);
    const exported=JSON.parse((await download(graph.getByRole('button',{name:'导出导图',exact:true}),'export-graph.json')).toString());assert.deepEqual(exported,detail.content);
    result.checks.push('13 nodes / 3 levels','expand, zoom and reset','native JSON export');
   }
   if(kind==='podcast'){
    const audio=dialog.locator('audio');await expect(audio).toHaveAttribute('src',/^blob:/);
    await expect.poll(()=>audio.evaluate(n=>n.readyState),{timeout:20000}).toBeGreaterThan(0);
    await audio.evaluate(n=>n.play());await expect.poll(()=>audio.evaluate(n=>n.currentTime)).toBeGreaterThan(0);await audio.evaluate(n=>n.pause());
    result.duration=await audio.evaluate(n=>n.duration);
    await expect(dialog.locator('.studio-transcript details')).toHaveCount(detail.content.segments.length);
    await dialog.locator('.studio-transcript summary').nth(1).click();await expect(dialog.locator('.studio-transcript details').nth(1)).toHaveAttribute('open','');
    const downloaded=await download(dialog.getByRole('link',{name:'下载音频'}),'export-podcast.mp3');assert(downloaded.length>10000);
    result.checks.push('real MP3 decoded and playback advances','chapter transcript','audio download');
   }
   if(kind==='scenario'){
    const content=detail.content;const scenes=new Map(content.scenes.map(s=>[s.id,s]));const paths=[];
    function walk(id,path=[]){const s=scenes.get(id);if(!s.choices.length){paths.push(path);return;}assert(path.length<16);s.choices.forEach((c,i)=>walk(c.next_id,[...path,i]));}walk(content.start_id);
    for(const path of paths){for(const i of path){await dialog.locator('.studio-scenario-choices button').nth(i).click();await expect(dialog.locator('.studio-scenario-feedback')).toBeVisible();await dialog.getByRole('button',{name:'继续情景'}).click();}await expect(dialog.locator('.studio-scenario-ending')).toBeVisible();await dialog.getByRole('button',{name:'重新体验'}).click();}
    result.paths=paths.length;result.checks.push('every root-to-ending path','choice feedback, ending and restart');
   }
   for(const width of [1440,390]){await page.setViewportSize({width,height:1000});await page.screenshot({path:`${out}/preview-${kind}-${width}.png`});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
   result.checks.push('desktop/mobile no page overflow');
   await page.setViewportSize({width:1440,height:1000});
   await page.reload();await openResource(kind,label);result.checks.push('saved resource reopens after reload');
   if(['report','quiz'].includes(kind)){
    await page.getByRole('button',{name:'加入课堂目录',exact:true}).click();
    await page.getByLabel('知识点',{exact:true}).selectOption(account.chapterId);
    await page.getByRole('button',{name:'确认加入',exact:true}).click();
    await expect(page.getByText('已加入课程，原始资源仍保留在我的资源。',{exact:true})).toBeVisible();result.checks.push('attach to classroom');
   }
   result.passed=true;
  }catch(e){result.passed=false;result.error=String(e);await page.screenshot({path:`${out}/error-${kind}.png`}).catch(()=>{});}
  await page.setViewportSize({width:1440,height:1000});
  console.log(JSON.stringify(result));fs.writeFileSync(out+'/preview.json',JSON.stringify({results,errors},null,2));
 }
}finally{fs.writeFileSync(out+'/preview.json',JSON.stringify({results,errors},null,2));await browser.close();}
