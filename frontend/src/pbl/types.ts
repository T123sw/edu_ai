export const TEMPLATE_VERSION = 'js-function-v1' as const;
export interface TestCase { id: string; label: string; input: number[]; expected: number[] }
export type RunMode = 'sample' | 'check';
export type RunStatus = 'passed' | 'failed' | 'error' | 'canceled' | 'timeout';
export interface CaseResult {
  caseId: string; status: RunStatus; actual?: number[]; expected: number[];
  inputAfter?: number[]; returnedSameReference?: boolean;
  error?: { code: string; message: string };
}
export interface RunRequest {
  exerciseId: string; runId: string; codeHash: string; code: string; artifactVersion: number;
  templateVersion: string; taskId: string; mode: RunMode; cases: TestCase[];
  caseTimeoutMs?: number; batchTimeoutMs?: number;
}
export interface RunResult {
  exerciseId: string; artifactVersion: number; templateVersion: string; taskId: string; mode: RunMode;
  runId: string; codeHash: string; status: RunStatus; results: CaseResult[]; durationMs: number;
}
export interface ExecutionHandle { stop(): void; result: Promise<RunResult> }
export interface ExerciseTask {
  id: string; title: string; objective: string; instructionsMarkdown: string; explanationMarkdown: string;
  hints: {id: string; title: string; body: string}[];
  examples: {input: number[]; expected: number[]; explanation: string}[]; testCaseIds: string[];
}
export interface ExerciseArtifact {
  schemaVersion: 1; exerciseId: string; artifactVersion: number; templateVersion: string;
  runtimeKind: 'js_function'; topic: string; title: string; summary: string;
  contract: {exportName: 'quickSort'; parameterName: string; inputType: string; outputType: string; mutatesInput: false; returnsNewArray: true};
  tasks: ExerciseTask[]; starterCode: string; testCases: TestCase[]; validationSummary: Record<string, unknown>;
}
export interface Workspace {
  exerciseId: string; artifactVersion: number; revision: number; files: Record<string, string>;
  activeTaskId: string; customInputText: string; updatedAt?: number;
}

export type RunReport = RunResult;
export type NumberCase = TestCase;
