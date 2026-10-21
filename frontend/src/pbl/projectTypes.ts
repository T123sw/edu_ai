import type {ProjectRuntime} from './projectRuntime';
export interface ProjectStep {
  id: string; stepId: string; title: string; objective: string; instructionsMarkdown: string;
  explanationMarkdown: string; hints: string[]; focusFiles: string[]; checkIds: string[]; cumulativeCheckIds: string[];
}
export interface UiLocator {role?: string; name?: string; testId?: string; index?: number}
export interface UiTarget extends UiLocator {within?: UiLocator}
export interface UiAction {
  type: 'click'|'fill'|'press'|'assert'; target: UiTarget; relativeTo?: UiTarget;
  value?: string; assertion?: string; expected?: string|number|boolean;
}
export interface UiCheck {id: string; label: string; actions: UiAction[]; viewport?: 'desktop'|'mobile'}
export interface JestCheck {id:string;label:string;engine:'sandpack-jest';source:string;viewport?:'desktop'|'mobile'}
export interface HttpCheck {id:string;label:string;engine:'http';requests:{method:string;path:string;body?:unknown;status:number;jsonBody?:unknown;text?:string}[];viewport?:'desktop'|'mobile'}
export type ProjectCheck = UiCheck | JestCheck | HttpCheck;
export interface ProjectArtifact {
  schemaVersion: 2; runtimeKind: 'react_app'|'sandpack_project'; runtime?:ProjectRuntime|null; templateVersion: 'react-app-v1'|'sandpack-project-v1'; exerciseId: string;
  artifactVersion: number; topic: string; title: string; summary: string; starterFiles: Record<string,string>;
  tasks: ProjectStep[]; checks: ProjectCheck[]; validationSummary: Record<string,unknown>;
  plan: {goal: string; steps: {id:string; deliverable:string}[]};
}
export interface ProjectReport {
  runId: string; exerciseId: string; artifactVersion: number; templateVersion: 'react-app-v1'|'sandpack-project-v1'; taskId: string;
  codeHash: string; status: 'passed'|'failed'; results: {caseId: string; status:'passed'|'failed'; message:string}[];
  durationMs: number; evidenceSource: 'server_verified';
}
