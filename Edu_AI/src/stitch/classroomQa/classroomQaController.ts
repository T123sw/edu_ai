import type { ClassroomQaState } from "./classroomQaState";

export type ClassroomQaController = {
  readonly state: ClassroomQaState;
  readonly supportsPlaybackInterruption: boolean;
  submitQuestion(question: string): Promise<void>;
  stopAnswer(): void;
  retry(): Promise<void>;
  resetForNavigation(): void;
};

export type QaAnswerAudioHandle = {
  play(): Promise<"ended" | "failed">;
  stop(): void;
  dispose(): void;
};
