import type { ExerciseArtifact, RunReport } from './types';
export async function hashCode(code: string): Promise<string> {
  const buffer = new TextEncoder().encode(JSON.stringify([['/src/algorithm.js', code]]));
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}
export function isCurrentReport(report: RunReport | null | undefined, artifact: ExerciseArtifact, codeHash: string): boolean {
  if (!report || report.exerciseId !== artifact.exerciseId || report.artifactVersion !== artifact.artifactVersion ||
    report.templateVersion !== artifact.templateVersion || report.taskId !== artifact.tasks[0].id ||
    report.codeHash !== codeHash || report.mode !== 'check' || report.status !== 'passed') return false;
  const ids = artifact.tasks[0].testCaseIds;
  return report.results.length === ids.length && new Set(report.results.map(r => r.caseId)).size === ids.length &&
    report.results.every(r => ids.includes(r.caseId) && r.status === 'passed');
}
