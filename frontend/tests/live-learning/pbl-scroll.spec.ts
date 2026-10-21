import {enterWorkbench} from './pblWorkbench';
import {test,expect,type Page} from 'playwright/test';
import {createHash} from 'node:crypto';
import type {ProjectArtifact,ProjectReport} from '../../src/pbl/projectTypes';
const files={'/src/App.jsx':"import React from 'react';export default function App(){return <main>请开始实现</main>}",'/src/styles.css':'body { padding: 20px; }'};
const solution="import React,{useState} from 'react';export default function App(){const [n,set]=useState(0);return <main><button onClick={()=>set(n+1)}>增加</button><output>{n}</output></main>}";
const artifact:ProjectArtifact={schemaVersion:2,runtimeKind:'react_app',templateVersion:'react-app-v1',exerciseId:'pbl_project_fixture',artifactVersion:1,topic:'计数器',title:'动手实现计数器',summary:'从界面到交互',starterFiles:files,plan:{goal:'计数器',steps:[{id:'layout',deliverable:'按钮'},{id:'count',deliverable:'计数'}]},tasks:[{id:'layout',stepId:'layout',title:'构建按钮',objective:'添加增加按钮',instructionsMarkdown:'创建一个按钮，文字为「增加」。',explanationMarkdown:'先完成可交互的界面。',hints:['使用 button 元素'],focusFiles:['/src/App.jsx'],checkIds:['button'],cumulativeCheckIds:['button']},{id:'count',stepId:'count',title:'实现递增',objective:'点击时增加计数',instructionsMarkdown:'将每次点击的结果呈现到页面。',explanationMarkdown:'使用 React state 保存计数。',hints:['用 useState 保存数值'],focusFiles:['/src/App.jsx'],checkIds:['increment'],cumulativeCheckIds:['button','increment']}],checks:[{id:'button',label:'增加按钮可以点击',actions:[{type:'click',target:{role:'button',name:'增加'}},{type:'assert',target:{role:'button',name:'增加'},assertion:'visible'}]},{id:'increment',label:'点击后显示1',actions:[{type:'click',target:{role:'button',name:'增加'}},{type:'assert',target:{testId:'display'},assertion:'text',expected:'1'}]}],validationSummary:{passed:true}};
async function edit(page:Page,code:string){await page.locator('.cm-content[contenteditable=true]').click();await page.keyboard.press('ControlOrMeta+A');await page.keyboard.insertText(code);}
async function fixture(page:Page){
  let workspace={exerciseId:artifact.exerciseId,artifactVersion:1,revision:0,files:{...files},activeTaskId:'layout',customInputText:''};
  const runs:ProjectReport[]=[];let failSave=false;
  await page.addInitScript(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'project_fixture',role:'student'}})));
  await page.route('**/api/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname.replace(/^\/backend/,'');if(!path.startsWith('/api/'))return route.continue();
    if(path.endsWith('/auth/verify'))return route.fulfill({json:{valid:true,user:{username:'project_fixture',role:'student'}}});
    if(path.endsWith('/self-learning/state'))return route.fulfill({json:{version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]}});
    if(path.endsWith('/workspace')){if(req.method()==='PUT'){if(failSave)return route.abort();const p=req.postDataJSON();if(p.expectedRevision!==workspace.revision)return route.fulfill({status:409,json:{detail:'版本冲突'}});workspace={...workspace,...p,revision:workspace.revision+1};}return route.fulfill({json:workspace});}
    if(path.endsWith('/check')){const p=req.postDataJSON();const ids=p.taskId==='layout'?['button']:['button','increment'];const passed=p.files['/src/App.jsx'].includes('useState');const report:ProjectReport={runId:p.runId,exerciseId:artifact.exerciseId,artifactVersion:1,templateVersion:'react-app-v1',taskId:p.taskId,codeHash:createHash('sha256').update(JSON.stringify(Object.fromEntries(Object.keys(p.files).sort().map(k=>[k,p.files[k]])))).digest('hex'),status:passed?'passed':'failed',results:ids.map(id=>({caseId:id,status:passed?'passed':'failed',message:passed?'通过':'未通过'})),durationMs:15,evidenceSource:'server_verified'};runs.unshift(report);return route.fulfill({json:report});}
    if(path.endsWith('/runs'))return route.fulfill({json:{items:runs}});
    if(path.endsWith('/pbl_project_fixture'))return route.fulfill({json:{artifact,job:null}});
    return route.fulfill({json:{items:[]}});
  });
  return {get:()=>workspace,offline:(v:boolean)=>{failSave=v;}};
}

test('滚轮平滑进入整屏工作区并返回，半屏预览不吞滚轮',async({page})=>{
  await fixture(page);await page.emulateMedia({reducedMotion:'no-preference'});
  await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  await page.setViewportSize({width:1920,height:911});await page.goto('/#/practice/code/pbl_project_fixture');
  const stage=page.locator('.pbl-workbench-stage');await expect(stage).toHaveAttribute('data-focused','false');
  await expect(page.locator('.sp-editor')).toBeVisible();
  // The reading area grows with the requirements and acceptance instructions.
  const initial=await stage.boundingBox();expect(initial!.y).toBeGreaterThan(911*.4);expect(initial!.y).toBeLessThan(911*.8);
  await page.screenshot({path:'/tmp/pbl-scroll-before-1920.png'});
  const editor=await page.locator('.cm-content').elementHandle(),frame=await page.locator('.sp-preview iframe').elementHandle();
  const samples=page.evaluate(()=>new Promise<number[]>(resolve=>{const values:number[]=[];const start=performance.now();const tick=()=>{values.push(document.querySelector('.sl-app')!.scrollTop);if(performance.now()-start>1000)resolve(values);else requestAnimationFrame(tick);};tick();}));
  await page.mouse.move(900,240);await page.mouse.wheel(0,120);
  await expect(stage).toHaveAttribute('data-focused','true');
  const positions=await samples,end=await page.locator('.sl-app').evaluate(el=>el.scrollTop);
  expect(new Set(positions.filter(n=>n>1&&n<end-1)).size).toBeGreaterThan(3);
  await expect(page.getByRole('heading',{name:'构建按钮',exact:true})).not.toBeInViewport();await expect(page.locator('.sl-header')).not.toBeInViewport();
  expect(Math.abs((await stage.boundingBox())!.y)).toBeLessThan(1);
  await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});await expect(page.locator('.sp-preview')).toBeInViewport({ratio:1});
  await expect(page.getByRole('button',{name:'检查本步',exact:true})).toBeInViewport();
  const toolbar=page.locator('.pbl-stage-toolbar');
  await expect(toolbar.getByRole('button',{name:'检查本步',exact:true})).toBeVisible();
  await expect(page.locator('.pbl-project-footer')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'问 AI',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'收起 AI 辅导'})).toHaveCount(0);
  await expect(page.getByTestId('save-status')).toBeHidden();
  await toolbar.getByText('工程操作',{exact:true}).click();
  const menu=page.locator('.pbl-project-tools>div');await expect(menu.getByRole('button',{name:'同步',exact:true})).toBeVisible();
  expect((await menu.boundingBox())!.y).toBeGreaterThan((await toolbar.boundingBox())!.y);
  await toolbar.getByText('工程操作',{exact:true}).click();
  const body=await page.locator('.pbl-workbench-body').boundingBox();
  expect(911-body!.y-body!.height).toBeLessThanOrEqual(13);
  await page.screenshot({path:'/tmp/pbl-scroll-after-1920.png'});
  await page.mouse.move(900,28);await page.mouse.wheel(0,-120);
  await expect.poll(()=>page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(0);
  await page.waitForTimeout(750); // End the return gesture before starting a fresh gesture over the preview.
  await page.mouse.move(1000,650);await page.mouse.wheel(0,120);await expect(stage).toHaveAttribute('data-focused','true');
  expect(await editor!.evaluate(el=>el.isConnected)).toBe(true);expect(await frame!.evaluate(el=>el.isConnected)).toBe(true);
});

test('工作区内独立滚动并保留草稿，缩放和手机切换不挤出操作区',async({page})=>{
  await fixture(page);await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  await page.goto('/#/practice/code/pbl_project_fixture');await enterWorkbench(page);
  await edit(page,solution+'\n'+Array.from({length:100},(_,i)=>`// 保留代码 ${i}`).join('\n'));
  if(await page.locator('#pbl-tutor-toggle').getAttribute('aria-expanded')!=='true')await page.locator('#pbl-tutor-toggle').click();await page.getByLabel('向编程辅导提问').fill('翻页前的草稿');
  const outer=await page.locator('.sl-app').evaluate(el=>el.scrollTop),codeScroll=page.locator('.cm-scroller');
  await codeScroll.evaluate(el=>{el.scrollTop=100;});const before=await codeScroll.evaluate(el=>el.scrollTop);
  await codeScroll.hover();await page.mouse.wheel(0,180);await expect.poll(()=>codeScroll.evaluate(el=>el.scrollTop)).toBeGreaterThan(before);
  expect(await page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(outer);
  await codeScroll.evaluate(el=>{el.scrollTop=0;});await page.mouse.wheel(0,-180);await page.waitForTimeout(250);expect(await page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(outer);
  await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();await enterWorkbench(page);
  await expect(page.getByLabel('向编程辅导提问')).toHaveValue('翻页前的草稿');await expect(page.locator('.cm-content')).toContainText('保留代码');
  for(const width of [1440,1024,768,390,320]){
    await page.setViewportSize({width,height:844});await expect(page.locator('.pbl-workbench-stage')).toHaveAttribute('data-focused','true');
    if(width<=760)await page.getByRole('button',{name:'代码',exact:true}).click();
    await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});await expect(page.getByRole('button',{name:'检查本步',exact:true})).toBeInViewport();
    if(width<=760)await page.getByRole('button',{name:'预览与验收',exact:true}).click();
    await expect(page.locator('.sp-preview')).toBeInViewport({ratio:1});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    if([1440,390].includes(width))await page.screenshot({path:`/tmp/pbl-scroll-after-${width}.png`});
  }
});

test('长题目可以完整阅读，切到短题目后工作区保持满屏',async({page})=>{
  await fixture(page);await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  const long=structuredClone(artifact);long.tasks[0].instructionsMarkdown=Array.from({length:25},(_,i)=>`第 ${i+1} 条要求：先观察按钮，再编写对应的事件。`).join('\n\n');
  await page.route('**/api/pbl/pbl_project_fixture',route=>route.fulfill({json:{artifact:long,job:null}}));
  await page.goto('/#/practice/code/pbl_project_fixture');await expect(page.locator('.pbl-problem-reading')).toContainText('第 25 条要求');
  await page.mouse.move(600,350);await page.mouse.wheel(0,120);await expect.poll(()=>page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBeGreaterThan(0);
  await expect(page.locator('.pbl-workbench-stage')).toHaveAttribute('data-focused','false');
  await enterWorkbench(page);await page.getByRole('button',{name:'下一步 →',exact:true}).click();
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('还需要调整');
  await expect(page.locator('.pbl-workbench-stage')).toHaveAttribute('data-focused','true');await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});
  await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();await expect.poll(()=>page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(0);
  await expect(page.getByRole('heading',{name:'实现递增',exact:true})).toBeInViewport();
});


for(const withExplorer of [false,true])test(`长代码的滚动条和末行始终位于代码面板内（文件列表${withExplorer?'开启':'关闭'}）`,async({page},testInfo)=>{
  await fixture(page);
  await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  if(withExplorer)await page.route('**/api/pbl/pbl_project_fixture',route=>route.fulfill({json:{artifact:{...artifact,runtime:{template:'react',entry:'/src/App.jsx',dependencies:{react:'18.3.1','react-dom':'18.3.1'},moduleType:'commonjs'}},job:null}}));
  await page.setViewportSize({width:1440,height:900});
  await page.goto('/#/practice/code/pbl_project_fixture');await enterWorkbench(page);
  await edit(page,solution+'\n'+Array.from({length:160},(_,i)=>`// 滚动检查 ${i}`).join('\n'));
  if(withExplorer)await page.locator('.pbl-file-explorer summary').click();
  const scroller=page.locator('.cm-scroller');
  for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:900});
    if(width<=760)await page.getByRole('button',{name:'代码',exact:true}).click();
    // Let the heading resize and the workbench's ResizeObserver anchor settle.
    await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
    await expect.poll(async()=>Math.abs((await page.locator('.pbl-workbench-stage').boundingBox())!.y)).toBeLessThan(1);
    await expect(scroller).toBeInViewport({ratio:1});
    expect(await scroller.evaluate(el=>el.scrollHeight-el.clientHeight)).toBeGreaterThan(100);
    await scroller.evaluate(el=>{el.scrollTop=el.scrollHeight;});
    await expect(page.locator('.cm-line').filter({hasText:'// 滚动检查 159'})).toBeInViewport();
    await page.screenshot({path:testInfo.outputPath(`editor-${width}.png`)});
    const outer=await page.locator('.sl-app').evaluate(el=>el.scrollTop);
    await scroller.hover();await page.mouse.wheel(0,-250);
    await expect.poll(()=>scroller.evaluate(el=>el.scrollHeight-el.clientHeight-el.scrollTop)).toBeGreaterThan(100);
    expect(await page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(outer);
  }
});
