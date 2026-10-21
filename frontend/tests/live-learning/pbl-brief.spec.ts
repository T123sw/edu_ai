import {test,expect,type Page} from 'playwright/test';
import {readFileSync} from 'node:fs';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import candidate from '../../../backend/src/tests/pbl/fixtures/candidate.json';
import type {ExerciseArtifact} from '../../src/pbl/types';
import type {ProjectArtifact} from '../../src/pbl/projectTypes';
import {enterWorkbench} from './pblWorkbench';

const algorithm:ExerciseArtifact={title:candidate.title,summary:candidate.summary,starterCode:candidate.starterCode,testCases:candidate.testCases,schemaVersion:1,exerciseId:'pbl_brief_algorithm',artifactVersion:1,templateVersion:'js-function-v1',runtimeKind:'js_function',topic:'快速排序',contract:{...candidate.contract,exportName:'quickSort',mutatesInput:false,returnsNewArray:true},tasks:candidate.tasks.map(task=>({...task,testCaseIds:candidate.testCases.map(check=>check.id)})),validationSummary:{}};
const project:ProjectArtifact={schemaVersion:2,runtimeKind:'react_app',templateVersion:'react-app-v1',exerciseId:'pbl_brief_project',artifactVersion:1,topic:'计数器',title:'从界面到交互：实现计数器',summary:'点击按钮更新数值',starterFiles:{'/src/App.jsx':'export default function App(){return <main>开始编程</main>}', '/src/styles.css':''},plan:{goal:'计数器',steps:[]},tasks:[
  {id:'layout',stepId:'layout',title:'搭建计数器界面',objective:'添加显示区与增加按钮，初始显示 0。',instructionsMarkdown:'1. 创建一个显示区，初始文字为 `0`。\n2. 添加文字为「增加」的按钮。\n\n本步只需完成界面，下一步再实现点击交互。',explanationMarkdown:'先建立页面结构，再连接状态。',hints:['使用 button 元素。'],focusFiles:['/src/App.jsx','/src/styles.css'],checkIds:['visible'],cumulativeCheckIds:['visible']},
  {id:'count',stepId:'count',title:'实现点击递增',objective:'每次点击按钮，显示值增加 1。',instructionsMarkdown:'点击「增加」后，显示区从 `0` 变为 `1`；连续点击应继续增加。',explanationMarkdown:'使用 state 更新显示值。',hints:['在点击事件中更新计数。'],focusFiles:['/src/App.jsx'],checkIds:['increment'],cumulativeCheckIds:['visible','increment']}
],checks:[{id:'visible',label:'显示区初始为 0，增加按钮可用',actions:[{type:'assert',target:{testId:'display'},assertion:'text',expected:'0'}]},{id:'increment',label:'连续点击增加按钮，显示值依次为 1、2',actions:[{type:'click',target:{name:'增加'}},{type:'assert',target:{testId:'display'},assertion:'text',expected:'1'},{type:'click',target:{name:'增加'}},{type:'assert',target:{testId:'display'},assertion:'text',expected:'2'}]}],validationSummary:{}};

async function open(page:Page,artifact:ExerciseArtifact|ProjectArtifact) {
  let workspace={exerciseId:artifact.exerciseId,artifactVersion:1,revision:0,files:artifact.runtimeKind==='react_app'?artifact.starterFiles:{'/src/algorithm.js':artifact.starterCode},activeTaskId:artifact.tasks[0].id,customInputText:'[3,1,2]'};
  await page.addInitScript(()=>localStorage.setItem('edu-ai-auth',JSON.stringify({token:'fixture',user:{username:'brief_fixture',role:'student'}})));
  await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  await page.route('**/api/**',route=>{
    const req=route.request(),path=new URL(req.url()).pathname.replace(/^\/backend/,'');
    if(!path.startsWith('/api/'))return route.continue();
    if(path.endsWith('/auth/verify'))return route.fulfill({json:{valid:true,user:{username:'brief_fixture',role:'student'}}});
    if(path.endsWith('/self-learning/state'))return route.fulfill({json:{version:1,rooms:[],resources:[],jobs:[],serverJobs:[],shared:[]}});
    if(path.endsWith('/workspace')){if(req.method()==='PUT')workspace={...workspace,...req.postDataJSON(),revision:workspace.revision+1};return route.fulfill({json:workspace});}
    if(path.endsWith('/'+artifact.exerciseId))return route.fulfill({json:{artifact,job:null}});
    return route.fulfill({json:{items:[]}});
  });
  await page.goto('/#/practice/code/'+artifact.exerciseId);
  await expect(page.locator('.pbl-task-brief')).toBeVisible();
}

async function layout(page:Page,kind:string) {
  for(const width of [1920,1440,1024,768,390,320]){
    await page.setViewportSize({width,height:911});
    await page.locator('.sl-app').evaluate(el=>el.scrollTo({top:0,behavior:'instant'}));
    const requirements=page.getByRole('region',{name:kind==='algorithm'?'任务要求':'要求与验收',exact:true}),example=page.getByRole('region',{name:kind==='algorithm'?'输入输出示例':'本步验收',exact:true});
    await expect(requirements).toBeVisible();await expect(example).toHaveCount(1);
    const taskBox=await requirements.boundingBox(),exampleBox=await example.boundingBox();
    if(kind==='algorithm'){
      expect(exampleBox!.y).toBeGreaterThan(taskBox!.y+taskBox!.height);
      expect(Math.abs(exampleBox!.x-taskBox!.x)).toBeLessThan(1);
    }else{
      const columns=page.locator('.pbl-brief-columns');
      const style=await columns.evaluate(el=>({count:getComputedStyle(el).gridTemplateColumns.split(' ').length,rule:getComputedStyle(el,':before').width}));
      expect(style.count).toBe(width>1100?2:1);
      if(width>1100)expect(style.rule).toBe('1px');
      for(const side of ['.pbl-brief-context','.pbl-brief-requirements']){
        expect(await page.locator(side).evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgba(0, 0, 0, 0)');
      }
    }
    await expect(page.locator('.pbl-task-brief [data-testid="task-status"]')).toHaveCount(0);
    await expect(page.locator('.pbl-task-brief button')).toHaveCount(0);
    expect(await page.locator('.sl-app').evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
    await expect(page.getByRole('button',{name:'查看题目与提示',exact:true})).toHaveCount(0);
    await expect(page.locator('.pbl-task-brief details')).toHaveCount(0);
    await expect(page.getByRole('region',{name:'验收标准',exact:true})).toHaveCount(0);
    if([1440,390].includes(width))await page.screenshot({path:`/tmp/pbl-brief-balanced-${kind}-${width}.png`});
  }
}

test('算法题完整渲染模型正文，首个空示例会换成代表性输入输出',async({page})=>{
  const multiple=structuredClone(algorithm);
  multiple.tasks[0].examples.unshift({input:[],expected:[],explanation:'边界用例'});
  multiple.tasks[0].instructionsMarkdown='给定一个数字数组，请用快速排序得到升序结果。\n\n- 返回新数组，保持原数组不变。\n- 保留所有重复元素，允许负数与小数。\n\n**模型提供的特殊约束：禁止调用内置排序函数。**';
  await open(page,multiple);
  const example=page.getByRole('region',{name:'输入输出示例'});
  await expect(example).toContainText('[3,1,2]');await expect(example).toContainText('[1,2,3]');
  await expect(example).not.toContainText('[]');
  await expect(page.getByRole('region',{name:'任务要求'})).toContainText('模型提供的特殊约束：禁止调用内置排序函数。');
  await expect(page.getByRole('region',{name:'任务要求'})).toContainText('保持原数组不变');
  await layout(page,'algorithm');
  await enterWorkbench(page);await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});
  await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();await expect(example).toHaveCount(1);
});

test('项目完整展示题面与本步要求，切步不会混入前序检查',async({page})=>{
  const long=structuredClone(project);
  long.tasks[0].instructionsMarkdown=Array.from({length:18},(_,i)=> `要求 ${i+1}：这是需要完整呈现的模型原文。`).join('\n\n')+'\n\n最后一项约束：保留初始状态，显示区标识为 `display`。\n\n```js\nconst label = '+ 'x'.repeat(250) +';\n```';
  await open(page,long);await layout(page,'project');
  await expect(page.getByRole('region',{name:'要求与验收'})).toContainText('要求 18：这是需要完整呈现的模型原文。');
  await expect(page.getByRole('region',{name:'要求与验收'})).toContainText('最后一项约束');
  await expect(page.getByRole('region',{name:'要求与验收'})).not.toContainText(long.tasks[0].objective);
  await expect(page.getByRole('region',{name:'输入输出示例'})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'本步验收'})).toContainText('显示区初始为 0，增加按钮可用');
  await enterWorkbench(page);await page.getByRole('navigation',{name:'练习步骤'}).getByRole('button',{name:/实现点击递增/}).click();
  await expect(page.locator('.pbl-workbench-stage')).toHaveAttribute('data-focused','true');
  await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();
  await expect(page.locator('.pbl-brief-step')).toHaveText('第 2 / 2 步');
  await expect(page.getByRole('region',{name:'要求与验收'})).toContainText('连续点击应继续增加');
  await expect(page.getByRole('region',{name:'要求与验收'})).not.toContainText('最后一项约束');
  const outcome=page.getByRole('region',{name:'本步验收'});
  await expect(outcome).toContainText('连续点击增加按钮，显示值依次为 1、2');
  await expect(outcome).not.toContainText('显示区初始为 0');
  await expect(page.getByRole('region',{name:'输入输出示例'})).toHaveCount(0);
});

test('已有真实教材原文完整显示，每一步展示完整本步检查',async({page})=>{
  test.skip(!process.env.PBL_BRIEF_ARTIFACT,'Optional saved public teaching artifact');
  const artifact=JSON.parse(readFileSync(process.env.PBL_BRIEF_ARTIFACT!,'utf8')).artifact as ProjectArtifact;
  await open(page,artifact);await layout(page,'calculator');

  await page.setViewportSize({width:1920,height:911});
  await page.locator('.sl-app').evaluate(el=>el.scrollTo({top:0,behavior:'instant'}));

  for(const step of artifact.tasks){
    await enterWorkbench(page);await page.getByRole('navigation',{name:'练习步骤'}).getByRole('button',{name:new RegExp(step.title)}).click();
    await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();
    await expect.poll(()=>page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(0);
    const html=renderToStaticMarkup(createElement(ReactMarkdown,{children:step.instructionsMarkdown,skipHtml:true}));
    const expected=await page.evaluate(markup=>Array.from(new DOMParser().parseFromString(markup,'text/html').body.children).map(el=>el.textContent!.replace(/\s/g,'')),html);
    const actual=(await page.locator('.pbl-project-statement').textContent())!.replace(/\s/g,'');
    for(const block of expected)expect(actual).toContain(block);
    await expect(page.getByRole('region',{name:'本步验收'})).toHaveCount(1);
    for(const check of artifact.checks.filter(check=>step.checkIds.includes(check.id)))await expect(page.getByRole('region',{name:'本步验收'})).toContainText(check.label);
    for(const width of [1920,1440,1200]){
      await page.setViewportSize({width,height:911});
      await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
      const heights=await page.locator('.pbl-brief-columns').evaluate(el=>{
        return Array.from(el.children).map(child=>child.getBoundingClientRect().height);
      });
      console.log('Balanced brief',step.id,width,heights);
      expect(Math.abs(heights[0]-heights[1]),`${step.id} at ${width}: ${heights}`).toBeLessThan(Math.max(75,Math.max(...heights)*.2));
      if(width===1440)await page.screenshot({path:`/tmp/pbl-brief-balanced-step-${artifact.tasks.indexOf(step)+1}.png`});
    }
  }
});

test('模型生成的布局检查展示真实窗口及几何要求',async({page})=>{
  test.skip(!process.env.PBL_BRIEF_ARTIFACT,'Optional saved public teaching artifact');
  const artifact=JSON.parse(readFileSync(process.env.PBL_BRIEF_ARTIFACT!,'utf8')).artifact as ProjectArtifact;
  test.skip(!artifact.checks.some(check=>check.viewport==='mobile'),'Requires generated layout checks');
  await open(page,artifact);await enterWorkbench(page);
  await page.getByRole('button',{name:'验收',exact:true}).click();
  const panel=page.getByRole('region',{name:'步骤验收',exact:true});
  await expect(panel).toContainText('桌面窗口（1280 × 800）');
  await expect(panel).toContainText('手机窗口（390 × 844）');
  for(const detail of await panel.locator('details').all())await detail.locator('summary').click();
  await expect(panel).toContainText('「标记为 display 的部件」位于「按钮」上方');
  await expect(panel).toContainText('「按钮」之间互不重叠');
  await expect(panel).toContainText('「按钮」完整显示在检查窗口内');
  await expect(panel).not.toContainText('undefined');
});


test('题面按内容分栏，代码块完整保留，没有内容时不保留空栏',async({page})=>{
  const rich=structuredClone(project);
  rich.tasks[0].instructionsMarkdown='请把现有页面变成可填写的资料卡。\n\n## 完成成果\n\n能预览输入内容的资料卡。\n\n## 起点\n\n沿用现有工程。\n\n**代码约定**\n\n使用 `profile-name` 标记姓名框。\n\n```js\n// ## 验收要求不是标题\nconst field = "profile-name";\n```\n\n## 交互要求\n\n修改姓名后，预览同步更新。\n\n### 空值处理\n\n清空时显示占位文字。';
  await open(page,rich);await layout(page,'adaptive');
  const left=page.getByRole('region',{name:'成果与代码约定'}),right=page.getByRole('region',{name:'要求与验收'});
  for(const text of ['能预览输入内容的资料卡','profile-name','// ## 验收要求不是标题'])await expect(left).toContainText(text);
  await expect(right).toContainText('沿用现有工程');
  await expect(right).toContainText('修改姓名后，预览同步更新');
  await expect(right).toContainText('清空时显示占位文字');
  await expect(right).not.toContainText('profile-name');
  await expect(left).not.toContainText('连续点击增加按钮');
  const minimal=structuredClone(project);
  minimal.tasks[0].instructionsMarkdown='只需要保留这段说明。';minimal.tasks[0].objective='';minimal.tasks[0].checkIds=[];
  await open(page,minimal);
  await expect(page.getByRole('region',{name:'成果与代码约定'})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'本步验收'})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'要求与验收'})).toContainText('只需要保留这段说明');
});
