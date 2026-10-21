import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkProject } from './check-pbl-project.mjs';
const files={'/src/App.jsx':`import React,{useState} from 'react';export default function App(){const [n,s]=useState(0);return <main><button onClick={()=>s(n+1)}>增加</button><output data-testid="count">{n}</output></main>}`, '/src/styles.css':'body { color: black; }'};
const checks=[{id:'increment',label:'递增',actions:[{type:'assert',target:{testId:'count'},assertion:'text',expected:'0'},{type:'click',target:{role:'button',name:'增加'}},{type:'assert',target:{testId:'count'},assertion:'text',expected:'1'}]}];
test('真实 React 渲染与点击，每个检查独立重置；错误实现不能通过',async()=>{
  const report=await checkProject({files,checks:[...checks,{...checks[0],id:'fresh'}]});
  assert.equal(report.passed,true,JSON.stringify(report));
  const broken=await checkProject({files:{...files,'/src/App.jsx':files['/src/App.jsx'].replace('s(n+1)','s(n+2)')},checks});
  assert.equal(broken.passed,false);
  assert.match(broken.results[0].message,/点击.*增加/);
  assert.match(broken.results[0].message,/预期："1"/);
  assert.match(broken.results[0].message,/实际："2"/);
  assert.match(report.results[1].message,/实际："0"/);
});
test('编译错误与任意系统模块导入被拒绝，不执行主机代码',async()=>{
  const report=await checkProject({files:{...files,'/src/App.jsx':"import fs from 'node:fs'; export default function App(){ return null }"},checks});
  assert.equal(report.passed,false);assert.match(report.results[0].message,/编译/);
});
test('浏览器网络请求被禁止，不能接触本机服务',async()=>{
  const report=await checkProject({files:{...files,'/src/App.jsx':`import React,{useEffect,useState} from 'react';export default function App(){const [value,set]=useState('等待');useEffect(()=>{fetch('http://127.0.0.1:8001/api/pbl').then(()=>set('泄露')).catch(()=>set('阻止'))},[]);return <button onClick={()=>{}}>{value}</button>}`},checks:[{id:'network',label:'隔离',actions:[{type:'assert',target:{role:'button',name:'阻止'},assertion:'visible'}]}]});
  assert.equal(report.passed,true,JSON.stringify(report));
});

test('缺失控件不伪造点击结果，长执行记录保留失败证据且可存入现有报告',async()=>{
  const missing=await checkProject({files,checks:[{id:'missing',actions:[{type:'click',target:{role:'button',name:'不存在'}},{type:'assert',target:{testId:'count'},assertion:'text',expected:'1'}]}]});
  assert.equal(missing.passed,false);assert.match(missing.results[0].message,/操作未完成/);assert.doesNotMatch(missing.results[0].message,/✓/);
  const actions=Array.from({length:80},()=>({type:'click',target:{role:'button',name:'增加'}}));
  actions.push({type:'assert',target:{testId:'count'},assertion:'text',expected:'81'});
  const long=await checkProject({files,checks:[{id:'long',actions}]});
  assert.equal(long.passed,false);assert.ok(long.results[0].message.length<=2000);assert.match(long.results[0].message,/预期："81"/);assert.match(long.results[0].message,/实际："80"/);
});
test('异步更新等待实际结果，不因短暂旧值误判失败',async()=>{
  const delayed={...files,'/src/App.jsx':files['/src/App.jsx'].replace('s(n+1)','setTimeout(()=>s(n+1),100)')};
  const report=await checkProject({files:delayed,checks});assert.equal(report.passed,true,JSON.stringify(report));
});

const shellFiles={
  '/src/App.jsx':`export default function App(){return <main><div data-testid="display">0</div><section><button>1</button><button>2</button><button>+</button><button>=</button></section></main>}`,
  '/src/styles.css':'body{margin:0}main{width:300px;margin:16px} [data-testid=display]{height:50px}section{display:grid;grid-template-columns:1fr 1fr;gap:8px}button{height:44px}',
};
const layoutChecks=[
  {id:'above',actions:[{type:'assert',target:{testId:'display'},assertion:'above',relativeTo:{role:'button'}}]},
  {id:'overlap',actions:[{type:'assert',target:{role:'button'},assertion:'not_overlapping'}]},
  {id:'viewport',actions:[{type:'assert',target:{testId:'display'},assertion:'within_viewport'},{type:'assert',target:{role:'button'},assertion:'within_viewport'}]},
];
test('外壳不需要计算即可通过桌面和手机的真实几何验收',async()=>{
  const report=await checkProject({files:shellFiles,checks:['desktop','mobile'].flatMap(viewport=>layoutChecks.map(c=>({...c,id:c.id+'-'+viewport,viewport})))});
  assert.equal(report.passed,true,JSON.stringify(report));assert.equal(report.results.length,6);
});
for(const [name,css,id,message] of [
  ['屏幕放到按键下方','main{display:flex;flex-direction:column}[data-testid=display]{order:2}','above','上方部件没有完整位于'],
  ['按钮重叠','button{grid-area:1 / 1}','overlap','相互重叠'],
  ['手机横向溢出','main{width:700px}','viewport','超出当前检查窗口'],
  ['手机纵向溢出','main{padding-top:820px}','viewport','超出当前检查窗口'],
])test(`控件齐全但${name}不能通过`,async()=>{
  const report=await checkProject({files:{...shellFiles,'/src/styles.css':shellFiles['/src/styles.css']+css},checks:layoutChecks.filter(c=>c.id===id).map(c=>({...c,viewport:'mobile'}))});
  assert.equal(report.passed,false);assert.match(report.results[0].message,new RegExp(message));
});
test('空控件集合、隐藏屏幕和重名屏幕不能让布局检查空通过',async()=>{
  for(const code of [
    'export default function App(){return <div data-testid="display">0</div>}',
    'export default function App(){return <><div data-testid="display" style={{display:"none"}}>0</div><button>1</button><button>2</button></>}',
    'export default function App(){return <><div data-testid="display">0</div><div data-testid="display">0</div><button>1</button><button>2</button></>}',
  ]){
    const report=await checkProject({files:{...shellFiles,'/src/App.jsx':code},checks:[{...layoutChecks[0],viewport:'desktop'}]});
    assert.equal(report.passed,false,JSON.stringify(report));
  }
});

test('通用语义角色可验收列表和表格，不依赖业务 testId',async()=>{
  const generic={'/src/App.jsx':`export default function App(){return <main><ul><li>第一项</li><li>第二项</li></ul><table><tbody><tr><td>内容</td></tr></tbody></table></main>}`,'/src/styles.css':''};
  const checks=[{id:'semantic-content',actions:[
    {type:'assert',target:{role:'listitem'},assertion:'count',expected:2},
    {type:'assert',target:{role:'cell',name:'内容'},assertion:'text',expected:'内容'},
    {type:'assert',target:{role:'table'},assertion:'visible'},
  ]}];
  assert.equal((await checkProject({files:generic,checks})).passed,true);
  const absent={...generic,'/src/App.jsx':'export default function App(){return <main>没有列表或表格</main>}'};
  assert.equal((await checkProject({files:absent,checks})).passed,false);
});

test('范围定位区分同名按钮，旧全局单项定位继续有效，缺失或重复容器不能空通过',async()=>{
  const files={'/src/App.jsx':`import React,{useState} from 'react';export default function App(){const [items,set]=useState(['甲']);return <main><button onClick={()=>set([...items,'乙'])}>添加</button>{items.map((x,i)=><section key={i} data-testid={'row-'+i}><span>{x}</span><button onClick={()=>set(items.map((v,j)=>j===i?v+'!':v))}>变更</button></section>)}</main>}`,'/src/styles.css':''};
  const report=await checkProject({files,checks:[
    {id:'old',actions:[{type:'click',target:{role:'button',name:'变更'}},{type:'assert',target:{testId:'row-0'},assertion:'text',expected:'甲!变更'}]},
    {id:'new',actions:[{type:'click',target:{role:'button',name:'添加'}},{type:'click',target:{role:'button',name:'变更',within:{testId:'row-1'}}},{type:'assert',target:{testId:'row-1'},assertion:'text',expected:'乙!变更'},{type:'assert',target:{testId:'row-0'},assertion:'text',expected:'甲变更'}]},
  ]});
  assert.equal(report.passed,true,JSON.stringify(report));
  for(const within of [{testId:'missing'},{role:'button'}]){
    const bad=await checkProject({files,checks:[{id:'bad-scope',actions:[{type:'assert',target:{testId:'missing',within},assertion:'count',expected:0}]}]});
    assert.equal(bad.passed,false);assert.match(bad.results[0].message,/容器缺失或重复/);
  }
});

test('确定顺序的集合可选择指定条目，索引越界不能伪装为空集合',async()=>{
 const files={'/src/App.jsx':`import React,{useState} from 'react';export default function App(){const [items,set]=useState(['甲','乙']);return <main>{items.map((x,i)=><section data-testid="row" key={i}><output>{x}</output><button onClick={()=>set(items.map((v,j)=>j===i?v+'!':v))}>变更</button></section>)}</main>}`,'/src/styles.css':''};
 const report=await checkProject({files,checks:[{id:'index',actions:[
  {type:'click',target:{role:'button',name:'变更',within:{testId:'row',index:1}}},
  {type:'assert',target:{role:'status',within:{testId:'row',index:1}},assertion:'text',expected:'乙!'},
  {type:'assert',target:{role:'status',index:0},assertion:'text',expected:'甲'},
 ]}]});assert.equal(report.passed,true,JSON.stringify(report));
 for(const target of [{testId:'row',index:2},{role:'button',within:{testId:'row',index:2}}]){
  const bad=await checkProject({files,checks:[{id:'out-of-bounds',actions:[{type:'assert',target,assertion:'count',expected:0}]}]});
  assert.equal(bad.passed,false);assert.match(bad.results[0].message,/越界/);
 }
});
