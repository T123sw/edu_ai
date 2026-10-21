import assert from 'node:assert/strict';
import test from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { ProjectBrief } from './WorkbenchBrief';
import type { ProjectStep, UiCheck } from './projectTypes';

test('外壳题展示完整成果和所有本步检查，不把一个显示值当成输入输出示例',()=>{
  const step={instructionsMarkdown:'先做出计算器的样子：上方显示数字，下方排列按键。',checkIds:['screen','digits','operators']} as ProjectStep;
  const checks:UiCheck[]=[
    {id:'screen',label:'屏幕初始显示 0',actions:[{type:'assert',target:{testId:'display'},assertion:'text',expected:'0'}]},
    {id:'digits',label:'数字 0–9 和小数点按钮齐全',actions:[]},
    {id:'operators',label:'加减乘除、等号和清空按钮齐全',actions:[]},
    {id:'future',label:'计算结果为 3',actions:[]},
  ];
  const html=renderToStaticMarkup(createElement(ProjectBrief,{step,checks,deliverable:'完整的计算器外壳，暂时不需要计算。'}));
  for(const expected of ['完整的计算器外壳','屏幕初始显示 0','数字 0–9 和小数点按钮齐全','加减乘除、等号和清空按钮齐全'])assert.ok(html.includes(expected));
  for(const excluded of ['输入输出示例','输入：','输出：','计算结果为 3','data-testid'])assert.ok(!html.includes(excluded));
});

test('旧项目缺少成果说明时仍保留模型题面和完整本步检查，不编造结果',()=>{
  const step={instructionsMarkdown:'保留原有界面，实现连续点击增加。',checkIds:['increment']} as ProjectStep;
  const checks:UiCheck[]=[{id:'layout',label:'旧步骤界面',actions:[]},{id:'increment',label:'连续点击两次后显示 2',actions:[]}];
  const html=renderToStaticMarkup(createElement(ProjectBrief,{step,checks}));
  assert.ok(html.includes(step.instructionsMarkdown));
  assert.ok(html.includes('连续点击两次后显示 2'));
  assert.ok(!html.includes('旧步骤界面'));
});

test('通用分栏保留嵌套标题、代码围栏和跨栏引用，不重复生成成果',()=>{
  const step={objective:'后备成果',checkIds:[],instructionsMarkdown:'## 完成成果\n\n显示[资料][ref]。\n\n## 代码约定\n\n```js\n// ## 交互要求\nconst name = "name";\n```\n\n## 交互要求\n\n### 空值处理\n\n保留占位文字。\n\n[ref]: https://example.com/profile'} as unknown as ProjectStep;
  const html=renderToStaticMarkup(createElement(ProjectBrief,{step,checks:[],deliverable:'重复成果'}));
  const left=html.split('aria-label="要求与验收"')[0];
  assert.ok(left.includes('const name'));
  assert.ok(left.includes('href="https://example.com/profile"'));
  assert.ok(!left.includes('保留占位文字'));
  assert.ok(html.includes('保留占位文字'));
  assert.ok(!html.includes('重复成果'));
  assert.ok(!html.includes('本步验收'));
});
