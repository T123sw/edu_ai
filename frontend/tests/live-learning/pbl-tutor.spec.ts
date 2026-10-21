import {enterWorkbench} from './pblWorkbench';
import {test, expect, type Page} from 'playwright/test';
import {createHash} from 'node:crypto';
import type {TutorQuestion, TutorTurn} from '../../src/pbl/tutorTypes';

const files = {'/src/App.jsx': "export default function App(){return <button>增加</button>}", '/src/styles.css': 'body {padding:20px}'};
const artifact = {
  schemaVersion:2, runtimeKind:'react_app', templateVersion:'react-app-v1', exerciseId:'pbl_tutor_fixture',
  artifactVersion:1, topic:'计数器', title:'计数器项目', summary:'实现点击计数', starterFiles:files,
  plan:{goal:'实现计数器',steps:[{id:'layout',deliverable:'按钮'},{id:'count',deliverable:'计数'}]},
  tasks:[['layout','构建按钮'],['count','实现计数']].map(([id,title]) => ({id,stepId:id,title,objective:title,
    instructionsMarkdown:'实现本步功能。',explanationMarkdown:'通过界面反馈验证实现。',hints:['先尝试'],focusFiles:['/src/App.jsx'],checkIds:[id],cumulativeCheckIds:[id]})),
  checks:['layout','count'].map(id => ({id,label:id,actions:[{type:'assert',target:{role:'button',name:'增加'},assertion:'visible'}]})),validationSummary:{passed:true},
};
async function fixture(page:Page) {
  let workspace = {exerciseId:artifact.exerciseId,artifactVersion:1,revision:0,files:{...files},activeTaskId:'layout',customInputText:''};
  const turns:TutorTurn[] = [], requests:TutorQuestion[] = [];
  let gate:Promise<void> | undefined, release = () => {}, fail = false;
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'tutor_fixture',role:'student'}})));
  await page.route('**/api/**',async route => {
    const req=route.request(), url=new URL(req.url()), path=url.pathname.replace(/^\/backend/,'');
    if(!path.startsWith('/api/')) return route.continue();
    if(path.endsWith('/auth/verify')) return route.fulfill({json:{valid:true,user:{username:'tutor_fixture',role:'student'}}});
    if(path.endsWith('/self-learning/state')) return route.fulfill({json:{version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]}});
    if(path.endsWith('/workspace')) {
      if(req.method()==='PUT') workspace={...workspace,...req.postDataJSON(),revision:workspace.revision+1};
      return route.fulfill({json:workspace});
    }
    if(path.endsWith('/tutor')) {
      if(req.method()==='GET') return route.fulfill({json:{items:turns.filter(t=>t.taskId===url.searchParams.get('taskId')),nextCursor:null}});
      const p:TutorQuestion=req.postDataJSON(); requests.push(p);
      if(gate) await gate;
      if(fail) return route.fulfill({status:502,json:{detail:'辅导暂时不可用，请重试'}});
      const turn:TutorTurn={requestId:p.requestId,taskId:p.taskId,artifactVersion:1,question:p.question,
        answer:p.taskId==='layout'?'请检查按钮是否有可见文字。':'请观察点击事件是否更新状态。',
        codeHash:createHash('sha256').update(JSON.stringify(Object.fromEntries(Object.keys(p.files).sort().map(k=>[k,p.files[k]])))).digest('hex'),
        runId:null,evidenceSource:null,createdAt:Date.now()/1000};
      turns.push(turn); return route.fulfill({json:turn});
    }
    if(path.endsWith('/pbl_tutor_fixture')) return route.fulfill({json:{artifact,job:null}});
    return route.fulfill({json:{items:[]}});
  });
  return {requests,delay:()=>{gate=new Promise<void>(resolve=>{release=resolve;});},release:()=>release(),fail:(value:boolean)=>{fail=value;}};
}
async function openTutor(page:Page) {
  if(await page.locator('#pbl-tutor-toggle').getAttribute('aria-expanded')!=='true')await page.locator('#pbl-tutor-toggle').click();
  await expect(page.getByRole('button',{name:'给我一个下一步提示',exact:true})).toBeEnabled();
}
test('辅导绑定提问代码、保留新输入、失效提示与刷新恢复',async({page}) => {
  const store=await fixture(page);
  await page.goto('/#/practice/code/pbl_tutor_fixture');await enterWorkbench(page); await openTutor(page);
  store.delay(); await page.getByLabel('向编程辅导提问').fill('为什么按钮没有反应？');
  await page.getByRole('button',{name:'发送问题',exact:true}).click();
  await expect.poll(()=>store.requests.length).toBe(1);
  await page.getByLabel('向编程辅导提问').fill('第二个问题，先保留');
  const editor=page.locator('.cm-content[contenteditable=true]');await editor.click();
  await page.keyboard.press('ControlOrMeta+A');await page.keyboard.insertText(files['/src/App.jsx']+'\n// 新修改');
  await page.locator('#pbl-tutor-toggle').click();store.release();await openTutor(page);
  await expect(page.getByText('请检查按钮是否有可见文字。',{exact:true})).toBeVisible();
  await expect(page.getByLabel('向编程辅导提问')).toHaveValue('第二个问题，先保留');
  await expect(page.getByText('代码已修改，这条建议基于提问时的代码。')).toBeVisible();
  expect(store.requests[0].files['/src/App.jsx']).not.toContain('新修改');
  await expect(page.getByTestId('save-status')).toHaveText('已保存');
  await page.reload();await enterWorkbench(page);await openTutor(page);
  await expect(page.getByText('请检查按钮是否有可见文字。',{exact:true})).toBeVisible();
  await expect(page.getByText('代码已修改，这条建议基于提问时的代码。')).toBeVisible();
  for(const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});await openTutor(page);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.getByLabel('向编程辅导提问').scrollIntoViewIfNeeded();
    await page.screenshot({path:`../docs/acceptance/2026-10-14-pbl-tutor/tutor-${width}.png`});
  }
});
test('辅导失败重试复用编号，切步隔离迟到回答',async({page}) => {
  const store=await fixture(page);
  await page.goto('/#/practice/code/pbl_tutor_fixture');await enterWorkbench(page);await openTutor(page);
  store.fail(true);await page.getByLabel('向编程辅导提问').fill('怎样开始？');
  await page.getByRole('button',{name:'发送问题',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('辅导暂时不可用');
  await expect(page.getByLabel('向编程辅导提问')).toHaveValue('怎样开始？');
  store.fail(false);store.delay();await page.getByRole('button',{name:'发送问题',exact:true}).click();
  await expect.poll(()=>store.requests.length).toBe(2);
  expect(store.requests[0].requestId).toBe(store.requests[1].requestId);
  await page.getByRole('navigation',{name:'练习步骤'}).getByRole('button',{name:/实现计数/}).click();await openTutor(page);
  store.release();await expect(page.getByText('请检查按钮是否有可见文字。',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'给我一个下一步提示',exact:true}).click();
  await expect(page.getByText('请观察点击事件是否更新状态。',{exact:true})).toBeVisible();
  await expect(page.getByLabel('向编程辅导提问')).toHaveValue('');
  await page.getByRole('navigation',{name:'练习步骤'}).getByRole('button',{name:/构建按钮/}).click();await openTutor(page);
  await expect(page.getByText('请检查按钮是否有可见文字。',{exact:true})).toBeVisible();
  await expect(page.getByText('请观察点击事件是否更新状态。',{exact:true})).toHaveCount(0);
});

test('独立辅导侧栏与预览验收并排，收起与窄屏保留草稿和主视图',async({page})=>{
  await fixture(page);
  await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  await page.goto('/#/practice/code/pbl_tutor_fixture');await enterWorkbench(page);
  const sidebar=page.getByRole('complementary',{name:'AI 辅导'});
  const results=page.getByRole('navigation',{name:'项目结果'});
  await expect(sidebar).toBeVisible();await expect(results.getByRole('button')).toHaveCount(2);
  await expect(page.locator('.pbl-preview-panel')).toBeVisible();
  const preview=await page.locator('.pbl-result-pane').boundingBox(),aside=await sidebar.boundingBox();
  expect(aside!.x).toBeGreaterThan(preview!.x+preview!.width);
  await page.getByLabel('向编程辅导提问').fill('侧栏中尚未发送的问题');
  await page.screenshot({path:'/tmp/pbl-ai-sidebar-desktop.png'});
  await page.locator('#pbl-tutor-toggle').click();
  await expect(page.getByRole('button',{name:'AI 辅导',exact:true})).toBeFocused();
  await expect(sidebar).toBeHidden();await expect(page.locator('.pbl-preview-panel')).toBeVisible();
  await page.getByRole('button',{name:'验收',exact:true}).click();await openTutor(page);
  await expect(page.getByRole('button',{name:'验收',exact:true,includeHidden:true})).toHaveAttribute('aria-pressed','true');
  await expect(page.getByLabel('向编程辅导提问')).toHaveValue('侧栏中尚未发送的问题');
  await page.getByLabel('向编程辅导提问').press('Escape');await expect(sidebar).toBeHidden();
  for(const width of [1024,768,390,320]){
    await page.setViewportSize({width,height:844});
    if(width<=760)await page.getByRole('button',{name:'代码',exact:true}).click();
    await openTutor(page);await expect(sidebar).toBeInViewport({ratio:1});
    await expect(page.getByLabel('向编程辅导提问')).toHaveValue('侧栏中尚未发送的问题');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    if(width===390)await page.screenshot({path:'/tmp/pbl-ai-sidebar-mobile.png'});
    await page.locator('#pbl-tutor-toggle').click();
    await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});
    await expect(page.getByRole('button',{name:'验收',exact:true,includeHidden:true})).toHaveAttribute('aria-pressed','true');
  }
});
