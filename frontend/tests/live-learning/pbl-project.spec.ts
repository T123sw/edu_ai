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
test('多步骤共用工程、真实预览、检查失效、保存恢复与手机视图',async({page})=>{
  const store=await fixture(page);await page.goto('/#/practice/code/pbl_project_fixture');await enterWorkbench(page);
  await expect(page.getByRole('heading',{name:'构建按钮',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('还需要调整');
  await edit(page,solution);await page.getByRole('button',{name:'页面预览',exact:true}).click();const preview=page.frameLocator('.sp-preview iframe');await expect(preview.getByRole('button',{name:'增加',exact:true})).toBeVisible({timeout:90000});await preview.getByRole('button',{name:'增加',exact:true}).click();await expect(preview.locator('output')).toHaveText('1');
  await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();await enterWorkbench(page);await expect(preview.locator('output')).toHaveText('1');
  const previewBox=await page.locator('.sp-preview iframe').boundingBox();await page.mouse.move(previewBox!.x+80,previewBox!.y+60);await page.mouse.wheel(0,-180);await page.waitForTimeout(250);await expect(page.locator('.pbl-workbench-stage')).toHaveAttribute('data-focused','true');
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('本步检查通过');await expect(page.getByRole('navigation',{name:'练习步骤'})).toContainText('1 / 2 已通过');
  await page.getByRole('button',{name:'下一步 →',exact:true}).click();await expect(page.getByRole('heading',{name:'实现递增',exact:true})).toBeVisible();await expect(page.locator('.cm-content')).toContainText('useState');
  await expect(page.getByText('前序回归')).toHaveCount(1);await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByText('项目全部功能已在当前代码中通过检查。')).toBeVisible();
  await edit(page,solution+'\n// 我的修改');await expect(page.getByTestId('task-status')).toHaveText('代码已修改，需重新检查');await expect(page.getByRole('navigation',{name:'练习步骤'})).toContainText('0 / 2 已通过');await expect(page.getByTestId('save-status')).toHaveText('已保存');
  expect(store.get().activeTaskId).toBe('count');await page.reload();await enterWorkbench(page);await expect(page.getByRole('heading',{name:'实现递增',exact:true})).toBeVisible();await expect(page.locator('.cm-content')).toContainText('我的修改');await expect(page.getByTestId('task-status')).toHaveText('代码已修改，需重新检查');
  for(const width of [1440,390]){await page.setViewportSize({width,height:1000});if(width===390)await page.getByRole('button',{name:'预览与验收',exact:true}).click();await page.getByRole('button',{name:'页面预览',exact:true}).click();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:`../docs/acceptance/2026-10-14-pbl-project-integration/fixture-${width}.png`,fullPage:true});}
});
test('多文件离线草稿和步骤在刷新后恢复',async({page})=>{
  const store=await fixture(page);await page.goto('/#/practice/code/pbl_project_fixture');await enterWorkbench(page);await expect(page.locator('.cm-content')).toBeVisible();store.offline(true);await edit(page,solution+'\n// 离线');
  await expect(page.locator('.cm-content')).toContainText('离线');await page.getByRole('navigation',{name:'练习步骤'}).getByRole('button',{name:/实现递增/}).click();await expect(page.getByTestId('save-status')).toHaveText('本地已记录，待同步');await expect(page.locator('.cm-content')).toContainText('离线');await page.reload();await enterWorkbench(page);await expect(page.locator('.cm-content')).toContainText('离线');await expect(page.getByRole('heading',{name:'实现递增',exact:true})).toBeVisible();store.offline(false);await page.getByText('工程操作',{exact:true}).click();await page.getByRole('button',{name:'同步',exact:true}).click();await expect(page.getByTestId('save-status')).toHaveText('已保存');expect(store.get().files['/src/App.jsx']).toContain('离线');
});
test('长题目不挤占工作区，双栏及手机切换保留工程',async({page})=>{
  await fixture(page);
  const longArtifact=structuredClone(artifact);
  longArtifact.tasks[0].instructionsMarkdown=Array.from({length:18},(_,i)=>`${i+1}. 创建按钮并观察当前代码的页面效果。`).join('\n\n');
  await page.route('**/api/pbl/pbl_project_fixture',route=>route.fulfill({json:{artifact:longArtifact,job:null}}));
  for(const width of [1440,1024,900,768,720,701,700,390]){
    await page.setViewportSize({width,height:900});await page.goto('/#/practice/code/pbl_project_fixture');await enterWorkbench(page);await page.reload();await enterWorkbench(page);
    await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();await expect(page.getByRole('heading',{name:'动手实现计数器',exact:true})).toBeInViewport();await enterWorkbench(page);
    await expect(page.getByRole('button',{name:'检查本步',exact:true})).toBeInViewport();
    await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});
    const steps=page.getByRole('navigation',{name:'练习步骤'});await expect(steps).toBeInViewport({ratio:1});await expect(steps.getByRole('button',{name:/构建按钮/})).toHaveAttribute('aria-current','step');await expect(steps.getByRole('button')).toHaveCount(2);
    if(width>760){
      await expect(page.locator('.sp-preview')).toBeInViewport({ratio:1});
      const left=await page.locator('.sp-editor').boundingBox(),right=await page.locator('.sp-preview').boundingBox();
      const sidebar=await steps.boundingBox();expect(sidebar!.x+sidebar!.width).toBeLessThan(left!.x);
      expect(right!.x).toBeGreaterThan(left!.x+left!.width);expect(Math.abs(right!.y-left!.y)).toBeLessThan(80);
    }else{await page.getByRole('button',{name:'预览与验收',exact:true}).click();await expect(page.locator('.sp-preview')).toBeInViewport({ratio:1});}
    await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();await expect(page.getByRole('region',{name:'任务要求',exact:true})).toBeVisible();await expect(page.getByRole('region',{name:'本步完成要求',exact:true})).toBeVisible();
    await enterWorkbench(page);
    if(width<=760)await page.getByRole('button',{name:'代码',exact:true}).click();
    await edit(page,solution+'\n// 切换保留修改');
    if(width<=760)await page.getByRole('button',{name:'预览与验收',exact:true}).click();
    await page.getByRole('button',{name:'验收',exact:true}).click();await page.getByRole('button',{name:'页面预览',exact:true}).click();
    if(width<=760)await page.getByRole('button',{name:'代码',exact:true}).click();
    await expect(page.locator('.cm-content')).toContainText('切换保留修改');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }
});
test('预览交互状态在验收、辅导和切步后保留，分栏可调',async({page})=>{
  await fixture(page);await page.setViewportSize({width:1440,height:900});await page.goto('/#/practice/code/pbl_project_fixture');await enterWorkbench(page);
  await edit(page,solution);const preview=page.frameLocator('.sp-preview iframe');
  await expect(preview.getByRole('button',{name:'增加',exact:true})).toBeVisible({timeout:90000});await preview.getByRole('button',{name:'增加',exact:true}).click();await expect(preview.locator('output')).toHaveText('1');
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('本步检查通过');await expect(page.getByRole('navigation',{name:'练习步骤'})).toContainText('1 / 2 已通过');
  await page.getByRole('button',{name:'页面预览',exact:true}).click();await expect(preview.locator('output')).toHaveText('1');
  if(await page.locator('#pbl-tutor-toggle').getAttribute('aria-expanded')!=='true')await page.locator('#pbl-tutor-toggle').click();await page.getByLabel('向编程辅导提问').fill('保留我的问题');
  await page.getByRole('button',{name:'页面预览',exact:true}).click();await expect(preview.locator('output')).toHaveText('1');
  await page.locator('#pbl-tutor-toggle').click();if(await page.locator('#pbl-tutor-toggle').getAttribute('aria-expanded')!=='true')await page.locator('#pbl-tutor-toggle').click();await expect(page.getByLabel('向编程辅导提问')).toHaveValue('保留我的问题');
  await page.getByRole('navigation',{name:'练习步骤'}).getByRole('button',{name:/实现递增/}).click();await page.getByRole('button',{name:'页面预览',exact:true}).click();await expect(preview.locator('output')).toHaveText('1');
  const resize=page.getByRole('separator',{name:'调整代码区宽度'});await resize.focus();await page.keyboard.press('ArrowRight');await expect(resize).toHaveAttribute('aria-valuenow','52');
  const bounds=await resize.boundingBox();await page.mouse.move(bounds!.x+4,bounds!.y+20);await page.mouse.down();await page.mouse.move(bounds!.x+85,bounds!.y+20);await page.mouse.up();expect(Number(await resize.getAttribute('aria-valuenow'))).toBeGreaterThan(52);
  await page.getByRole('button',{name:'重新运行预览',exact:true}).click();await expect(preview.locator('output')).toHaveText('0',{timeout:90000});
  await expect(preview.getByRole('button',{name:'增加',exact:true})).toBeVisible({timeout:90000});await preview.getByRole('button',{name:'增加',exact:true}).click();await expect(preview.locator('output')).toHaveText('1');
});
