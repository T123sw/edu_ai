import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../stitch/api/client';
import { pblApi, type RunRecord, type WorkspacePatch } from './api';
import { draftKey, getDraft, putDraft, type Draft } from './draftStore';
import type { ProjectArtifact } from './projectTypes';
import type { ExerciseArtifact, Workspace } from './types';
export function usePblWorkspace(owner: string, artifact: ExerciseArtifact | ProjectArtifact) {
  const [workspace,setWorkspace]=useState<Workspace | null>(null);
  const [latestCheck,setLatestCheck]=useState<RunRecord | null>(null);
  const [saveStatus,setSaveStatus]=useState('正在读取代码');
  const [conflict,setConflict]=useState<Workspace | null>(null);
  const [backup,setBackup]=useState<string>();
  const state=useRef<Draft>();
  const saving=useRef(false), stopped=useRef(false), conflictRef=useRef<'none' | 'needs_read' | 'awaiting_choice'>('none');
  const timer=useRef<ReturnType<typeof setTimeout>>();
  const key=draftKey(owner,artifact.exerciseId,artifact.artifactVersion);
  const persist=useCallback(async()=>{
    if(state.current) await putDraft(key,structuredClone(state.current));
  },[key]);
  const readConflict=useCallback(async()=>{
    setSaveStatus('正在读取服务器版本');
    try {
      const remote=await pblApi.getWorkspace(artifact.exerciseId);
      if(stopped.current) return;
      conflictRef.current='awaiting_choice';setConflict(remote);
      setSaveStatus('另一页面更新了代码，请选择保留哪份');
    } catch {
      if(!stopped.current) setSaveStatus('保存冲突，请点击同步或连接恢复后重试');
    }
  },[artifact.exerciseId]);
  const flush=useCallback(async()=>{
    if(saving.current || stopped.current || conflictRef.current==='awaiting_choice' || !state.current) return;
    saving.current=true;
    try {
      if(conflictRef.current==='needs_read') {await readConflict();return;}
      // Recheck both queues after every request: edits can arrive during report upload.
      while(state.current && (state.current.dirty || state.current.pendingPatch || state.current.pendingRuns.length) && !stopped.current) {
        setSaveStatus('正在保存');
        if(!state.current.dirty && !state.current.pendingPatch) {
          await pblApi.appendRun(artifact.exerciseId,state.current.pendingRuns[0]);
          if(stopped.current || !state.current) return;
          state.current.pendingRuns.shift();await persist();
          continue;
        }
        const local=state.current;
        const patch: WorkspacePatch = local.pendingPatch || {
          artifactVersion:artifact.artifactVersion,expectedRevision:local.workspace.revision,mutationId:crypto.randomUUID(),
          files:{...local.workspace.files},activeTaskId:local.workspace.activeTaskId,customInputText:local.workspace.customInputText,
        };
        local.pendingPatch=patch;
        await persist();
        setSaveStatus('正在保存');
        const saved=await pblApi.saveWorkspace(artifact.exerciseId,patch);
        if(stopped.current || !state.current) return;
        const current=state.current;
        current.workspace={...current.workspace,revision:saved.revision,updatedAt:saved.updatedAt};
        current.pendingPatch=undefined;
        current.dirty=JSON.stringify(current.workspace.files)!==JSON.stringify(patch.files) || current.workspace.customInputText!==patch.customInputText || current.workspace.activeTaskId!==patch.activeTaskId;
        setWorkspace({...current.workspace});
        await persist();
      }
      if(!stopped.current) setSaveStatus('已保存');
    } catch(error) {
      if(stopped.current) return;
      if(error instanceof ApiError && error.status===409) {
        conflictRef.current='needs_read';
        await readConflict();
      } else setSaveStatus('本地已记录，待同步');
    } finally {saving.current=false;}
  },[artifact.artifactVersion,artifact.exerciseId,persist,readConflict]);
  useEffect(()=>{
    stopped.current=false;
    let active=true;
    void (async()=>{
      try {
        const local=await getDraft(key);
        let remote: Workspace;
        try {remote=await pblApi.getWorkspace(artifact.exerciseId);}
        catch(error) {if(!local) throw error;remote=local.workspace;}
        if(!active) return;
        const draft=local && (local.dirty || local.pendingPatch) ? local : {workspace:remote,dirty:false,pendingRuns:local?.pendingRuns || [],backup:local?.backup};
        state.current=draft;setWorkspace(draft.workspace);setBackup(draft.backup);
        // Replay an uncertain mutation first: server may already have accepted it.
        if(draft.dirty && !draft.pendingPatch && draft.workspace.revision!==remote.revision) {
          conflictRef.current='awaiting_choice';setConflict(remote);setSaveStatus('发现未同步草稿和服务器新版本');
        } else {setSaveStatus(draft.dirty?'本地已记录，待同步':'已保存');void flush();}
        try {
          const runs=await pblApi.listRuns(artifact.exerciseId);
          if(active) setLatestCheck([...draft.pendingRuns].reverse().find(r=>r.mode==='check') || runs.items.find(r=>r.mode==='check') || null);
        } catch {if(active) setLatestCheck([...draft.pendingRuns].reverse().find(r=>r.mode==='check') || null);}
      } catch {if(active)setSaveStatus('读取失败，请刷新重试');}
    })();
    const online=()=>void flush();window.addEventListener('online',online);
    return ()=>{active=false;stopped.current=true;clearTimeout(timer.current);window.removeEventListener('online',online);};
  },[artifact.exerciseId,key,flush]);
  const change=useCallback((patch: Partial<Workspace>)=>{
    if(!state.current) return;
    state.current.workspace={...state.current.workspace,...patch};state.current.dirty=true;
    setWorkspace({...state.current.workspace});setSaveStatus('本地草稿');
    void persist().catch(()=>setSaveStatus('本地存储不可用，请下载代码备份'));
    clearTimeout(timer.current);timer.current=setTimeout(()=>void flush(),800);
  },[persist,flush]);
  const onRunReport=useCallback((run: RunRecord)=>{
    if(!state.current) return;
    state.current.pendingRuns.push(run);
    if(run.mode==='check')setLatestCheck(run);
    void persist().then(()=>flush()).catch(()=>setSaveStatus('结果未同步，请重试'));
  },[persist,flush]);
  const encodeBackup=(files: Record<string,string>)=>artifact.schemaVersion===2?JSON.stringify(files):files['/src/algorithm.js'];
  const decodeBackup=(value:string):Record<string,string>=>artifact.schemaVersion===2?JSON.parse(value):{'/src/algorithm.js':value};
  const resolveConflict=async(keepLocal: boolean)=>{
    const remote=conflict || await pblApi.getWorkspace(artifact.exerciseId);
    if(!state.current) return;
    state.current.backup=encodeBackup(keepLocal?remote.files:state.current.workspace.files);
    setBackup(state.current.backup);
    state.current.workspace=keepLocal?{...state.current.workspace,revision:remote.revision}:remote;
    state.current.dirty=keepLocal;state.current.pendingPatch=undefined;
    setWorkspace({...state.current.workspace});setConflict(null);conflictRef.current='none';
    await persist();void flush();
  };
  const resetCode=async()=>{
    if(!state.current || !window.confirm('恢复初始代码？当前代码将保留为可恢复备份。'))return;
    state.current.backup=encodeBackup(state.current.workspace.files);setBackup(state.current.backup);
    await persist();change({files:artifact.schemaVersion===2?{...artifact.starterFiles}:{'/src/algorithm.js':artifact.starterCode}});
  };
  return {workspace,latestCheck,saveStatus,conflict,backup,change,onRunReport,resetCode,resolveConflict,retrySave:flush,
    restoreBackup:()=>backup && change({files:decodeBackup(backup)})};
}
