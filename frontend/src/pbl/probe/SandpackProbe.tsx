import { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { SandpackProvider, SandpackPreview, SandpackCodeEditor, SandpackLayout, useSandpack, type SandpackPreviewRef } from '@codesandbox/sandpack-react';
import { assembleSandpackFiles } from '../assemble';
import { starterCode, referenceSolution, testCases } from '../fixtures/quicksort';
import { BUNDLER_URL, connectPreview } from '../bridge';
import type { RunResult } from '../types';
function Probe() {
  const preview = useRef<SandpackPreviewRef>(null);
  const bridge = useRef<ReturnType<typeof connectPreview>>();
  const {sandpack} = useSandpack();
  const code = sandpack.files['/src/algorithm.js'].code;
  const [ready,setReady] = useState('loading');
  const [report,setReport] = useState<RunResult | null>(null);
  const [status,setStatus] = useState('idle');
  const runId = useRef('');
  const codeRef = useRef(code); codeRef.current = code;
  async function run(mode: 'sample' | 'check') {
    const snapshot = codeRef.current;
    const hash = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([['/src/algorithm.js',snapshot]])));
    runId.current = crypto.randomUUID(); setReport(null); setStatus('running');
    bridge.current?.send('run-request',{runId:runId.current,codeHash:Array.from(new Uint8Array(hash),v=>v.toString(16).padStart(2,'0')).join(''),code:snapshot,mode,cases:mode==='check'?testCases:[testCases[0]],exerciseId:'probe',artifactVersion:1,templateVersion:'js-function-v1',taskId:'implement-sort'});
  }
  const runRef = useRef(run); runRef.current = run;
  useEffect(() => {
    bridge.current = connectPreview(() => {
      const client = preview.current?.getClient();
      return client ? (client as unknown as {iframe: HTMLIFrameElement}).iframe : null;
    }, message => {
      if (message.type === 'runtime-ready') setReady('ready');
      if (message.type === 'run-intent' && (message.mode==='sample'||message.mode==='check')) void runRef.current(message.mode);
      if (message.type === 'run-finished' && message.runId === runId.current) { setReport(message as unknown as RunResult); setStatus(String(message.status)); }
    });
    return () => bridge.current?.close();
  },[]);
  return <main><h1>Sandpack runtime P0</h1><p data-testid="runtime-ready">{ready}</p>
    <button onClick={()=>sandpack.updateFile('/src/algorithm.js','export function quickSort(array) { while (true) {} }',false)}>加载死循环样例</button>
    <button onClick={()=>sandpack.updateFile('/src/algorithm.js',referenceSolution,false)}>加载正确样例</button>
    <button disabled={ready!=='ready'} onClick={()=>void run('sample')}>运行样例</button>
    <button disabled={ready!=='ready'} onClick={()=>void run('check')}>检查练习</button>
    <button onClick={()=>bridge.current?.send('stop-request',{runId:runId.current})}>停止</button>
    <textarea aria-label="原型源码" value={code} onChange={e=>sandpack.updateFile('/src/algorithm.js',e.target.value,false)} style={{width:'95%',height:130}} />
    <p data-testid="run-status">{status}</p><p data-testid="run-error">{report?.results[0]?.error?.code ?? ''}</p><p data-testid="case-count">{report?.results.length ?? 0}</p>
    <SandpackLayout><SandpackCodeEditor showRunButton={false} /><SandpackPreview ref={preview} showOpenInCodeSandbox={false} showRefreshButton={false}/></SandpackLayout>
  </main>;
}
function App() {
  const files=useMemo(()=>assembleSandpackFiles({starterCode,testCases,artifactVersion:1}),[]);
  return <SandpackProvider template="vanilla" files={files} options={{autoReload:false,bundlerURL:BUNDLER_URL,visibleFiles:['/src/algorithm.js'],activeFile:'/src/algorithm.js'}}><Probe /></SandpackProvider>;
}
createRoot(document.getElementById('root')!).render(<App />);
