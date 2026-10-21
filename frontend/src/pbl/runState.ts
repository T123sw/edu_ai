import type { ExerciseArtifact, RunReport } from './types';
import { isCurrentReport } from './protocol';
export function deriveTaskStatus({ hasEdits, currentCodeHash, artifact, latestCheck }: {
  hasEdits: boolean; currentCodeHash: string; artifact: ExerciseArtifact; latestCheck?: RunReport | null;
}): 'not_started' | 'in_progress' | 'tests_passed' | 'needs_recheck' {
  if (isCurrentReport(latestCheck, artifact, currentCodeHash)) return 'tests_passed';
  if (latestCheck?.mode === 'check' && latestCheck.codeHash !== currentCodeHash) return 'needs_recheck';
  return hasEdits || latestCheck ? 'in_progress' : 'not_started';
}
