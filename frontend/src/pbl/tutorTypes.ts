export interface TutorQuestion {
  requestId: string; artifactVersion: number; taskId: string;
  files: Record<string, string>; question: string;
}
export interface TutorTurn {
  requestId: string; artifactVersion: number; taskId: string;
  question: string; answer: string; codeHash: string; createdAt: number;
  runId: string | null; evidenceSource: 'server_verified' | 'browser_reported' | null;
}
export interface TutorHistory { items: TutorTurn[]; nextCursor: string | null }
