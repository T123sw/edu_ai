import test from 'node:test';
import assert from 'node:assert/strict';
import {checkProject} from './check-pbl-project.mjs';

const code=`import React,{useState} from 'react';
export function sum(values){return values.reduce((a,b)=>a+b,0)}
export default function App(){const [name,setName]=useState('');const [items,setItems]=useState([]);const [picked,setPicked]=useState(false);
return <main><input aria-label="名称" value={name} onChange={e=>setName(e.target.value)}/><button disabled={!name.trim()} onClick={()=>{setItems([...items,name]);setName('')}}>添加</button><ul>{items.map((item,i)=><li key={i}>{item}<button onClick={()=>setItems(items.filter((_,j)=>j!==i))}>删除</button></li>)}</ul><input type="radio" aria-label="选项" checked={picked} onChange={()=>setPicked(true)}/><output>{String(picked)}</output></main>}`;
const files={'/src/App.jsx':code,'/src/styles.css':''};
const prefix=`import React from 'react';import {render,screen,fireEvent,within,waitFor} from '@testing-library/react';import App,{sum} from '../src/App.jsx';`;
const native=(id,source)=>({id,label:id,engine:'sandpack-jest',source:prefix+source});
const checks=[
  native('form',`test('禁用与空集合',()=>{render(<App/>);expect(screen.getByRole('button',{name:'添加'}).disabled).toBe(true);expect(screen.queryAllByRole('listitem')).toHaveLength(0)});test('添加和重复项隔离',async()=>{render(<App/>);for(let i=0;i<2;i++){fireEvent.change(screen.getByLabelText('名称'),{target:{value:'同名'}});fireEvent.click(screen.getByRole('button',{name:'添加'}))}await waitFor(()=>expect(screen.getAllByRole('listitem')).toHaveLength(2));fireEvent.click(within(screen.getAllByRole('listitem')[1]).getByRole('button'));expect(screen.getAllByRole('listitem')).toHaveLength(1);expect(screen.getByLabelText('名称').value).toBe('')});`),
  native('radio',`test('单选重复点击保持选中',()=>{render(<App/>);const radio=screen.getByRole('radio');fireEvent.click(radio);fireEvent.click(radio);expect(radio.checked).toBe(true);expect(screen.getByRole('status').textContent).toBe('true')});`),
  native('function',`describe('纯函数',()=>{test('空值与正负数',()=>{expect(sum([])).toBe(0);expect(sum([3,-2,4])).toBe(5)})});`),
];

test('原生组件/纯函数/异步/重复项与旧页面检查累计执行', {timeout:90000},async()=>{
  const report=await checkProject({files,checks:[...checks,{id:'legacy',actions:[{type:'assert',target:{role:'button',name:'添加'},assertion:'visible'}]}]});
  assert.equal(report.passed,true,JSON.stringify(report));assert.deepEqual(report.results.map(r=>r.caseId),['form','radio','function','legacy']);
});
test('破坏禁用与删除行为会被标准测试发现', {timeout:90000},async()=>{
  const broken=code.replace('disabled={!name.trim()}','disabled={false}').replace('items.filter((_,j)=>j!==i)','[]');
  const report=await checkProject({files:{...files,'/src/App.jsx':broken},checks:[checks[0]]});
  assert.equal(report.passed,false);assert.match(report.results[0].message,/Expected/);
});
test('空文件、无断言、跳过和测试语法错误不能空通过', {timeout:90000},async()=>{
  const report=await checkProject({files,checks:[
    {id:'empty',engine:'sandpack-jest',source:'// no tests'},
    {id:'vacuous',engine:'sandpack-jest',source:'test("no assertion",()=>{});'},
    {id:'skipped',engine:'sandpack-jest',source:'test.skip("skipped",()=>expect(1).toBe(1));'},
    {id:'syntax',engine:'sandpack-jest',source:'test("syntax",()=>{ broken syntax });'},
  ]});
  assert.equal(report.passed,false);assert.ok(report.results.every(r=>r.status==='failed'),JSON.stringify(report));
});
test('学生代码语法错误返回失败，不能计为通过', {timeout:90000},async()=>{
  const report=await checkProject({files:{...files,'/src/App.jsx':'export default function App( {'},checks:[checks[0]]});
  assert.equal(report.passed,false);assert.ok(report.results[0].message.length);
});
test('测试钩子异常不会漏报，异步准备和参数化测试可用', {timeout:90000},async()=>{
  const report=await checkProject({files,checks:[
    {id:'before',engine:'sandpack-jest',source:'beforeEach(()=>{throw new Error("before failure")});test("body",()=>expect(1).toBe(1));'},
    {id:'after',engine:'sandpack-jest',source:'afterEach(()=>{throw new Error("after failure")});test("body",()=>expect(1).toBe(1));'},
    {id:'after-all',engine:'sandpack-jest',source:'afterAll(async()=>{await new Promise(r=>setTimeout(r,50));throw new Error("afterAll failure")});test("body",()=>expect(1).toBe(1));'},
    {id:'async-setup',engine:'sandpack-jest',source:'let ready=false;beforeAll(async()=>{await new Promise(r=>setTimeout(r,50));ready=true});test.each([1,2])("case %s",value=>{expect(ready).toBe(true);expect(value).toBeGreaterThan(0)});'},
  ]});
  assert.deepEqual(report.results.map(r=>r.status),['failed','failed','failed','passed'],JSON.stringify(report));
  assert.match(report.results[0].message,/before failure/);assert.match(report.results[2].message,/afterAll failure/);
});
