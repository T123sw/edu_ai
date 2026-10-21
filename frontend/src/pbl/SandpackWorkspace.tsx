import { useEffect, useRef, useState } from 'react';
import { SandpackProvider, SandpackCodeEditor, SandpackPreview, useSandpack, type SandpackPreviewRef } from '@codesandbox/sandpack-react';
import { assembleSandpackFiles } from './assemble';
import { BUNDLER_URL, connectPreview } from './bridge';
import { hashCode } from './protocol';
import { validateSource } from './runtime/sourceValidation';
import type { ExerciseArtifact, RunRequest, RunReport, Workspace } from './types';
import type { RunRecord } from './api';
import { WorkbenchPanels, type WorkbenchViewProps } from './WorkbenchPanels';
interface Props extends WorkbenchViewProps {checkRequest:number;stopRequest:number;onRuntimeState(value:{ready:boolean;running:boolean;error:string}):void;artifact: ExerciseArtifact; workspace: Workspace; onChange(code: string): void; onInput(text: string): void; onReport(report: RunRecord): void}
function Editor({artifact,workspace,onChange,onInput,onReport,panel,onPanel,mobilePane,onMobilePane,checks,checkRequest,stopRequest,onRuntimeState}: Props) {
  const {sandpack}=useSandpack();
  const preview=useRef<SandpackPreviewRef>(null);
  const bridge=useRef<ReturnType<typeof connectPreview>>();
  const active=useRef<RunRequest | null>(null);
  const [ready,setReady]=useState(false), [error,setError]=useState(''), [running,setRunning]=useState(false);
  const [runtimeEpoch,setRuntimeEpoch]=useState(0);
  const refs=useRef({artifact,workspace,onChange,onInput,onReport,sandpack});refs.current={artifact,workspace,onChange,onInput,onReport,sandpack};
  const code=sandpack.files['/src/algorithm.js']?.code || '';
  const lastCode=useRef(workspace.files['/src/algorithm.js']);
  useEffect(()=>{
    if(code!==lastCode.current) {lastCode.current=code;onChange(code);}
  },[code,onChange]);
  useEffect(()=>{
    const incoming=workspace.files['/src/algorithm.js'];
    if(incoming!==lastCode.current) {lastCode.current=incoming;refs.current.sandpack.updateFile('/src/algorithm.js',incoming,false);}
  },[workspace.files]);
  useEffect(()=>{
    let mounted=true;
    const timeout=setTimeout(()=>{if(mounted)setError('运行环境加载较慢，请检查网络后重试。代码已保留。');},45000);
    bridge.current=connectPreview(()=>{
      const client=preview.current?.getClient();return client ? (client as unknown as {iframe:HTMLIFrameElement}).iframe : null;
    },message=>{
      if(message.type==='runtime-ready' && message.templateVersion===artifact.templateVersion) {
        clearTimeout(timeout);setReady(true);setError('');active.current=null;setRunning(false);
        bridge.current?.send('set-input',{customInputText:refs.current.workspace.customInputText});
      }
      if(message.type==='input-changed' && typeof message.customInputText==='string') refs.current.onInput(message.customInputText);
      if(message.type==='run-intent' && (message.mode==='sample'||message.mode==='check') && typeof message.customInputText==='string') {
        if(active.current)return;
        const {artifact,sandpack}=refs.current;
        const code=sandpack.files['/src/algorithm.js'].code;
        const validation=validateSource(code);
        if(!validation.ok) {setError(validation.issues.map(i=>i.message).join('；'));return;}
        setError(validation.issues.map(i=>i.message).join('；'));
        let cases=artifact.testCases;
        if(message.mode==='sample') {
          try {
            const input:unknown=JSON.parse(message.customInputText);
            if(!Array.isArray(input)||input.length>1000||!input.every(v=>typeof v==='number'&&Number.isFinite(v)))throw new Error();
            cases=[{id:'sample',label:'自定义输入',input,expected:[...input].sort((a,b)=>a-b)}];
          } catch {setError('请输入有效的数字数组，例如 [3, 1, 2]，最多 1000 个数字。');return;}
        }
        const request:RunRequest={exerciseId:artifact.exerciseId,artifactVersion:artifact.artifactVersion,templateVersion:artifact.templateVersion,
          taskId:artifact.tasks[0].id,runId:crypto.randomUUID(),codeHash:'',code,mode:message.mode,cases};
        active.current=request;setRunning(true);
        void hashCode(code).then(hash=>{
          if(!mounted || active.current!==request)return;
          request.codeHash=hash;bridge.current?.send('run-request',{...request});
        }).catch(()=>{active.current=null;setRunning(false);setError('无法创建代码快照，请使用 HTTPS 或本机地址。');});
      }
      if(message.type==='run-finished') {
        const request=active.current;
        if(!request || message.runId!==request.runId || message.codeHash!==request.codeHash || !Array.isArray(message.results) ||
          !['passed','failed','error','timeout','canceled'].includes(String(message.status)) || typeof message.durationMs!=='number')return;
        const results=(message.results as RunReport['results']).map(item=>({caseId:item.caseId,status:item.status,expected:item.expected,
          ...(item.actual?{actual:item.actual}:{}),...(item.inputAfter?{inputAfter:item.inputAfter}:{}),
          ...(item.returnedSameReference!==undefined?{returnedSameReference:item.returnedSameReference}:{}),...(item.error?{error:item.error}:{})}));
        refs.current.onReport({...request,status:message.status as RunReport['status'],results,durationMs:message.durationMs,evidenceSource:'browser_reported'});
        active.current=null;setRunning(false);
      }
    });
    return ()=>{mounted=false;clearTimeout(timeout);bridge.current?.send('stop-request',{runId:active.current?.runId});bridge.current?.close();};
  },[artifact.templateVersion,runtimeEpoch]);
  useEffect(()=>{onRuntimeState({ready,running,error});},[ready,running,error,onRuntimeState]);
  useEffect(()=>{if(checkRequest)bridge.current?.send('request-check');},[checkRequest]);
  useEffect(()=>{if(stopRequest)bridge.current?.send('stop-request',{runId:active.current?.runId});},[stopRequest]);
  return <WorkbenchPanels panel={panel} onPanel={onPanel} mobilePane={mobilePane} onMobilePane={onMobilePane} checks={checks} previewLabel="运行结果" codeHint="运行时使用当前代码"
    code={<SandpackCodeEditor showRunButton={false} showTabs showLineNumbers wrapContent closableTabs={false}/>}
    preview={<><div className="pbl-preview-tools"><span role="status">{running?'正在运行':ready?'运行环境已就绪':'正在连接运行环境'}</span>
      <button onClick={()=>{active.current=null;setRunning(false);setReady(false);setError('');setRuntimeEpoch(n=>n+1);}}>重试运行环境</button></div>
      {error&&<p className="pbl-alert" role="alert">{error}</p>}
      <SandpackPreview key={runtimeEpoch} ref={preview} showOpenInCodeSandbox={false} showRefreshButton={false} showNavigator={false}/></>}/>;
}
export function SandpackWorkspace(props: Props) {
  const [files]=useState(()=>assembleSandpackFiles(props.artifact,props.workspace));
  return <SandpackProvider template="vanilla" files={files} options={{autoReload:false,bundlerURL:BUNDLER_URL,visibleFiles:['/src/algorithm.js'],activeFile:'/src/algorithm.js',recompileMode:'delayed',recompileDelay:500}}>
    <Editor {...props}/>
  </SandpackProvider>;
}
