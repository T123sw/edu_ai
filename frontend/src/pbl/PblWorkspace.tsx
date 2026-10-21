import { useEffect, useState, type ReactNode } from 'react';
import { PracticeGenerationProgress } from '../practice/PracticeGenerationProgress';
import { serialPolling } from '../liveLearning/serialPolling';
import { pblApi, type PblDetail } from './api';
import { ProjectWorkspace } from './ProjectWorkspace';
import './pbl.css';
import { AlgorithmWorkspace } from './AlgorithmWorkspace';
export function PblWorkspace({exerciseId,owner,pendingContent}: {exerciseId:string;owner:string;pendingContent?:ReactNode}) {
  const [detail,setDetail]=useState<PblDetail | null>(null),[error,setError]=useState('');
  useEffect(()=>serialPolling(async signal=>{
    try {const value=await pblApi.get(exerciseId);if(!signal.aborted){setDetail(value);setError('');}}
    catch {if(!signal.aborted)setError('暂时无法读取练习，请检查连接。');}
  },2000),[exerciseId]);
  if(detail?.artifact?.schemaVersion===2)return <ProjectWorkspace key={`${owner}:${exerciseId}:${detail.artifact.artifactVersion}`} owner={owner} artifact={detail.artifact}/>;
  if(detail?.artifact)return <AlgorithmWorkspace key={`${owner}:${exerciseId}:${detail.artifact.artifactVersion}`} owner={owner} artifact={detail.artifact}/>;
  return <>{pendingContent}<PracticeGenerationProgress mode="code" job={detail?.job} error={error}
    goal={String(detail?.job?.input_summary?.topic || '')} onClose={() => { location.hash = '/practice/code'; }}
    onJobChange={job => setDetail(previous => previous && { ...previous, job })} /></>;
}
