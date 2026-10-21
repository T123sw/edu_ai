import { Component, useEffect, useRef, useState, type ReactNode } from 'react';
import { SandpackLayout, SandpackProvider, SandpackTests } from '@codesandbox/sandpack-react';
import {projectSetup,type ProjectRuntime} from './projectRuntime';
import type { JestCheck } from './projectTypes';
import { nativeTestFiles, nativeTestResults, testPath, NATIVE_TEST_OPTIONS, NATIVE_TEST_SETUP, type NativeSpec } from './nativeTests';

class NativeTestBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){return this.state.failed?<p role="alert">测试界面未能完成运行，请重新运行即时测试。</p>:this.props.children;}
}

export function NativeTestRunner({files,checks,runtime,onComplete}: {
  files:Record<string,string>;checks:JestCheck[];runtime?:ProjectRuntime|null;onComplete?:(specs:Record<string,NativeSpec>)=>void;
}) {
  // Each runner is a frozen snapshot. Rebuilding the provider's files during
  // onComplete can restart Sandpack while Jest is still finishing its realm.
  const [runner]=useState(()=>({
    files:nativeTestFiles(files,checks,runtime),
    template:runtime?.template==='vanilla'?'react' as const:runtime?.template==='vanilla-ts'?'react-ts' as const:runtime?.template || 'react' as const,
    customSetup:{entry:'/__pbl__/test-entry.js',dependencies:{...projectSetup(files,runtime).customSetup.dependencies,...NATIVE_TEST_SETUP.dependencies}},
    options:{...NATIVE_TEST_OPTIONS,visibleFiles:Object.keys(files),activeFile:Object.keys(files)[0]},
  }));
  const container=useRef<HTMLDivElement>(null);
  const callback=useRef(onComplete);callback.current=onComplete;
  const hookState=useRef({pending:0,errors:Object.create(null) as Record<string,string[]>,specs:undefined as Record<string,NativeSpec>|undefined});
  const flush=()=>{
    const state=hookState.current;
    if(!state.specs||state.pending>0)return;
    const specs={...state.specs};
    for(const [id,errors] of Object.entries(state.errors)) specs[testPath(id)]={...specs[testPath(id)],error:{message:errors.join('\n')}};
    callback.current?.(specs);
  };
  const flushRef=useRef(flush);flushRef.current=flush;
  useEffect(()=>{
    const listener=(event:MessageEvent)=>{
      if(event.origin!==new URL(NATIVE_TEST_OPTIONS.bundlerURL).origin||event.source!==container.current?.querySelector('iframe')?.contentWindow)return;
      const data=event.data;
      if(data?.type==='test'&&data.event==='total_test_start') {hookState.current={pending:0,errors:Object.create(null),specs:undefined};return;}
      if(data?.channel!=='pbl-jest-hooks-v1'||!checks.some(check=>check.id===data.checkId))return;
      const state=hookState.current;
      if(data.event==='start')state.pending++;
      if(data.event==='error') (state.errors[data.checkId] ||= []).push(String(data.message).slice(0,2000));
      if(data.event==='end') {state.pending=Math.max(0,state.pending-1);flushRef.current();}
    };
    window.addEventListener('message',listener);
    return()=>window.removeEventListener('message',listener);
  },[checks]);
  return <div ref={container}><SandpackProvider template={runner.template} files={runner.files} customSetup={runner.customSetup} options={runner.options}>
    <SandpackLayout><SandpackTests verbose watchMode showWatchButton={false} onComplete={specs=>{hookState.current.specs=specs;queueMicrotask(()=>flushRef.current());}}/></SandpackLayout>
  </SandpackProvider></div>;
}

export function NativeProjectTests({files,checks,runtime}: {files:Record<string,string>;checks:JestCheck[];runtime?:ProjectRuntime|null}) {
  const [snapshot,setSnapshot]=useState<{files:Record<string,string>;key:number}>();
  const [results,setResults]=useState<ReturnType<typeof nativeTestResults>>();
  const [timedOut,setTimedOut]=useState(false);
  const activeRun=useRef(0);
  const serialize=(value:Record<string,string>)=>JSON.stringify(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)));
  const stale=Boolean(snapshot&&serialize(snapshot.files)!==serialize(files));
  useEffect(()=>{
    if(!snapshot||results)return;
    const timer=setTimeout(()=>{activeRun.current++;setTimedOut(true);},75000);
    return()=>clearTimeout(timer);
  },[snapshot,results]);
  return <section className="pbl-native-tests" aria-label="即时测试">
    <h3>即时测试</h3>
    <p>在独立环境中试运行本步及前序测试。步骤通过以顶部“检查本步”的结果为准。</p>
    <button onClick={()=>{setResults(undefined);setTimedOut(false);setSnapshot({files:{...files},key:++activeRun.current});}}>运行即时测试</button>
    {timedOut&&<p role="alert">即时测试未完成，请检查网络连接或代码中的无限循环后重新运行。</p>}
    {stale&&<p role="status">代码已修改，请重新运行；下方结果对应修改前的代码。</p>}
    {results&&<p role="status">{results.filter(result=>result.status==='passed').length} / {checks.length} 项通过{stale?'（旧代码）':''}</p>}
    {results?.filter(result=>result.status==='failed').map(result=><pre className="pbl-native-error" key={result.caseId}>{result.message}</pre>)}
    {snapshot&&!timedOut&&<NativeTestBoundary key={snapshot.key}><NativeTestRunner files={snapshot.files} checks={checks} runtime={runtime} onComplete={specs=>{if(activeRun.current===snapshot.key)setResults(nativeTestResults(checks,specs));}}/></NativeTestBoundary>}
  </section>;
}
