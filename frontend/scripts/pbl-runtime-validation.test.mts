import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {checkProject} from './check-pbl-project.mjs';
import {browserHost} from './pbl-browser-host.mjs';

const check={id:'increment',label:'递增',actions:[{type:'assert',target:{testId:'count'},assertion:'text',expected:'0'},{type:'click',target:{role:'button',name:'增加'}},{type:'assert',target:{testId:'count'},assertion:'text',expected:'1'}]};
const html='<main><button>增加</button><output data-testid="count">0</output></main>';
const browserJs=`import {next} from './counter';document.getElementById('app').innerHTML=${JSON.stringify(html)};let n=0;document.querySelector('button').onclick=()=>document.querySelector('output').textContent=String(n=next(n));`;
const react=`import React,{useState} from 'react';import {next} from './counter';export default function App(){const [n,set]=useState(0);return <main><button onClick={()=>set(next(n))}>增加</button><output data-testid="count">{n}</output></main>}`;
export const fixtures=[
  ...['vanilla','vanilla-ts'].map(template=>{const ext=template.endsWith('-ts')?'ts':'js';return{runtime:{template,entry:`/index.${ext}`,dependencies:{},moduleType:'commonjs'},files:{[`/index.${ext}`]:browserJs,[`/counter.${ext}`]:ext==='ts'?'export const next=(n:number)=>n+1;':'export const next=n=>n+1;','/index.html':`<html><body><div id="app"></div><script src="index.${ext}"></script></body></html>`}}}),
  ...['react','react-ts'].map(template=>{const ext=template.endsWith('-ts')?'tsx':'js';return{runtime:{template,entry:`/index.${ext}`,dependencies:{},moduleType:'commonjs'},files:{[`/index.${ext}`]:`import React from 'react';import {createRoot} from 'react-dom/client';import App from './App';createRoot(document.getElementById('root')).render(<App/>);`,[`/App.${ext}`]:react,'/counter.js':'export const next=n=>n+1;'}}}),
  ...['vue'].map(template=>({runtime:{template,entry:template==='vue'?'/src/main.js':'/src/main.ts',dependencies:{},moduleType:'commonjs'},files:{[template==='vue'?'/src/main.js':'/src/main.ts']:`import {createApp} from 'vue';import App from './App.vue';createApp(App).mount('#app');`,'/src/App.vue':`<script setup>import {ref} from 'vue';import {next} from './counter';const n=ref(0);</script><template><main><button @click="n=next(n)">增加</button><output data-testid="count">{{n}}</output></main></template>`,'/src/counter.js':'export const next=n=>n+1;'}})),
  {runtime:{template:'svelte',entry:'/index.js',dependencies:process.env.PBL_SVELTE_VERSION?{svelte:process.env.PBL_SVELTE_VERSION}:{},moduleType:'commonjs'},files:{'/index.js':`import App from './App.svelte';new App({target:document.getElementById('app')});`,'/App.svelte':`<script>import {next} from './counter';let n=0;</script><main><button on:click={()=>n=next(n)}>增加</button><output data-testid="count">{n}</output></main>`,'/counter.js':'export const next=n=>n+1;','/public/index.html':'<html><body><div id="app"></div></body></html>'}},

];
for(const fixture of fixtures)test(fixture.runtime.template+'：真实多文件预览、点击、错误实现反例',{timeout:180000},async()=>{
  const report=await checkProject({...fixture,checks:[check]});assert.equal(report.passed,true,JSON.stringify(report));
  const broken=Object.fromEntries(Object.entries(fixture.files).map(([path,source])=>[path,source.replace('n+1','n+2')]));
  const failed=await checkProject({...fixture,files:broken,checks:[check]});assert.equal(failed.passed,false,JSON.stringify(failed));assert.match(failed.results[0].message,/实际："2"/);
});
test('React TypeScript 多文件标准测试',{timeout:180000},async()=>{
  const fixture=fixtures.find(f=>f.runtime.template==='react-ts');
  const report=await checkProject({...fixture,checks:[{id:'native',label:'组件',engine:'sandpack-jest',source:`import React from 'react';import {render,screen,fireEvent} from '@testing-library/react';import App from '../App.tsx';test('递增',()=>{render(<App/>);fireEvent.click(screen.getByRole('button'));expect(screen.getByTestId('count').textContent).toBe('1')});`}]});assert.equal(report.passed,true,JSON.stringify(report));
});
for(const moduleType of ['commonjs','module'])test('Node/Express '+moduleType+'：多文件 HTTP 请求、检查间隔离与错误反例',{timeout:240000},async()=>{
  const runtime={template:'node',entry:'/src/server.js',moduleType,dependencies:{express:'4.21.2'}};
  const files={'/src/server.js':(moduleType==='commonjs'?`const express=require('express');const {next}=require('./counter');`:`import express from 'express';import {next} from './counter.js';`)+`const app=express();app.use(express.json());let n=0;app.get('/',(req,res)=>res.send('Ready'));app.get('/count',(req,res)=>res.json({count:n}));app.post('/count',(req,res)=>{n=next(n);res.status(201).json({count:n})});app.listen(3000);`,'/src/counter.js':moduleType==='commonjs'?'exports.next=n=>n+1;':'export const next=n=>n+1;'};
  const check={id:'api',label:'计数接口',engine:'http',requests:[{method:'GET',path:'/count',status:200,jsonBody:{count:0}},{method:'POST',path:'/count',status:201,jsonBody:{count:1}},{method:'GET',path:'/count',status:200,jsonBody:{count:1}}]};
  const report=await checkProject({runtime,files,checks:[check,{...check,id:'fresh'}]});assert.equal(report.passed,true,JSON.stringify(report));
  const broken=await checkProject({runtime,files:{...files,'/src/counter.js':files['/src/counter.js'].replace('n+1','n+2')},checks:[check]});assert.equal(broken.passed,false,JSON.stringify(broken));assert.match(broken.results[0].message,/实际.*2/);
});
test('Nodebox 页面和 ServiceWorker 均不能访问本机服务',{timeout:120000},async()=>{
  let hits=0;const canary=createServer((req,res)=>{hits++;res.setHeader('Access-Control-Allow-Origin','*');res.end('private')});await new Promise(r=>canary.listen(0,'127.0.0.1',r));
  const host=await browserHost('src/pbl/runtime/SandpackPreviewHarness.tsx');
  try{
    const context=await host.newContext();const page=await context.newPage();await page.goto(host.origin);await page.evaluate(()=>window.startPblPreview({runtime:{template:'node',entry:'/index.js',dependencies:{},moduleType:'commonjs'},files:{'/index.js':`require('http').createServer((req,res)=>res.end('Ready')).listen(3000)`}}));
    await page.frameLocator('.sp-preview iframe:not(.sp-bridge-frame)').getByText('Ready',{exact:true}).waitFor({timeout:60000});
    const url=`http://127.0.0.1:${canary.address().port}/private`;
    const frames=page.frames().filter(f=>f.url().startsWith('https:'));
    for(const frame of frames)assert.equal(await frame.evaluate(url=>fetch(url).then(()=>false,()=>true),url),true);
    assert.ok(context.serviceWorkers().length,'Nodebox must have an active worker');
    for(const worker of context.serviceWorkers())assert.equal(await worker.evaluate(url=>fetch(url).then(()=>false,()=>true),url),true);
    assert.equal(hits,0);await context.close();
  }finally{await host.close();await new Promise(r=>canary.close(r))}
});

test('Nodebox 请求体缺陷明确失败，不挂起或记通过',async()=>{const report=await checkProject({runtime:{template:'node',entry:'/index.js',dependencies:{},moduleType:'commonjs'},files:{'/index.js':"require('http').createServer((req,res)=>res.end('ok')).listen(3000)"},checks:[{id:'body',engine:'http',requests:[{method:'POST',path:'/',body:{value:1},status:200}]}]});assert.equal(report.passed,false);assert.match(report.results[0].message,/请求体传输不可用/)});

test('原生 JS 工程复用标准 Jest 的多文件函数验收',{timeout:180000},async()=>{const fixture=fixtures[0];const report=await checkProject({...fixture,checks:[{id:'pure',engine:'sandpack-jest',source:"import {next} from '../counter.js';test('递增',()=>{expect(next(0)).toBe(1);expect(next(-1)).toBe(0)});"}]});assert.equal(report.passed,true,JSON.stringify(report));});

test('静态 HTML/CSS 页面及缺失成果反例',{timeout:180000},async()=>{const runtime={template:'static',entry:'/index.html',dependencies:{},moduleType:'commonjs'};const files={'/index.html':'<!doctype html><html><head><link rel="stylesheet" href="/styles.css"></head><body><main><h1>作品集</h1></main></body></html>','/styles.css':'body{margin:0}main{width:80%;margin:20px auto}'};const checks=[{id:'page',actions:[{type:'assert',target:{role:'heading',name:'作品集'},assertion:'visible'},{type:'assert',target:{role:'main'},assertion:'within_viewport'}]}];const good=await checkProject({runtime,files,checks});assert.equal(good.passed,true,JSON.stringify(good));const bad=await checkProject({runtime,files:{...files,'/index.html':'<main>未完成</main>'},checks});assert.equal(bad.passed,false);});
