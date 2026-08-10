import { useEffect, useMemo, useSyncExternalStore } from 'react';
import type {
  PagePlaybackCheckpoint,
  PagePlaybackSnapshot,
} from '../../openmaic/pagePlaybackController';
import {
  fetchClassroomQaAudioBlobUrl,
  getClassroomQaSession,
  submitClassroomQaTurn,
} from '../api/classroomQa';
import type {
  ClassroomQaCheckpoint,
  ClassroomQaSession,
  ClassroomQaTurnRequest,
  ClassroomQaTurnSubmission,
} from '../api/types';
import {
  INITIAL_CLASSROOM_QA_STATE,
  reduceClassroomQa,
  type ClassroomQaEvent,
  type ClassroomQaState,
} from './classroomQaState';

export interface AnswerAudioHandle {
  play(): Promise<'ended' | 'failed'>;
  stop(): void;
  dispose(): void;
}

export type InterruptionPlayback = {
  interrupt(): PagePlaybackCheckpoint | null;
  resumeInterrupted(checkpoint: PagePlaybackCheckpoint): boolean;
  snapshot(): PagePlaybackSnapshot;
};

export type InterruptionDependencies = {
  courseId: string;
  classroomId: string;
  playback: InterruptionPlayback;
  loadSession: (
    courseId: string,
    classroomId: string,
  ) => Promise<ClassroomQaSession>;
  submitTurn: (
    courseId: string,
    classroomId: string,
    request: ClassroomQaTurnRequest,
  ) => Promise<ClassroomQaTurnSubmission>;
  loadAudio: (path: string) => Promise<string>;
  createAudio: (url: string) => AnswerAudioHandle;
  speakBrowser: (text: string) => Promise<'ended' | 'failed'>;
  cancelBrowserSpeech: () => void;
  createClientTurnId: () => string;
  revokeObjectUrl: (url: string) => void;
};

export type ClassroomInterruptionController = {
  readonly state: ClassroomQaState;
  openQuestion(): void;
  cancelDraft(): void;
  submitQuestion(question: string): Promise<void>;
  stopAnswerAndResume(): void;
  retry(): Promise<void>;
  closePanel(): void;
  resetForNavigation(): void;
};

type ActiveOwnership = {
  clientTurnId: string;
  sceneIndex: number;
  pageRevision: number;
};

export class ClassroomInterruptionCoordinator
  implements ClassroomInterruptionController
{
  private currentState: ClassroomQaState = { ...INITIAL_CLASSROOM_QA_STATE };
  private readonly listeners = new Set<() => void>();
  private checkpoint: PagePlaybackCheckpoint | null = null;
  private ownership: ActiveOwnership | null = null;
  private answerAudio: AnswerAudioHandle | null = null;
  private objectUrl: string | null = null;
  private operationToken = 0;
  private resumeConsumed = false;
  private disposed = false;

  constructor(private readonly dependencies: InterruptionDependencies) {}

  get state(): ClassroomQaState {
    return this.currentState;
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): ClassroomQaState => this.currentState;

  async loadSession(): Promise<void> {
    const token = this.operationToken;
    try {
      const session = await this.dependencies.loadSession(
        this.dependencies.courseId,
        this.dependencies.classroomId,
      );
      if (!this.disposed && token === this.operationToken) {
        this.dispatch({ type: 'session_loaded', turns: session.turns });
      }
    } catch {
      // Session history is supplementary. Submitting still reports actionable errors.
    }
  }

  openQuestion(): void {
    if (this.disposed || this.currentState.activeTurn) return;
    if (this.currentState.phase === 'drafting') return;
    this.dispatch({ type: 'open' });
  }

  cancelDraft(): void {
    if (this.disposed || this.currentState.phase !== 'drafting') return;
    this.checkpoint = null;
    this.dispatch({ type: 'cancel_draft' });
  }

  async submitQuestion(question: string): Promise<void> {
    if (this.disposed || this.currentState.phase !== 'drafting') return;
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion || normalizedQuestion.length > 1000) return;
    const checkpoint = this.dependencies.playback.interrupt();
    if (!checkpoint) return;
    this.checkpoint = checkpoint;
    this.resumeConsumed = false;
    const clientTurnId = this.dependencies.createClientTurnId();
    this.dispatch({ type: 'submit', question: normalizedQuestion, clientTurnId });
    await this.runSubmission(clientTurnId, normalizedQuestion);
  }

  async retry(): Promise<void> {
    const active = this.currentState.activeTurn;
    if (this.disposed || this.currentState.phase !== 'error' || !active) return;
    this.dispatch({ type: 'retry' });
    await this.runSubmission(active.clientTurnId, active.question);
  }

  stopAnswerAndResume(): void {
    if (this.disposed || !this.checkpoint || !this.currentState.activeTurn) return;
    this.operationToken += 1;
    this.answerAudio?.stop();
    this.dependencies.cancelBrowserSpeech();
    this.dispatch({
      type: 'answer_finished',
      clientTurnId: this.currentState.activeTurn.clientTurnId,
    });
    this.finishResume(this.currentState.isOpen);
  }

  closePanel(): void {
    if (this.currentState.phase === 'drafting') {
      this.cancelDraft();
      return;
    }
    this.dispatch({ type: 'close' });
  }

  resetForNavigation(): void {
    if (this.disposed) return;
    this.operationToken += 1;
    this.answerAudio?.stop();
    this.dependencies.cancelBrowserSpeech();
    this.cleanupMedia();
    this.checkpoint = null;
    this.ownership = null;
    this.resumeConsumed = false;
    this.dispatch({ type: 'reset' });
  }

  dispose(): void {
    if (this.disposed) return;
    this.operationToken += 1;
    this.answerAudio?.stop();
    this.dependencies.cancelBrowserSpeech();
    this.cleanupMedia();
    this.disposed = true;
    this.listeners.clear();
  }

  private async runSubmission(
    clientTurnId: string,
    question: string,
  ): Promise<void> {
    const checkpoint = this.checkpoint;
    if (!checkpoint) return;
    const token = ++this.operationToken;
    this.ownership = {
      clientTurnId,
      sceneIndex: checkpoint.sceneIndex,
      pageRevision: checkpoint.pageRevision,
    };
    try {
      const submission = await this.dependencies.submitTurn(
        this.dependencies.courseId,
        this.dependencies.classroomId,
        {
          client_turn_id: clientTurnId,
          question,
          checkpoint: toApiCheckpoint(checkpoint),
        },
      );
      if (!this.ownsResult(clientTurnId, token)) return;
      this.dispatch({
        type: 'turn_received',
        clientTurnId,
        turn: submission.turn,
      });

      if (submission.turn.tts_status === 'ready' && submission.turn.audio_url) {
        const played = await this.playServerAudio(
          submission.turn.audio_url,
          clientTurnId,
          token,
        );
        if (played === 'ended' || !this.ownsResult(clientTurnId, token)) return;
      }
      await this.playBrowserSpeech(
        `${submission.turn.answer_text}\n${submission.turn.transition_text}`,
        clientTurnId,
        token,
      );
    } catch (error) {
      if (!this.ownsResult(clientTurnId, token)) return;
      this.dispatch({
        type: 'fail',
        clientTurnId,
        message: error instanceof Error ? error.message : '课堂问答失败',
      });
    }
  }

  private async playServerAudio(
    path: string,
    clientTurnId: string,
    token: number,
  ): Promise<'ended' | 'failed'> {
    try {
      const objectUrl = await this.dependencies.loadAudio(path);
      if (!this.ownsResult(clientTurnId, token)) {
        this.dependencies.revokeObjectUrl(objectUrl);
        return 'failed';
      }
      this.objectUrl = objectUrl;
      this.answerAudio = this.dependencies.createAudio(objectUrl);
      this.dispatch({ type: 'answer_playing', clientTurnId });
      const result = await this.answerAudio.play();
      if (!this.ownsResult(clientTurnId, token)) return result;
      if (result === 'ended') {
        this.dispatch({ type: 'answer_finished', clientTurnId });
        this.finishResume(this.currentState.isOpen);
        return 'ended';
      }
      this.cleanupMedia();
      return 'failed';
    } catch {
      this.cleanupMedia();
      return 'failed';
    }
  }

  private async playBrowserSpeech(
    text: string,
    clientTurnId: string,
    token: number,
  ): Promise<void> {
    if (!this.ownsResult(clientTurnId, token)) return;
    this.dispatch({ type: 'answer_playing', clientTurnId });
    const result = await this.dependencies.speakBrowser(text);
    if (!this.ownsResult(clientTurnId, token)) return;
    if (result === 'ended') {
      this.dispatch({ type: 'answer_finished', clientTurnId });
      this.finishResume(this.currentState.isOpen);
      return;
    }
    this.dispatch({
      type: 'fail',
      clientTurnId,
      message: '语音播放失败，请手动继续授课。',
    });
  }

  private finishResume(keepOpen: boolean): void {
    const checkpoint = this.checkpoint;
    this.cleanupMedia();
    if (!checkpoint || this.resumeConsumed) return;
    this.resumeConsumed = true;
    const resumed = this.dependencies.playback.resumeInterrupted(checkpoint);
    if (!resumed) {
      const clientTurnId = this.currentState.activeTurn?.clientTurnId;
      if (clientTurnId) {
        this.dispatch({
          type: 'fail',
          clientTurnId,
          message: '课堂位置已经变化，无法从原位置继续。',
        });
      }
      return;
    }
    this.checkpoint = null;
    this.ownership = null;
    this.dispatch({ type: 'resume_complete', keepOpen });
  }

  private ownsResult(clientTurnId: string, token: number): boolean {
    if (
      this.disposed ||
      token !== this.operationToken ||
      this.ownership?.clientTurnId !== clientTurnId ||
      this.currentState.activeTurn?.clientTurnId !== clientTurnId
    ) return false;
    const snapshot = this.dependencies.playback.snapshot();
    return (
      snapshot.sceneIndex === this.ownership.sceneIndex &&
      snapshot.revision === this.ownership.pageRevision
    );
  }

  private cleanupMedia(): void {
    this.answerAudio?.dispose();
    this.answerAudio = null;
    if (this.objectUrl) {
      this.dependencies.revokeObjectUrl(this.objectUrl);
      this.objectUrl = null;
    }
  }

  private dispatch(event: ClassroomQaEvent): void {
    if (this.disposed) return;
    const next = reduceClassroomQa(this.currentState, event);
    if (next === this.currentState) return;
    this.currentState = next;
    this.listeners.forEach((listener) => listener());
  }
}

function toApiCheckpoint(
  checkpoint: PagePlaybackCheckpoint,
): ClassroomQaCheckpoint {
  return {
    scene_id: checkpoint.sceneId,
    scene_index: checkpoint.sceneIndex,
    action_index: checkpoint.actionIndex,
    action_id: checkpoint.actionId,
    phase: checkpoint.phase,
    page_revision: checkpoint.pageRevision,
  };
}

type UseClassroomInterruptionOptions = {
  courseId: string;
  classroomId: string;
  playback: InterruptionPlayback;
  pageRevision: number;
  enabled?: boolean;
};

export function useClassroomInterruption({
  courseId,
  classroomId,
  playback,
  pageRevision,
  enabled = true,
}: UseClassroomInterruptionOptions): ClassroomInterruptionController {
  const coordinator = useMemo(
    () => {
      // A page revision owns its checkpoint runtime. Recreate on hard replay
      // or navigation so late results cannot resume a different page.
      void pageRevision;
      return new ClassroomInterruptionCoordinator({
        courseId,
        classroomId,
        playback,
        loadSession: getClassroomQaSession,
        submitTurn: submitClassroomQaTurn,
        loadAudio: fetchClassroomQaAudioBlobUrl,
        createAudio: (url) => new BrowserAnswerAudio(url),
        speakBrowser: speakWithBrowser,
        cancelBrowserSpeech: () => window.speechSynthesis?.cancel(),
        createClientTurnId: () => crypto.randomUUID(),
        revokeObjectUrl: (url) => URL.revokeObjectURL(url),
      });
    },
    [classroomId, courseId, pageRevision, playback],
  );
  const state = useSyncExternalStore(
    coordinator.subscribe,
    coordinator.getSnapshot,
    coordinator.getSnapshot,
  );
  useEffect(() => {
    if (enabled) void coordinator.loadSession();
    return () => coordinator.dispose();
  }, [coordinator, enabled]);
  return useMemo(
    () => ({
      state,
      openQuestion: () => coordinator.openQuestion(),
      cancelDraft: () => coordinator.cancelDraft(),
      submitQuestion: (question) => coordinator.submitQuestion(question),
      stopAnswerAndResume: () => coordinator.stopAnswerAndResume(),
      retry: () => coordinator.retry(),
      closePanel: () => coordinator.closePanel(),
      resetForNavigation: () => coordinator.resetForNavigation(),
    }),
    [coordinator, state],
  );
}

class BrowserAnswerAudio implements AnswerAudioHandle {
  private readonly audio: HTMLAudioElement;
  private settle: ((result: 'ended' | 'failed') => void) | null = null;

  constructor(url: string) {
    this.audio = new Audio(url);
  }

  play(): Promise<'ended' | 'failed'> {
    return new Promise((resolve) => {
      let settled = false;
      const finish = (result: 'ended' | 'failed') => {
        if (settled) return;
        settled = true;
        this.audio.onended = null;
        this.audio.onerror = null;
        this.settle = null;
        resolve(result);
      };
      this.settle = finish;
      this.audio.onended = () => finish('ended');
      this.audio.onerror = () => finish('failed');
      this.audio.play().catch(() => finish('failed'));
    });
  }

  stop(): void {
    this.audio.pause();
    this.settle?.('ended');
  }

  dispose(): void {
    this.audio.pause();
    this.audio.onended = null;
    this.audio.onerror = null;
  }
}

function speakWithBrowser(text: string): Promise<'ended' | 'failed'> {
  if (
    typeof window === 'undefined' ||
    !window.speechSynthesis ||
    typeof SpeechSynthesisUtterance === 'undefined'
  ) return Promise.resolve('failed');
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    let settled = false;
    const finish = (result: 'ended' | 'failed') => {
      if (settled) return;
      settled = true;
      resolve(result);
    };
    utterance.lang = 'zh-CN';
    utterance.onend = () => finish('ended');
    utterance.onerror = () => finish('failed');
    window.speechSynthesis.speak(utterance);
  });
}
