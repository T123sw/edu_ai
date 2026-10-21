import {test,expect,type Page} from 'playwright/test';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {enterWorkbench} from './pblWorkbench';
import type {ProjectArtifact} from '../../src/pbl/projectTypes';

const liveDir=process.env.PBL_NATIVE_LIVE_DIR;
const api=process.env.PBL_NATIVE_API || 'http://127.0.0.1:8031';
const evidence=process.env.PBL_NATIVE_EVIDENCE || '../docs/acceptance/2026-10-17-pbl-sandpack-tests';
async function edit(page:Page,path:string,code:string){
  await page.getByRole('button',{name:path.split('/').pop()!,exact:true}).click();
  await page.locator('.cm-content[contenteditable=true]').click();
  await page.keyboard.press('ControlOrMeta+A');await page.keyboard.insertText(code);
}
for(const name of ['signup','reading'])test(`标准测试真实生成项目 ${name} 的页面和服务端验收`,async({page,request})=>{
  test.skip(!liveDir,'Requires native-test generation artifacts and a dedicated test account');test.setTimeout(600000);
  page.setDefaultTimeout(20000);
  const serverErrors:string[]=[];
  page.on('response',response=>{
    if(response.status()>=500&&new URL(response.url()).pathname.includes('/api/pbl/'))
      serverErrors.push(`${response.status()} ${new URL(response.url()).pathname}`);
  });
  const artifact:ProjectArtifact=JSON.parse(await readFile(`${liveDir}/${name}-artifact.json`,'utf8'));
  expect(artifact).toBeTruthy();
  const material=JSON.parse(await readFile(`${liveDir}/${name}-private.json`,'utf8'));
  const credentials=process.env.PBL_NATIVE_CREDENTIALS
    ? JSON.parse(await readFile(process.env.PBL_NATIVE_CREDENTIALS,'utf8'))
    : {username:'native_acceptance',password:'native-isolated-only'};
  const login=await request.post(api+'/api/auth/login',{data:credentials});
  expect(login.ok()).toBe(true);const auth=await login.json();
  const headers={Authorization:`Bearer ${auth.token}`};const path=api+'/api/pbl/'+artifact.exerciseId;
  const workspace=await(await request.get(path+'/workspace',{headers})).json();
  expect((await request.put(path+'/workspace',{headers,data:{artifactVersion:1,expectedRevision:workspace.revision,mutationId:crypto.randomUUID(),files:artifact.starterFiles,activeTaskId:artifact.tasks[0].id,customInputText:''}})).ok()).toBe(true);
  await page.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),auth);
  await page.goto(`/#/practice/code/${artifact.exerciseId}`);console.log(name,'page loaded');await enterWorkbench(page);console.log(name,'workbench opened');
  const status=page.getByTestId('task-status');
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(status).toHaveText('还需要调整');
  console.log(name,'starter rejected');
  const steps=[];
  for(let i=0;i<artifact.tasks.length;i++){
    const step=artifact.tasks[i];
    for(const [file,code] of Object.entries(material.completed[i].candidate.referenceFiles))await edit(page,file,code as string);
    await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(status).toHaveText('本步检查通过');
    const count=artifact.checks.filter(c=>'engine' in c&&step.cumulativeCheckIds.includes(c.id)).length;
    await page.getByRole('button',{name:'运行即时测试',exact:true}).click();
    await expect(page.locator('.pbl-native-tests').getByText(`${count} / ${count} 项通过`,{exact:true})).toBeVisible();
    console.log(name,step.id,'server and native passed');
    steps.push({stepId:step.id,checks:step.cumulativeCheckIds.length,nativeChecks:count,passed:true});
    if(i<artifact.tasks.length-1)await page.getByRole('button',{name:'下一步 →',exact:true}).click();
  }
  const finalFiles=material.completed.at(-1).candidate.referenceFiles;
  await edit(page,'/src/App.jsx','export default function App(){return <main>未实现功能</main>}');
  await expect(status).toHaveText('代码已修改，需重新检查');
  await expect(page.locator('.pbl-native-tests').getByText('代码已修改，请重新运行；下方结果对应修改前的代码。')).toBeVisible();
  await page.getByRole('button',{name:'运行即时测试',exact:true}).click();
  const total=artifact.checks.filter(c=>'engine' in c).length;
  await expect(page.locator('.pbl-native-tests').getByText(`0 / ${total} 项通过`,{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(status).toHaveText('还需要调整');
  await edit(page,'/src/App.jsx',finalFiles['/src/App.jsx']);
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(status).toHaveText('本步检查通过');
  await page.reload();await enterWorkbench(page);await expect(status).toHaveText('本步检查通过');
  await expect(page.locator('.cm-content')).toContainText('function');
  await mkdir(evidence,{recursive:true});
  for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:1000});
    if(width<=390)await page.getByRole('button',{name:'预览与验收',exact:true}).click();
    await page.getByRole('button',{name:'验收',exact:true}).click();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:`${evidence}/${name}-${width}.png`,fullPage:true});
  }
  const runs=await(await request.get(path+'/runs',{headers})).json();
  expect(runs.items.every((run:{evidenceSource:string})=>run.evidenceSource==='server_verified')).toBe(true);
  const detail=await(await request.get(path,{headers})).json();expect(JSON.stringify(detail)).not.toContain('referenceFiles');
  expect(serverErrors).toEqual([]);
  await writeFile(`${evidence}/${name}-flow.json`,JSON.stringify({passed:true,steps,runs:runs.items.length,serverErrors,tested:['empty starter fails','cumulative server execution','native browser execution','modified source invalidates results','broken source fails both runtimes','restore and refresh','320/390/1440 widths'],backend:process.env.PBL_NATIVE_ENVIRONMENT || 'isolated PostgreSQL with real API',generation:'actual model'},null,2));
});
