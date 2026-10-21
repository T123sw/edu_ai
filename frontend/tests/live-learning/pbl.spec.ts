import {enterWorkbench} from './pblWorkbench';
import {test,expect,type Page} from 'playwright/test';
import candidate from '../../../backend/src/tests/pbl/fixtures/candidate.json';
import {testCases,referenceSolution} from '../../src/pbl/fixtures/quicksort';

const artifact={schemaVersion:1,exerciseId:'pbl_fixture',artifactVersion:1,templateVersion:'js-function-v1',runtimeKind:'js_function',topic:'快速排序',title:candidate.title,summary:candidate.summary,contract:candidate.contract,starterCode:candidate.starterCode,tasks:candidate.tasks.map(t=>({...t,testCaseIds:testCases.map(c=>c.id)})),testCases,validationSummary:{passed:true,templateVersion:'js-function-v1'}};
async function edit(page:Page,code:string) {await enterWorkbench(page);const editor=page.locator('.cm-content[contenteditable=true]');await editor.click();await page.keyboard.press('ControlOrMeta+A');await page.keyboard.insertText(code);}
async function openTools(page:Page) {if(!await page.getByRole('button',{name:'同步',exact:true}).isVisible())await page.getByText('工程操作',{exact:true}).click();}
async function fixture(page:Page) {
  let workspace={exerciseId:'pbl_fixture',artifactVersion:1,revision:0,files:{'/src/algorithm.js':artifact.starterCode},activeTaskId:'implement-sort',customInputText:'[3,1,2]',updatedAt:Date.now()/1000};
  const runs:unknown[]=[];
  await page.addInitScript(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'pbl_fixture_user',role:'student'}})));
  await page.route('**/api/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname.replace(/^\/backend/,'');
    if(!path.startsWith('/api/'))return route.continue();
    if(path.endsWith('/auth/verify'))return route.fulfill({json:{valid:true,user:{username:'pbl_fixture_user',role:'student'}}});
    if(path.endsWith('/self-learning/state'))return route.fulfill({json:{version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]}});
    if(path==='/api/pbl'&&req.method()==='POST')return route.fulfill({json:{exerciseId:'pbl_fixture',jobId:'job_fixture',status:'queued'}});
    if(path==='/api/pbl')return route.fulfill({json:{items:[]}});
    if(path.endsWith('/workspace')) {
      if(req.method()==='PUT'){const body=req.postDataJSON();if(body.expectedRevision!==workspace.revision)return route.fulfill({status:409,json:{detail:'版本冲突'}});workspace={...workspace,...body,revision:workspace.revision+1};}
      return route.fulfill({json:workspace});
    }
    if(path.endsWith('/runs')){if(req.method()==='POST'){runs.unshift(req.postDataJSON());return route.fulfill({json:runs[0]});}return route.fulfill({json:{items:runs}});}
    if(path==='/api/pbl/pbl_fixture')return route.fulfill({json:{exerciseId:'pbl_fixture',job:{status:'succeeded'},artifact}});
    return route.fulfill({json:{items:[]}});
  });
  return {getWorkspace:()=>workspace};
}
test('固定练习：首页、错误修正、代码失效和刷新恢复',async({page})=>{
  page.on('pageerror',error=>console.log('PBL page error:',error.message));
  const storage=await fixture(page);
  await page.goto('/#/practice/code');
  await page.getByLabel('实验主题与目标').fill('快速排序');await page.getByRole('button',{name:'生成项目'}).click();
  await page.getByRole('button',{name:'进入项目',exact:true}).click();
  await expect(page.getByRole('heading',{name:'实现快速排序',exact:true})).toBeVisible();
  await expect(page.getByText('运行环境已就绪',{exact:true})).toBeVisible({timeout:90000});
  const runtime=page.frameLocator('.sp-preview iframe');
  await edit(page,'export function quickSort(array) { return array.filter((v,i,a)=>a.indexOf(v)===i).sort((a,b)=>a-b); }');
  await runtime.getByRole('button',{name:'检查练习',exact:true}).click();
  await expect(runtime.getByText('还需要调整',{exact:true})).toBeVisible();
  await expect(runtime.locator('.case.failed')).toContainText('重复元素');
  await edit(page,referenceSolution);
  await runtime.getByRole('button',{name:'检查练习',exact:true}).click();
  await expect(page.getByTestId('task-status')).toHaveText('全部用例通过');
  await edit(page,referenceSolution+'\n// 再次观察');
  await expect(page.getByTestId('task-status')).toHaveText('代码已修改，需重新检查');
  await expect(page.getByTestId('save-status')).toHaveText('已保存');
  expect(storage.getWorkspace().files['/src/algorithm.js']).toContain('再次观察');
  await page.reload();await enterWorkbench(page);
  await expect(page.locator('.cm-content')).toContainText('再次观察');
  await expect(page.getByTestId('task-status')).toHaveText('代码已修改，需重新检查');
  await expect(page.getByText('运行环境已就绪',{exact:true})).toBeVisible({timeout:90000});
  await runtime.getByRole('button',{name:'检查练习',exact:true}).click();
  await expect(page.getByTestId('task-status')).toHaveText('全部用例通过');
  for(const width of [1440,1024,390]){
    await page.setViewportSize({width,height:1000});
    if(width===390){await page.getByRole('button',{name:'预览与验收',exact:true}).click();await page.getByRole('button',{name:'运行结果',exact:true}).click();await expect(runtime.getByText('检查通过',{exact:true})).toBeVisible();}
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:`../docs/acceptance/2026-10-13-sandpack-algorithm-practice/fixture-${width}.png`,fullPage:true});
  }
});

test('延迟保存响应不覆盖新编辑，冲突时保留两份代码',async({page})=>{
  const storage=await fixture(page);
  let release:()=>void=()=>{};
  let pending=false;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/api/pbl/*/workspace',async route=>{
    if(route.request().method()==='PUT'&&!pending){pending=true;await gate;}
    await route.fallback();
  });
  await page.goto('/#/practice/code/pbl_fixture');await enterWorkbench(page);
  await expect(page.locator('.cm-content')).toBeVisible();
  await edit(page,referenceSolution+'\n// A');
  await expect.poll(()=>pending).toBe(true);
  await edit(page,referenceSolution+'\n// B');
  release();
  await expect(page.getByTestId('save-status')).toHaveText('已保存');
  await expect(page.locator('.cm-content')).toContainText('// B');
  expect(storage.getWorkspace().files['/src/algorithm.js']).toContain('// B');
  const remote=storage.getWorkspace();remote.revision++;remote.files={'/src/algorithm.js':referenceSolution+'\n// other tab'};
  await edit(page,referenceSolution+'\n// local');
  await expect(page.getByRole('button',{name:'保留本地草稿'})).toBeVisible();
  await expect(page.locator('.cm-content')).toContainText('// local');
  await page.getByRole('button',{name:'保留本地草稿'}).click();
  await expect(page.getByTestId('save-status')).toHaveText('已保存');
  expect(storage.getWorkspace().files['/src/algorithm.js']).toContain('// local');
  await openTools(page);await page.getByRole('button',{name:'恢复备份'}).click();
  await expect(page.locator('.cm-content')).toContainText('// other tab');
});

test('离线草稿刷新后恢复，运行环境重试保留代码',async({page})=>{
  const storage=await fixture(page);
  let offline=true;
  await page.route('**/api/pbl/*/workspace',async route=>{
    if(offline&&route.request().method()==='PUT')return route.abort('internetdisconnected');
    await route.fallback();
  });
  await page.goto('/#/practice/code/pbl_fixture');await enterWorkbench(page);
  await expect(page.locator('.cm-content')).toBeVisible();
  await edit(page,referenceSolution+'\n// offline draft');
  await expect(page.getByTestId('save-status')).toHaveText('本地已记录，待同步');
  await page.reload();await enterWorkbench(page);await expect(page.locator('.cm-content')).toContainText('// offline draft');
  offline=false;await openTools(page);await page.getByRole('button',{name:'同步',exact:true}).click();
  await expect(page.getByTestId('save-status')).toHaveText('已保存');
  expect(storage.getWorkspace().files['/src/algorithm.js']).toContain('// offline draft');
  await expect(page.getByText('运行环境已就绪',{exact:true})).toBeVisible({timeout:90000});
  await page.getByRole('button',{name:'重试运行环境'}).click();
  await expect(page.getByText('运行环境已就绪',{exact:true})).toBeVisible({timeout:90000});
  await expect(page.locator('.cm-content')).toContainText('// offline draft');
});

test('运行环境不可达时仍可保存，重新连接后继续运行',async({page})=>{
  await fixture(page);
  let blocked=true;
  await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>blocked?route.abort('internetdisconnected'):route.continue());
  await page.goto('/#/practice/code/pbl_fixture');await enterWorkbench(page);await expect(page.locator('.cm-content')).toBeVisible();
  await edit(page,referenceSolution+'\n// bundler unavailable');
  await expect(page.getByTestId('save-status')).toHaveText('已保存');
  blocked=false;await page.getByRole('button',{name:'重试运行环境'}).click();
  await expect(page.getByText('运行环境已就绪',{exact:true})).toBeVisible({timeout:90000});
  await expect(page.locator('.cm-content')).toContainText('// bundler unavailable');
  const runtime=page.frameLocator('.sp-preview iframe');
  await runtime.getByRole('button',{name:'检查练习',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('全部用例通过');
});

test('运行中编辑与停止保留快照，样例通过不等于完成',async({page})=>{
  await fixture(page);await page.goto('/#/practice/code/pbl_fixture');await enterWorkbench(page);
  await expect(page.getByText('运行环境已就绪',{exact:true})).toBeVisible({timeout:90000});
  const runtime=page.frameLocator('.sp-preview iframe');
  await edit(page,'export function quickSort(array) { while (true) {} }');
  await runtime.getByRole('button',{name:'检查练习',exact:true}).click();
  await expect(page.getByText('正在运行',{exact:true})).toBeVisible();
  await edit(page,referenceSolution);
  await runtime.getByRole('button',{name:'停止',exact:true}).click();
  await expect(runtime.getByText('已停止运行',{exact:true})).toBeVisible();
  await expect(page.getByTestId('task-status')).toHaveText('代码已修改，需重新检查');
  await runtime.getByRole('button',{name:'运行一次',exact:true}).click();
  await expect(runtime.getByText('检查通过',{exact:true})).toBeVisible();
  await expect(page.getByTestId('task-status')).not.toHaveText('全部用例通过');
});

for(const recovery of ['manual','online'] as const) {
  test(`冲突读取失败后通过 ${recovery} 重试，选择前保留两份代码`,async({page})=>{
    const storage=await fixture(page);
    let failConflictRead=false;
    let puts=0;
    await page.route('**/api/pbl/*/workspace',async route=>{
      if(route.request().method()==='PUT')puts++;
      if(route.request().method()==='GET'&&failConflictRead)return route.abort('internetdisconnected');
      await route.fallback();
    });
    await page.goto('/#/practice/code/pbl_fixture');await enterWorkbench(page);
    await expect(page.locator('.cm-content')).toBeVisible();
    const remote=storage.getWorkspace();remote.revision++;remote.files={'/src/algorithm.js':referenceSolution+'\n// remote conflict'};
    failConflictRead=true;
    await edit(page,referenceSolution+'\n// local conflict');
    await expect(page.getByTestId('save-status')).toHaveText('保存冲突，请点击同步或连接恢复后重试');
    expect(puts).toBe(1);
    failConflictRead=false;
    if(recovery==='manual'){await openTools(page);await page.getByRole('button',{name:'同步',exact:true}).click();}
    else await page.evaluate(()=>window.dispatchEvent(new Event('online')));
    await expect(page.getByRole('button',{name:'保留本地草稿'})).toBeVisible();
    await expect(page.getByRole('button',{name:'使用服务器版本'})).toBeVisible();
    await expect(page.locator('.cm-content')).toContainText('// local conflict');
    expect(storage.getWorkspace().files['/src/algorithm.js']).toContain('// remote conflict');
    expect(puts).toBe(1);
    await page.getByRole('button',{name:'保留本地草稿'}).click();
    await expect(page.getByTestId('save-status')).toHaveText('已保存');
    expect(storage.getWorkspace().files['/src/algorithm.js']).toContain('// local conflict');
    await openTools(page);await page.getByRole('button',{name:'恢复备份'}).click();
    await expect(page.locator('.cm-content')).toContainText('// remote conflict');
  });
}

test('报告上传期间的新编辑在显示已保存前继续同步',async({page})=>{
  const storage=await fixture(page);
  let releaseReport:()=>void=()=>{},releaseWorkspace:()=>void=()=>{};
  const reportGate=new Promise<void>(resolve=>{releaseReport=resolve;});
  const workspaceGate=new Promise<void>(resolve=>{releaseWorkspace=resolve;});
  let reportPending=false,workspacePending=false;
  await page.route('**/api/pbl/*/runs',async route=>{
    if(route.request().method()==='POST'){reportPending=true;await reportGate;}
    await route.fallback();
  });
  await page.route('**/api/pbl/*/workspace',async route=>{
    if(route.request().method()==='PUT'&&reportPending){workspacePending=true;await workspaceGate;}
    await route.fallback();
  });
  await page.goto('/#/practice/code/pbl_fixture');await enterWorkbench(page);
  await expect(page.getByText('运行环境已就绪',{exact:true})).toBeVisible({timeout:90000});
  await edit(page,referenceSolution);
  await expect(page.getByTestId('save-status')).toHaveText('已保存');
  await page.frameLocator('.sp-preview iframe').getByRole('button',{name:'检查练习',exact:true}).click();
  await expect.poll(()=>reportPending).toBe(true);
  await edit(page,referenceSolution+'\n// edited during report');
  // Let the 800 ms debounce fire while the report request remains in flight.
  await page.waitForTimeout(1100);
  expect(workspacePending).toBe(false);
  await expect(page.getByTestId('save-status')).not.toHaveText('已保存');
  releaseReport();
  await expect.poll(()=>workspacePending,{timeout:10000}).toBe(true);
  await expect(page.getByTestId('save-status')).toHaveText('正在保存');
  expect(storage.getWorkspace().files['/src/algorithm.js']).not.toContain('// edited during report');
  releaseWorkspace();
  await expect(page.getByTestId('save-status')).toHaveText('已保存');
  expect(storage.getWorkspace().files['/src/algorithm.js']).toContain('// edited during report');
});

test('保存响应丢失后先重放原变更，再同步最新编辑',async({page})=>{
  const storage=await fixture(page);
  let release:()=>void=()=>{};
  const gate=new Promise<void>(resolve=>{release=resolve;});
  const patches:Record<string,unknown>[]=[];
  await page.route('**/api/pbl/*/workspace',async route=>{
    if(route.request().method()!=='PUT')return route.fallback();
    const patch=route.request().postDataJSON();patches.push(patch);
    if(patches.length===1){
      Object.assign(storage.getWorkspace(),patch,{revision:1});
      await gate;return route.abort('internetdisconnected');
    }
    if(patches.length===2)return route.fulfill({json:storage.getWorkspace()});
    await route.fallback();
  });
  await page.goto('/#/practice/code/pbl_fixture');await enterWorkbench(page);
  await expect(page.locator('.cm-content')).toBeVisible();
  await edit(page,referenceSolution+'\n// uncertain A');
  await expect.poll(()=>patches.length).toBe(1);
  await edit(page,referenceSolution+'\n// newer B');
  await page.waitForTimeout(1100);
  release();
  await expect(page.getByTestId('save-status')).toHaveText('本地已记录，待同步');
  await openTools(page);await page.getByRole('button',{name:'同步',exact:true}).click();
  await expect(page.getByTestId('save-status')).toHaveText('已保存');
  expect(patches).toHaveLength(3);
  expect(patches[1]).toEqual(patches[0]);
  expect(patches[2].mutationId).not.toBe(patches[0].mutationId);
  expect(patches[2].expectedRevision).toBe(1);
  expect(storage.getWorkspace().files['/src/algorithm.js']).toContain('// newer B');
  await expect(page.locator('.cm-content')).toContainText('// newer B');
});

test('单步算法共用双栏工作台，顶部验收与辅导切换保留运行输入',async({page})=>{
  await fixture(page);await page.setViewportSize({width:1440,height:900});await page.goto('/#/practice/code/pbl_fixture');await enterWorkbench(page);
  await expect(page.getByText('运行环境已就绪',{exact:true})).toBeVisible({timeout:90000});
  const runtime=page.frameLocator('.sp-preview iframe');await runtime.getByLabel('输入数组').fill('[9,4,7]');
  await edit(page,referenceSolution);await page.getByRole('button',{name:'检查本步',exact:true}).click();
  await expect(page.getByTestId('task-status')).toHaveText('全部用例通过');await expect(page.getByRole('region',{name:'步骤验收'})).toBeVisible();
  await expect(page.locator('.pbl-check-card.passed')).toHaveCount(testCases.length);
  await page.getByRole('button',{name:'运行结果',exact:true}).click();await expect(runtime.getByLabel('输入数组')).toHaveValue('[9,4,7]');
  if(await page.locator('#pbl-tutor-toggle').getAttribute('aria-expanded')!=='true')await page.locator('#pbl-tutor-toggle').click();await page.getByLabel('向编程辅导提问').fill('我的递归何时结束？');
  await page.getByRole('button',{name:'运行结果',exact:true}).click();await expect(runtime.getByLabel('输入数组')).toHaveValue('[9,4,7]');
  await page.locator('#pbl-tutor-toggle').click();if(await page.locator('#pbl-tutor-toggle').getAttribute('aria-expanded')!=='true')await page.locator('#pbl-tutor-toggle').click();await expect(page.getByLabel('向编程辅导提问')).toHaveValue('我的递归何时结束？');
  await page.getByRole('button',{name:'运行结果',exact:true}).click();
  const resize=page.getByRole('separator',{name:'调整代码区宽度'});await resize.focus();await page.keyboard.press('ArrowRight');await expect(resize).toHaveAttribute('aria-valuenow','52');
  for(const width of [1440,1024,900,768,720,700,390,320]){
    await page.setViewportSize({width,height:900});
    if(width<=760)await page.getByRole('button',{name:'代码',exact:true}).click();
    await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});await expect(page.getByRole('button',{name:'检查本步',exact:true})).toBeInViewport();
    if(width<=760)await page.getByRole('button',{name:'预览与验收',exact:true}).click();
    await expect(page.locator('.sp-preview')).toBeInViewport({ratio:1});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();await expect(page.getByRole('region',{name:'任务要求',exact:true})).toBeVisible();await expect(page.getByRole('region',{name:'输入输出示例',exact:true})).toBeVisible();await enterWorkbench(page);
    if([1440,390].includes(width))await page.screenshot({path:`/tmp/pbl-unified-algorithm-${width}.png`});
  }
});
