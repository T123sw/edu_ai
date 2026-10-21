import { useCallback, useEffect, useState } from 'react';
import { AlgorithmBrief } from './WorkbenchBrief';
import { SandpackWorkspace } from './SandpackWorkspace';
import { usePblWorkspace } from './usePblWorkspace';
import { hashCode } from './protocol';
import { deriveTaskStatus } from './runState';
import { PblTutor } from './PblTutor';
import { WorkbenchStage } from './WorkbenchStage';
import { useWorkbenchTutor } from './useWorkbenchTutor';
import { WorkbenchHeading, WorkbenchControls, WorkbenchBody } from './WorkbenchChrome';
import type { WorkbenchPanel } from './WorkbenchPanels';
import type { ExerciseArtifact } from './types';
const labels={not_started:'尚未开始',in_progress:'正在练习',tests_passed:'全部用例通过',needs_recheck:'代码已修改，需重新检查'};
export function AlgorithmWorkspace({owner,artifact}: {owner:string;artifact:ExerciseArtifact}) {
  const state=usePblWorkspace(owner,artifact);
  const [hashed,setHashed]=useState({code:'',hash:''});
  const [panel,setPanel]=useState<WorkbenchPanel>('preview');
  const [mobilePane,setMobilePane]=useState<'code'|'result'>('code');
  const {tutorOpen,tutorVisited,openTutor,closeTutor,toggleTutor}=useWorkbenchTutor();
  const [suggestion,setSuggestion]=useState<{id:string;text:string}>();
  const [runtime,setRuntime]=useState({ready:false,running:false,error:''});
  const [checkRequest,setCheckRequest]=useState(0),[stopRequest,setStopRequest]=useState(0);
  const code=state.workspace?.files['/src/algorithm.js'] || '';
  useEffect(()=>{let active=true;void hashCode(code).then(hash=>{if(active)setHashed({code,hash});});return()=>{active=false;};},[code]);
  const change=state.change;
  const onChange=useCallback((value:string)=>change({files:{'/src/algorithm.js':value}}),[change]);
  const onInput=useCallback((value:string)=>change({customInputText:value}),[change]);
  const hash=hashed.code===code?hashed.hash:'';
  const status=deriveTaskStatus({hasEdits:code!==artifact.starterCode,currentCodeHash:hash,artifact,latestCheck:state.latestCheck});
  const step=artifact.tasks[0],report=state.latestCheck,current=Boolean(report&&report.codeHash===hash);
  const showPanel=(next:WorkbenchPanel)=>{setPanel(next);setMobilePane('result');};
  const download=()=>{const url=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));const a=document.createElement('a');a.href=url;a.download='algorithm.js';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const checks=<section className="pbl-checks-panel" aria-label="步骤验收">
    <header><div><h3>本步验收</h3><p>全部公开用例，共 {artifact.testCases.length} 项</p></div><span>{runtime.running?'检查中':current?`${report!.results.filter(r=>r.status==='passed').length} / ${artifact.testCases.length} 通过`:'待检查'}</span></header>
    <p className="pbl-checks-note">点击顶部“检查本步”，验证当前代码的全部公开用例。运行单个输入不会标记本步通过。</p>
    {runtime.error&&<p className="pbl-alert" role="alert">{runtime.error}</p>}
    {report&&!current&&<p className="pbl-alert">代码已修改，以下是修改前的记录，请重新检查。</p>}
    {runtime.running&&<p role="status" className="pbl-checks-running">正在运行代码并检查输出…</p>}
    {artifact.testCases.map(test=>{const result=report?.results.find(r=>r.caseId===test.id);return <article key={test.id} className={`pbl-check-card ${current&&result?(result.status==='passed'?'passed':'failed'):''}`}>
      <div className="pbl-check-card-title"><strong>{test.label}</strong><span>{!current||!result?'待检查':result.status==='passed'?'通过':'未通过'}</span></div>
      <details><summary>输入与预期</summary><pre>输入：{JSON.stringify(test.input)}{'\n'}预期：{JSON.stringify(test.expected)}</pre></details>
      {result&&<div className="pbl-check-evidence"><strong>{current?'实际执行记录':'历史执行记录'}</strong><pre>输入：{JSON.stringify(test.input)}{'\n'}预期：{JSON.stringify(result.expected)}{'\n'}实际：{result.actual?JSON.stringify(result.actual):'未得到有效结果'}{result.error?`\n${result.error.message}`:''}</pre>
        {current&&result.status!=='passed'&&<button onClick={()=>{setSuggestion({id:crypto.randomUUID(),text:`帮我分析「${test.label}」的检查结果，解释预期和实际结果为什么不同，并给我下一步提示。`});openTutor();}}>请 AI 分析失败原因</button>}</div>}
    </article>;})}
    <p className="pbl-evidence-note">检查依据：浏览器实际运行的公开用例。通过用例后，也请确认自己理解实现思路。</p>
  </section>;
  return <main className="pbl-workspace pbl-project pbl-workbench pbl-algorithm">
    <WorkbenchHeading title={artifact.title} taskTitle={step.title} stepNumber={1} totalSteps={1}>
      <AlgorithmBrief artifact={artifact} step={step}/>
    </WorkbenchHeading>
    <WorkbenchStage tutorOpen={tutorOpen} onTutorToggle={toggleTutor} controls={<WorkbenchControls status={labels[status]} saveStatus={state.saveStatus} operations={<><button onClick={()=>void state.retrySave()}>同步</button><button onClick={download}>下载代码</button><button onClick={()=>void state.resetCode()}>重置代码</button>{state.backup&&<button onClick={state.restoreBackup}>恢复备份</button>}</>}
      actions={<>{runtime.running&&<button onClick={()=>setStopRequest(n=>n+1)}>停止</button>}<button className="pbl-check-primary" disabled={!state.workspace||!runtime.ready||runtime.running} onClick={()=>{showPanel('checks');setCheckRequest(n=>n+1);}}>{runtime.running?'正在检查…':'检查本步'}</button></>}/>}>
    {state.conflict&&<section className="pbl-alert" role="alert"><p>本地草稿与服务器版本冲突。另一份代码会保留为备份。</p><button onClick={()=>void state.resolveConflict(true)}>保留本地草稿</button><button onClick={()=>void state.resolveConflict(false)}>使用服务器版本</button></section>}
    <WorkbenchBody steps={[{...step,passed:status==='tests_passed'}]} activeStep={step.id} onStep={()=>{}} disabled={!state.workspace} tutorOpen={tutorOpen} onTutorClose={closeTutor}
      tutor={tutorVisited&&state.workspace?<PblTutor embedded suggestion={suggestion} exerciseId={artifact.exerciseId} artifactVersion={artifact.artifactVersion} taskId={step.id} files={state.workspace.files} codeHash={hash}/>:null}>
    {state.workspace?<SandpackWorkspace artifact={artifact} workspace={state.workspace} onChange={onChange} onInput={onInput} onReport={state.onRunReport}
      panel={panel} onPanel={showPanel} mobilePane={mobilePane} onMobilePane={setMobilePane} checks={checks} checkRequest={checkRequest} stopRequest={stopRequest} onRuntimeState={setRuntime}
      />:<p className="pbl-project-loading">{state.saveStatus}</p>}
    </WorkbenchBody>

    </WorkbenchStage>
  </main>;
}
