import {test,expect} from 'playwright/test';
import {readFile} from 'node:fs/promises';
import {enterWorkbench} from './pblWorkbench';
const dir=process.env.PBL_RUNTIME_LIVE_DIR;
const api=process.env.PBL_RUNTIME_API||'http://127.0.0.1:8032';
for(const name of ['react-ts','vanilla','vue','node-read'])test(`真实工作区预览操作 ${name}`,async({page,request})=>{
 test.skip(!dir,'Requires completed isolated projects');test.setTimeout(180000);
 const artifact=JSON.parse(await readFile(`${dir}/${name}-artifact.json`,'utf8'));
 const material=JSON.parse(await readFile(`${dir}/${name}-private.json`,'utf8'));
 const credentials=process.env.PBL_RUNTIME_CREDENTIALS?JSON.parse(await readFile(process.env.PBL_RUNTIME_CREDENTIALS,'utf8')):{username:'runtime_acceptance',password:'runtime-isolated-only'};
 const login=await request.post(api+'/api/auth/login',{data:credentials});expect(login.ok()).toBe(true);
 const auth=await login.json();await page.addInitScript(auth=>localStorage.setItem('edu-ai-auth',JSON.stringify(auth)),auth);
 await page.goto(`/#/practice/code/${artifact.exerciseId}`);await enterWorkbench(page);await page.getByRole('button',{name:'页面预览',exact:true}).click();
 const preview=page.frameLocator('.sp-preview iframe:not(.sp-bridge-frame)');
 if(name==='react-ts'){await preview.getByTestId('text-input').fill('a b',{timeout:90000});await expect(preview.getByTestId('char-count')).toHaveText('3');await preview.getByTestId('clear-button').click();await expect(preview.getByTestId('char-count')).toHaveText('0');}
 if(name==='vanilla'){await preview.locator('[data-testid="celsius-input"], #celsius-input').fill('100',{timeout:90000});await preview.locator('[data-testid="convert-button"], #convert-button').click();await expect(preview.locator('[data-testid="result"], #result')).toHaveText('212');await preview.locator('[data-testid="reset-button"], #reset-button').click();await expect(preview.locator('[data-testid="result"], #result')).toHaveText('');}
 if(name==='vue'){await preview.getByTestId('name-input').fill('张同学',{timeout:90000});await preview.getByTestId('submit-button').click();await expect(preview.getByTestId('result-name')).toHaveText('张同学');await preview.getByTestId('reset-button').click();await expect(preview.getByTestId('submit-button')).toBeDisabled();}
 if(name==='node-read'){
  await expect(preview.locator('body')).toContainText('ok',{timeout:90000});
  const get=async()=>{const frame=await(await page.locator('.sp-preview iframe:not(.sp-bridge-frame)').elementHandle())!.contentFrame();return frame!.evaluate(async()=>{const r=await fetch('/square?n=4');return r.json()})};
  expect(await get()).toEqual({result:16});
  const final=material.completed.at(-1).candidate.referenceFiles as Record<string,string>;
  const path=Object.keys(final).find(path=>/health/.test(path))!;expect(path).toBeTruthy();
  async function edit(code:string){await page.getByRole('button',{name:path.split('/').pop()!,exact:true}).click();await page.locator('.cm-content[contenteditable=true]').click();await page.keyboard.press('ControlOrMeta+A');await page.keyboard.insertText(code);}
  expect(final[path]).toContain('ok');
  try{await edit(final[path].replace('ok','updated'));await expect(preview.locator('body')).toContainText('updated',{timeout:60000});}
  finally{await edit(final[path]);await expect(preview.locator('body')).toContainText('ok',{timeout:60000});}
 }
});
