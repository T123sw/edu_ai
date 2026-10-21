import { useEffect, useRef, useState } from 'react';
import { SandpackProvider, SandpackCodeEditor, SandpackPreview, SandpackFileExplorer, SandpackConsole, useSandpack } from '@codesandbox/sandpack-react';
import { BUNDLER_URL } from './bridge';
import {projectSetup,type ProjectRuntime} from './projectRuntime';
import type { Workspace } from './types';
import { WorkbenchPanels, type WorkbenchPanel, type WorkbenchViewProps } from './WorkbenchPanels';
export type ProjectPanel = WorkbenchPanel;
type ProjectEditorProps = WorkbenchViewProps & {runtime?:ProjectRuntime|null;startRoute?:string;workspace:Workspace;onChange(files:Record<string,string>):void};
function serializeProject(files: Record<string,string>) {return JSON.stringify(Object.fromEntries(Object.keys(files).sort().map(k=>[k,files[k]])));}
function Editor({runtime,startRoute,workspace,onChange,panel,onPanel,mobilePane,onMobilePane,checks}: ProjectEditorProps) {
  const {sandpack,dispatch,listen}=useSandpack();
  const last=useRef(serializeProject(workspace.files));
  const api=useRef(sandpack);api.current=sandpack;
  const restartPending=useRef(new Set<string>());
  const sent=useRef(serializeProject(workspace.files));
  const pendingSource=useRef(sent.current);
  const edited=serializeProject(Object.fromEntries(Object.keys(workspace.files).map(path=>[path,sandpack.files[path]?.code || ''])));
  pendingSource.current=edited;
  // Queue the latest edit until the current compilation finishes: the bundler
  // can discard updates submitted while its initial dependencies are loading.
  useEffect(()=>{
    let timer:ReturnType<typeof setTimeout>;
    const flush=()=>{
      if(sent.current===pendingSource.current)return;
      const clients=Object.values(api.current.clients);
      if(!clients.length||clients.some(client=>client.status!=='done')){timer=setTimeout(flush,250);return;}
      if(runtime?.template==='node'){const previous=JSON.parse(sent.current);const next=JSON.parse(pendingSource.current);restartPending.current=new Set(Object.keys(next).filter(path=>next[path]!==previous[path]));}
      for(const client of clients)client.updateSandbox({files:api.current.files,template:api.current.environment});
      sent.current=pendingSource.current;
    };
    timer=setTimeout(flush,700);
    return()=>clearTimeout(timer);
  },[edited]);
  useEffect(()=>listen(message=>{
    if(runtime?.template!=='node'||message.type!=='fs/change'||!restartPending.current.size)return;
    const path=message.path.startsWith('/')?message.path:'/'+message.path;
    if(message.content!==api.current.files[path]?.code)return;
    restartPending.current.delete(path);
    if(!restartPending.current.size)dispatch({type:'shell/restart'});
  }),[listen,dispatch,runtime?.template]);
  useEffect(()=>{if(edited!==last.current){last.current=edited;onChange(JSON.parse(edited));}},[edited,onChange]);
  useEffect(()=>{
    const incoming=serializeProject(workspace.files);
    if(incoming!==last.current){last.current=incoming;api.current.updateFile(workspace.files,undefined,false);}
  },[workspace.files]);
  return <WorkbenchPanels panel={panel} onPanel={onPanel} mobilePane={mobilePane} onMobilePane={onMobilePane} checks={checks}
    code={<div className="pbl-project-files">{runtime&&<details className="pbl-file-explorer"><summary>工程文件 · {Object.keys(workspace.files).length} 个</summary><SandpackFileExplorer /></details>}<SandpackCodeEditor showRunButton={false} showTabs showLineNumbers wrapContent closableTabs={false}/></div>}
    preview={<><div className="pbl-preview-tools"><span>{runtime?.template==='node'?'在地址栏访问接口路径，或查看服务日志':'直接点击页面中的按钮试用'}</span><button onClick={()=>dispatch({type:'refresh'})}>重新运行预览</button></div><SandpackPreview startRoute={startRoute} showOpenInCodeSandbox={false} showNavigator={runtime?.template==='node'}/>{runtime?.template==='node'&&<details><summary>服务日志</summary><SandpackConsole/></details>}</>}/>;
}
export function ProjectEditor(props: ProjectEditorProps) {
  const [setup]=useState(()=>projectSetup(props.workspace.files,props.runtime));
  return <SandpackProvider template={setup.template} files={setup.files} customSetup={setup.customSetup}
    options={{bundlerTimeOut:60000,initMode:'lazy',autoReload:false,...(props.runtime?.template==='node'||props.runtime?.template==='static'?{}:{bundlerURL:BUNDLER_URL}),visibleFiles:setup.visibleFiles,activeFile:setup.activeFile,recompileMode:'delayed',recompileDelay:700}}><Editor {...props}/></SandpackProvider>;
}
