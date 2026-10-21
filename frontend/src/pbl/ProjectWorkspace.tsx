import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ProjectBrief } from './WorkbenchBrief';
import { usePblWorkspace } from './usePblWorkspace';
import { pblApi } from './api';
import { PblTutor } from './PblTutor';
import { WorkbenchStage } from './WorkbenchStage';
import { useWorkbenchTutor } from './useWorkbenchTutor';
import { ProjectEditor, type ProjectPanel } from './ProjectEditor';
import { ProjectChecks } from './ProjectChecks';
import { NativeProjectTests } from './NativeProjectTests';
import { isJestCheck } from './nativeTests';
import type { ProjectArtifact, ProjectReport } from './projectTypes';
import { WorkbenchHeading, WorkbenchControls, WorkbenchBody } from './WorkbenchChrome';

function serializeProject(files: Record<string,string>) {return JSON.stringify(Object.fromEntries(Object.keys(files).sort().map(k=>[k,files[k]])));}
async function hashProject(source:string) {const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source));return Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');}
export function ProjectWorkspace({owner,artifact}: {owner:string;artifact:ProjectArtifact}) {
  const state=usePblWorkspace(owner,artifact);
  const [panel,setPanel]=useState<ProjectPanel>('preview');
  const [mobilePane,setMobilePane]=useState<'code'|'result'>('code');
  const {tutorOpen,tutorVisited,openTutor,closeTutor,toggleTutor}=useWorkbenchTutor();
  const [suggestion,setSuggestion]=useState<{id:string;text:string}>();
  const [running,setRunning]=useState(false),[checkingTask,setCheckingTask]=useState(''),[error,setError]=useState('');
  const showPanel=(next:ProjectPanel)=>{setPanel(next);setMobilePane('result');};
  const [reports,setReports]=useState<ProjectReport[]>([]);
  const [hashed,setHashed]=useState({source:'',hash:''});
  const pending=useRef<Parameters<typeof pblApi.checkProject>[1]>();
  const alive=useRef(true);
  const source=serializeProject(state.workspace?.files || {});
  useEffect(()=>{let active=true;void hashProject(source).then(hash=>{if(active)setHashed({source,hash});}).catch(()=>{if(active)setError('无法校验代码快照，请使用 HTTPS 或本机地址');});return()=>{active=false;};},[source]);
  useEffect(()=>{alive.current=true;void pblApi.listProjectRuns(artifact.exerciseId).then(value=>{if(alive.current)setReports(value.items);}).catch(()=>{if(alive.current)setError('历史检查暂未读取，可重新检查当前代码');});return()=>{alive.current=false;};},[artifact.exerciseId]);
  const step=artifact.tasks.find(t=>t.id===state.workspace?.activeTaskId) || artifact.tasks[0];
  const currentHash=hashed.source===source?hashed.hash:'';
  const latest=reports.find(r=>r.taskId===step.id);
  const isPassed=(ids:string[])=>{
    const report=reports.find(r=>r.codeHash===currentHash&&ids.every(id=>r.results.some(result=>result.caseId===id)));
    return Boolean(report&&ids.every(id=>report.results.some(result=>result.caseId===id&&result.status==='passed')));
  };
  const passed=isPassed(step.cumulativeCheckIds);
  const label=running&&checkingTask===step.id?'正在检查当前代码':passed?'本步检查通过':latest&&latest.codeHash!==currentHash?'代码已修改，需重新检查':latest?.status==='failed'?'还需要调整':'完成后检查本步';
  const checks=useMemo(()=>artifact.checks.filter(c=>step.cumulativeCheckIds.includes(c.id)),[artifact.checks,step]);
  const change=state.change;
  const onChange=useCallback((files:Record<string,string>)=>change({files}),[change]);
  const check=async()=>{
    if(!state.workspace || running)return;
    const request: Parameters<typeof pblApi.checkProject>[1]={artifactVersion:artifact.artifactVersion,taskId:step.id,files:{...state.workspace.files},runId:crypto.randomUUID()};
    if(pending.current?.taskId===request.taskId&&serializeProject(pending.current.files)===serializeProject(request.files))request.runId=pending.current.runId;
    pending.current=request;setRunning(true);setCheckingTask(step.id);setError('');showPanel('checks');
    try {const report=await pblApi.checkProject(artifact.exerciseId,request);if(alive.current){setReports(prev=>[report,...prev.filter(r=>r.runId!==report.runId)]);pending.current=undefined;}}
    catch(e){if(alive.current)setError(e instanceof Error?e.message:'检查未完成，请稍后重试');}
    finally{if(alive.current)setRunning(false);}
  };
  const download=()=>{if(!state.workspace)return;const url=URL.createObjectURL(new Blob([JSON.stringify(state.workspace.files,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='project-files.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const stepIndex=artifact.tasks.indexOf(step);
  const selectStep=(id:string)=>{change({activeTaskId:id});setSuggestion(undefined);};
  const askAbout=(name:string)=>{setSuggestion({id:crypto.randomUUID(),text:`帮我分析「${name}」的检查结果，解释预期和实际结果为什么不同，并给我下一步提示。`});openTutor();};
  return <main className="pbl-workspace pbl-project pbl-workbench">
    <WorkbenchHeading title={artifact.title} taskTitle={step.title} stepNumber={stepIndex+1} totalSteps={artifact.tasks.length}>
      <ProjectBrief step={step} checks={checks} deliverable={artifact.plan.steps.find(item=>item.id===step.id)?.deliverable}/>
    </WorkbenchHeading>
    <WorkbenchStage tutorOpen={tutorOpen} onTutorToggle={toggleTutor} controls={<WorkbenchControls status={label} saveStatus={state.saveStatus} operations={<><button onClick={()=>void state.retrySave()}>同步</button><button onClick={download}>下载工程</button><button onClick={()=>void state.resetCode()}>重置工程</button>{state.backup&&<button onClick={state.restoreBackup}>恢复备份</button>}</>}
      actions={<><button className="pbl-check-primary" disabled={running||!state.workspace} onClick={()=>void check()}>{running?'正在检查…':'检查本步'}</button>{stepIndex<artifact.tasks.length-1&&<button disabled={!state.workspace} onClick={()=>selectStep(artifact.tasks[stepIndex+1].id)}>下一步 →</button>}</>}/>}>
    {state.conflict&&<section className="pbl-alert" role="alert"><p>另一页面更新了工程，请选择保留哪份。另一份将保存为备份。</p><button onClick={()=>void state.resolveConflict(true)}>保留本地草稿</button><button onClick={()=>void state.resolveConflict(false)}>使用服务器版本</button></section>}
    <WorkbenchBody steps={artifact.tasks.map(task=>({...task,passed:isPassed(task.cumulativeCheckIds)}))} activeStep={step.id} onStep={selectStep} disabled={!state.workspace} tutorOpen={tutorOpen} onTutorClose={closeTutor}
      tutor={tutorVisited&&state.workspace?<PblTutor key={step.id} embedded suggestion={suggestion} exerciseId={artifact.exerciseId} artifactVersion={artifact.artifactVersion} taskId={step.id} files={state.workspace.files} codeHash={currentHash}/>:null}>
    {state.workspace?<ProjectEditor runtime={artifact.runtime} startRoute={artifact.checks.flatMap(check=>'engine' in check&&check.engine==='http'?check.requests:[]).find(request=>request.method==='GET')?.path} workspace={state.workspace} onChange={onChange} panel={panel} onPanel={showPanel} mobilePane={mobilePane} onMobilePane={setMobilePane}
      checks={<><ProjectChecks checks={checks} step={step} report={latest} currentHash={currentHash} running={running&&checkingTask===step.id} error={error} complete={passed&&stepIndex===artifact.tasks.length-1} onAsk={askAbout}/>
        {checks.some(isJestCheck)&&<NativeProjectTests runtime={artifact.runtime} key={step.id} files={state.workspace.files} checks={checks.filter(isJestCheck)}/>}</>}
      />:<p className="pbl-project-loading">{state.saveStatus}</p>}
    </WorkbenchBody>


    </WorkbenchStage>
  </main>;
}
