import {enterWorkbench} from './pblWorkbench';
import {test,expect,type Page} from 'playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import type {ProjectArtifact} from '../../src/pbl/projectTypes';
const evidence='../docs/acceptance/2026-10-14-pbl-project-integration';
async function edit(page:Page,path:string,code:string){await page.getByRole('button',{name:path.split('/').pop()!,exact:true}).click();await page.locator('.cm-content[contenteditable=true]').click();await page.keyboard.press('ControlOrMeta+A');await page.keyboard.insertText(code);await page.keyboard.press('ControlOrMeta+Home');await expect(page.locator('.cm-content')).toContainText(code.split('\n')[0]);}
test('真实四步计算器：逐步实现、累计检查、预览交互、回归失败与刷新恢复',async({page,request})=>{
  test.skip(process.env.PBL_PROJECT_LIVE!=='1','Requires isolated actual generated calculator');test.setTimeout(420000);
  const privateFixture=JSON.parse(await readFile('/tmp/pbl-project-acceptance-private.json','utf8'));
  const artifact:ProjectArtifact=JSON.parse(await readFile(`${evidence}/real-model-artifact.json`,'utf8'));
  const login=await request.post('http://127.0.0.1:8018/api/auth/login',{data:{username:'pbl_learner',password:'pbl-isolated-acceptance-only'}});expect(login.ok()).toBe(true);const auth=await login.json();
  await page.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),auth);
  const path=`http://127.0.0.1:8018/api/pbl/${artifact.exerciseId}`;const headers={Authorization:`Bearer ${auth.token}`};
  const before=await(await request.get(path+'/workspace',{headers})).json();
  await request.put(path+'/workspace',{headers,data:{artifactVersion:1,expectedRevision:before.revision,mutationId:crypto.randomUUID(),files:artifact.starterFiles,activeTaskId:artifact.tasks[0].id,customInputText:''}});
  await page.goto(`/#/practice/code/${artifact.exerciseId}`);await enterWorkbench(page);
  await expect(page.getByRole('heading',{name:artifact.tasks[0].title,exact:true})).toBeVisible();
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('还需要调整');
  const results=[];
  for(let index=0;index<artifact.tasks.length;index++){
    const task=artifact.tasks[index];
    await expect(page.getByRole('heading',{name:task.title,exact:true})).toBeVisible();
    const files=privateFixture.completed[index].candidate.referenceFiles;
    for(const [path,code] of Object.entries(files))await edit(page,path,code as string);
    await expect(page.getByTestId('save-status')).toHaveText('已保存');
    await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('本步检查通过');
    results.push({stepId:task.id,checks:task.cumulativeCheckIds.length,passed:true});
    await page.screenshot({path:`${evidence}/real-step-${index+1}.png`,fullPage:true});
    if(index<artifact.tasks.length-1)await page.getByRole('button',{name:'下一步 →',exact:true}).click();
  }
  await expect(page.getByText('项目全部功能已在当前代码中通过检查。')).toBeVisible();
  await page.getByRole('button',{name:'页面预览',exact:true}).click();
  const preview=page.frameLocator('.sp-preview iframe');
  const finalScenario=artifact.checks[artifact.checks.length-1];
  for(const action of finalScenario.actions){
    const locator=action.target.testId?preview.getByTestId(action.target.testId):preview.getByRole(action.target.role as 'button',{name:action.target.name,exact:true});
    if(action.type==='click')await locator.click();
    if(action.type==='assert'&&action.assertion==='text')await expect(locator).toHaveText(String(action.expected));
  }
  const finalFiles=privateFixture.completed.at(-1).candidate.referenceFiles;
  await edit(page,'/src/App.jsx',finalFiles['/src/App.jsx']+'\n// E2E 保留的代码');await expect(page.getByTestId('task-status')).toHaveText('代码已修改，需重新检查');
  await expect(page.getByTestId('save-status')).toHaveText('已保存');await page.reload();await enterWorkbench(page);await expect(page.getByRole('heading',{name:artifact.tasks.at(-1)!.title,exact:true})).toBeVisible();await edit(page,'/src/App.jsx',privateFixture.completed[0].candidate.referenceFiles['/src/App.jsx']);
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('还需要调整');
  await edit(page,'/src/App.jsx',finalFiles['/src/App.jsx']);await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('本步检查通过');await expect(page.getByTestId('save-status')).toHaveText('已保存');
  for(const width of [1440,390]){await page.setViewportSize({width,height:1000});if(width===390)await page.getByRole('button',{name:'预览与验收',exact:true}).click();await page.getByRole('button',{name:'页面预览',exact:true}).click();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:`${evidence}/real-${width}.png`,fullPage:true});}
  const detail=await(await request.get(path,{headers})).json();expect(JSON.stringify(detail)).not.toContain('referenceFiles');
  const runs=await(await request.get(path+'/runs',{headers})).json();expect(runs.items[0].status).toBe('passed');expect(runs.items.every((r:{evidenceSource:string})=>r.evidenceSource==='server_verified')).toBe(true);
  await writeFile(`${evidence}/real-flow.json`,JSON.stringify({passed:true,exerciseId:artifact.exerciseId,steps:results,runs:runs.items.length,checks:artifact.checks.length,backend:'real isolated PostgreSQL + actual model artifact + server browser checks',preview:'official hosted Sandpack React',tested:['empty starter rejection','cumulative checks per step','shared code across steps','interactive error recovery scenario','changed hash invalidation','refresh retains files and active step','later regression rejected','desktop/mobile layout']},null,2));
});
