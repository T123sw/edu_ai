import {enterWorkbench} from './pblWorkbench';
import {spawn} from 'node:child_process';
function checkProject(input:unknown):Promise<{passed:boolean;results:ProjectReport['results']}>{return new Promise((resolve,reject)=>{
  const child=spawn(process.execPath,['scripts/check-pbl-project.mjs'],{cwd:process.cwd()});let output='',error='';
  const timeout=setTimeout(()=>{child.kill();reject(new Error('Checker timed out'));},30000);
  child.stdout.on('data',chunk=>output+=chunk);child.stderr.on('data',chunk=>error+=chunk);
  child.on('error',reason=>{clearTimeout(timeout);reject(reason);});child.on('close',code=>{clearTimeout(timeout);if(code!==0)reject(new Error(error));else {try{resolve(JSON.parse(output));}catch(reason){reject(reason);}}});
  child.stdin.end(JSON.stringify(input));
});}

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
    if(path.endsWith('/check')){const p=req.postDataJSON();const ids=p.taskId==='layout'?['button']:['button','increment'];const actual=await checkProject({files:p.files,checks:artifact.checks.filter(c=>ids.includes(c.id))});const passed=actual.passed;const report:ProjectReport={runId:p.runId,exerciseId:artifact.exerciseId,artifactVersion:1,templateVersion:'react-app-v1',taskId:p.taskId,codeHash:createHash('sha256').update(JSON.stringify(Object.fromEntries(Object.keys(p.files).sort().map(k=>[k,p.files[k]])))).digest('hex'),status:passed?'passed':'failed',results:actual.results,durationMs:15,evidenceSource:'server_verified'};runs.unshift(report);return route.fulfill({json:report});}
    if(path.endsWith('/runs'))return route.fulfill({json:{items:runs}});
    if(path.endsWith('/pbl_project_fixture'))return route.fulfill({json:{artifact,job:null}});
    return route.fulfill({json:{items:[]}});
  });
  return {get:()=>workspace,offline:(v:boolean)=>{failSave=v;}};
}
test('真实验收记录展示点击顺序与预期实际差异，辅导接收失败项',async({page})=>{
  await fixture(page);await page.setViewportSize({width:1440,height:900});await page.goto('/#/practice/code/pbl_project_fixture');await enterWorkbench(page);
  await page.getByRole('navigation',{name:'练习步骤'}).getByRole('button',{name:/实现递增/}).click();
  const broken=solution.replace('set(n+1)','set(n+2)').replace('<output>','<output data-testid="display">');
  await edit(page,broken);const preview=page.frameLocator('.sp-preview iframe');
  await expect(preview.getByRole('button',{name:'增加',exact:true})).toBeVisible({timeout:90000});await preview.getByRole('button',{name:'增加',exact:true}).click();await expect(preview.locator('output')).toHaveText('2');
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('还需要调整');
  const failure=page.locator('.pbl-check-card.failed');await expect(failure).toContainText('预期："1"');await expect(failure).toContainText('实际："2"');await expect(failure).toContainText('点击 "增加"');
  await page.screenshot({path:'/tmp/pbl-workbench-evidence.png'});
  await failure.getByRole('button',{name:'请 AI 分析失败原因'}).click();await expect(page.getByLabel('向编程辅导提问')).toHaveValue(/点击后显示1/);await expect(page.getByRole('button',{name:'验收',exact:true})).toHaveAttribute('aria-pressed','true');await expect(page.getByRole('complementary',{name:'AI 辅导'})).toBeVisible();
  await page.getByRole('button',{name:'页面预览',exact:true}).click();await expect(preview.locator('output')).toHaveText('2');
  await edit(page,broken.replace('set(n+2)','set(n+1)'));await expect(page.getByTestId('task-status')).toHaveText('代码已修改，需重新检查');
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('本步检查通过');
  await expect(page.getByText('项目全部功能已在当前代码中通过检查。')).toBeVisible();await page.reload();await enterWorkbench(page);await page.getByRole('button',{name:'验收',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('本步检查通过');
});
