import {test,expect,type Page} from 'playwright/test';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {enterWorkbench} from './pblWorkbench';
import type {ProjectArtifact} from '../../src/pbl/projectTypes';
const dir=process.env.PBL_RUNTIME_LIVE_DIR;
const api=process.env.PBL_RUNTIME_API||'http://127.0.0.1:8032';
const evidence=process.env.PBL_RUNTIME_EVIDENCE||'/tmp/pbl-runtime-expansion/ui';
async function edit(page:Page,path:string,code:string){
 const label=page.getByRole('button',{name:path.split('/').pop()!,exact:true});
 await (await label.count()===1?label:page.getByRole('button',{name:path.slice(1),exact:true})).click();
 await page.locator('.cm-content[contenteditable=true]').click();await page.keyboard.press('ControlOrMeta+A');await page.keyboard.insertText(code);
}
for(const name of (process.env.PBL_RUNTIME_PROJECTS||'vanilla,vue,node,react-ts').split(','))test(`多环境真实生成项目 ${name} 编辑、预览、累计验收与保存`,async({page,request})=>{
 test.skip(!dir,'Requires isolated generated projects');test.setTimeout(600000);
 const artifact:ProjectArtifact=JSON.parse(await readFile(`${dir}/${name}-artifact.json`,'utf8'));
 const material=JSON.parse(await readFile(`${dir}/${name}-private.json`,'utf8'));
 const credentials=process.env.PBL_RUNTIME_CREDENTIALS?JSON.parse(await readFile(process.env.PBL_RUNTIME_CREDENTIALS,'utf8')):{username:'runtime_acceptance',password:'runtime-isolated-only'};
 const login=await request.post(api+'/api/auth/login',{data:credentials});expect(login.ok()).toBe(true);
 const auth=await login.json(),headers={Authorization:`Bearer ${auth.token}`},path=api+'/api/pbl/'+artifact.exerciseId;
 const workspace=await(await request.get(path+'/workspace',{headers})).json();
 expect((await request.put(path+'/workspace',{headers,data:{artifactVersion:1,expectedRevision:workspace.revision,mutationId:crypto.randomUUID(),files:artifact.starterFiles,activeTaskId:artifact.tasks[0].id,customInputText:''}})).ok()).toBe(true);
 await page.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),auth);
 await page.goto(`/#/practice/code/${artifact.exerciseId}`);await enterWorkbench(page);
 const status=page.getByTestId('task-status');console.log(name,'opened');
 await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(status).toHaveText('还需要调整',{timeout:180000});
 console.log(name,'starter rejected');const steps=[];
 for(let i=0;i<artifact.tasks.length;i++){
  const step=artifact.tasks[i];
  for(const [file,code] of Object.entries(material.completed[i].candidate.referenceFiles))await edit(page,file,code as string);
  await page.getByRole('button',{name:'页面预览',exact:true}).click();
  await expect.poll(async()=>{
   const frame=await (await page.locator('.sp-preview iframe:not(.sp-bridge-frame)').elementHandle())?.contentFrame();
   return frame?(await frame.locator('body').innerText().catch(()=>'' )).trim():'';
  },{timeout:90000}).not.toBe('');
  const preview=page.frameLocator('.sp-preview iframe:not(.sp-bridge-frame)');
  if(name==='react-ts'){await preview.getByTestId('text-input').fill('a b');await expect(preview.getByTestId('char-count')).toHaveText('3');}
  if(name==='vanilla'){await expect(async()=>{await preview.locator('[data-testid="celsius-input"], #celsius-input').fill('100');await preview.locator('[data-testid="convert-button"], #convert-button').click();await expect(preview.locator('[data-testid="result"], #result')).toHaveText('212',{timeout:2000});}).toPass({timeout:60000});}
  if(name==='vue'){await expect(async()=>{await preview.getByTestId('name-input').fill('张同学');await expect(preview.getByTestId('submit-button')).toBeEnabled();if(i>0){await preview.getByTestId('submit-button').click();await expect(preview.getByTestId('result-name')).toHaveText('张同学',{timeout:2000});}}).toPass({timeout:60000});}
  if(name==='node-read'){await expect(preview.locator('body')).toContainText('ok');if(i>0){const frame=await(await page.locator('.sp-preview iframe:not(.sp-bridge-frame)').elementHandle())!.contentFrame();await expect.poll(()=>frame!.evaluate(async()=>{const r=await fetch('/square?n=4');return r.json()}).catch(()=>null),{timeout:60000}).toEqual({result:16});}}
  await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(status).toHaveText('本步检查通过',{timeout:180000});
  console.log(name,step.id,'server passed');
  const native=artifact.checks.filter(c=>'engine' in c&&c.engine==='sandpack-jest'&&step.cumulativeCheckIds.includes(c.id));
  if(native.length){await page.getByRole('button',{name:'运行即时测试',exact:true}).click();await expect(page.locator('.pbl-native-tests').getByText(`${native.length} / ${native.length} 项通过`,{exact:true})).toBeVisible({timeout:90000})}
  console.log(name,step.id,'passed');steps.push({id:step.id,checks:step.cumulativeCheckIds.length,native:native.length});
  if(i<artifact.tasks.length-1)await page.getByRole('button',{name:'下一步 →',exact:true}).click();
 }
 const final=material.completed.at(-1).candidate.referenceFiles;
 const brokenFile=Object.keys(final).find(f=>f.endsWith('.vue')||f.endsWith('.tsx')&&f!==artifact.runtime?.entry)||artifact.runtime!.entry;
 await edit(page,brokenFile,'broken syntax !!!');await expect(status).toHaveText('代码已修改，需重新检查');
 await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(status).toHaveText('还需要调整',{timeout:180000});
 await edit(page,brokenFile,final[brokenFile]);await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(status).toHaveText('本步检查通过',{timeout:180000});
 await page.reload();await enterWorkbench(page);await expect(status).toHaveText('本步检查通过');
 const saved=await(await request.get(path+'/workspace',{headers})).json();expect(saved.files).toEqual(final);
 await mkdir(evidence,{recursive:true});
 for(const width of [1440,390]){await page.setViewportSize({width,height:1000});if(width===390)await page.getByRole('button',{name:'预览与验收',exact:true}).click();await page.getByRole('button',{name:'验收',exact:true}).click();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:`${evidence}/${name}-${width}.png`,fullPage:true})}
 const runs=await(await request.get(path+'/runs',{headers})).json();expect(runs.items.every(r=>r.evidenceSource==='server_verified')).toBe(true);
 await writeFile(`${evidence}/${name}.json`,JSON.stringify({passed:true,runtime:artifact.runtime,steps,runs:runs.items.length,files:Object.keys(final)},null,2));
});
