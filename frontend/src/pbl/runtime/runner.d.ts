import type { CaseResult, ExecutionHandle, RunRequest } from '../types';
export function createExecution(request: RunRequest, onCase?: (result: CaseResult) => void): ExecutionHandle;
export function inspectResult(fn: (input: number[]) => unknown, input: number[], expected: number[]): {
  actual?: number[]; inputAfter?: number[]; returnedSameReference: boolean; passed: boolean;
  error?: {code: string; message: string};
};
