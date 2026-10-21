import { apiRequest } from '../stitch/api/client';
import type { ProjectArtifact, ProjectReport } from './projectTypes';
import type { JobRecord } from '../jobs/types';
import type { ExerciseArtifact, RunReport, TestCase, Workspace } from './types';
import type { TutorHistory, TutorQuestion, TutorTurn } from './tutorTypes';
export type WorkspacePatch = Omit<Workspace, 'exerciseId' | 'revision' | 'updatedAt'> & {expectedRevision: number; mutationId: string};
export type RunRecord = RunReport & {code: string; cases: TestCase[]; evidenceSource: 'browser_reported'};
export interface PblDetail {exerciseId: string; job: JobRecord | null; artifact: ExerciseArtifact | ProjectArtifact | null}
export interface PblItem {exerciseId: string; topic: string; status: string; jobId: string}
const path = (id: string) => '/api/pbl/' + encodeURIComponent(id);
export const pblApi = {
  create: (topic: string, request_id: string) => apiRequest<{exerciseId: string; jobId: string; status: string}>('/api/pbl', {method:'POST',body:JSON.stringify({topic,request_id})}),
  list: (signal?: AbortSignal) => apiRequest<{items:PblItem[]}>('/api/pbl?limit=100', {signal}),
  get: (id: string) => apiRequest<PblDetail>(path(id)),
  getWorkspace: (id: string) => apiRequest<Workspace>(path(id)+'/workspace'),
  saveWorkspace: (id: string, patch: WorkspacePatch) => apiRequest<Workspace>(path(id)+'/workspace', {method:'PUT',body:JSON.stringify(patch)}),
  appendRun: (id: string, run: RunRecord) => apiRequest<RunRecord>(path(id)+'/runs',{method:'POST',body:JSON.stringify(run)}),
  checkProject: (id: string, input: {artifactVersion:number; taskId:string; runId:string; files:Record<string,string>}) => apiRequest<ProjectReport>(path(id)+'/check',{method:'POST',body:JSON.stringify(input)}),
  listProjectRuns: (id: string) => apiRequest<{items:ProjectReport[]}>(path(id)+'/runs?limit=100'),
  listRuns: (id: string) => apiRequest<{items:RunRecord[]}>(path(id)+'/runs'),
  tutorHistory: (id: string, version: number, taskId: string, cursor?: string, signal?: AbortSignal) =>
    apiRequest<TutorHistory>(path(id)+'/tutor?'+new URLSearchParams({artifactVersion:String(version),taskId,...(cursor?{cursor}:{})}),{signal}),
  askTutor: (id: string, question: TutorQuestion) => apiRequest<TutorTurn>(path(id)+'/tutor',{method:'POST',body:JSON.stringify(question)}),
};
