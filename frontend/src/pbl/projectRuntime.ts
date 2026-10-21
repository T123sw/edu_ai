import type {SandpackPredefinedTemplate} from '@codesandbox/sandpack-react';
import catalog from '../../../shared/pbl-runtimes.json';
export type RuntimeTemplate = keyof typeof catalog;
export interface ProjectRuntime {template:RuntimeTemplate;entry:string;dependencies:Record<string,string>;moduleType:'commonjs'|'module'}
export const LEGACY_RUNTIME:ProjectRuntime={template:'react',entry:'/index.js',dependencies:{react:'18.3.1','react-dom':'18.3.1'},moduleType:'commonjs'};
export function projectSetup(files:Record<string,string>,runtime?:ProjectRuntime|null) {
  if(!runtime) return {template:'react' as SandpackPredefinedTemplate,files:{...files,
    '/index.js':{code:"import React from 'react';import {createRoot} from 'react-dom/client';import App from './src/App.jsx';import './src/styles.css';createRoot(document.getElementById('root')).render(<App/>);",hidden:true,readOnly:true},
    '/App.js':{code:"export {default} from './src/App.jsx';",hidden:true,readOnly:true},'/styles.css':{code:'',hidden:true,readOnly:true}},customSetup:{dependencies:LEGACY_RUNTIME.dependencies},visibleFiles:Object.keys(files),activeFile:'/src/App.jsx'};
  const spec=catalog[runtime.template];
  const dependencies={...spec.dependencies,...runtime.dependencies};
  const manifest={name:'pbl-project',version:'1.0.0',main:runtime.entry,dependencies,
    ...(runtime.template==='node'?{type:runtime.moduleType,scripts:{start:'node pblruntime.cjs'}}:{})};
  return {template:runtime.template as SandpackPredefinedTemplate,
    files:{...Object.fromEntries(Object.entries(spec.files).map(([path,code])=>[path,{code,hidden:true,readOnly:true}])),...files,
      ...(runtime.template==='node'?{'/pblruntime.cjs':{code:(runtime.moduleType==='module'?'import(':'require(')+JSON.stringify('.'+runtime.entry)+');',hidden:true,readOnly:true}}:{}),
      '/package.json':{code:JSON.stringify(manifest),hidden:true,readOnly:true}},
    customSetup:{entry:runtime.entry,dependencies},visibleFiles:Object.keys(files),
    activeFile:Object.hasOwn(files,spec.activeFile)?spec.activeFile:runtime.entry};
}
