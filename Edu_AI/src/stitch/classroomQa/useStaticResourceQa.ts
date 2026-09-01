import { useEffect, useMemo, useSyncExternalStore } from "react";
import {
  fetchResourceQaAudioBlobUrl,
  getResourceQaSession,
  submitResourceQaTurn,
} from "../api/resourceQa";
import type {
  ResourceQaAnchor,
  ResourceQaKind,
  ResourceQaSession,
  ResourceQaTurnRequest,
  ResourceQaTurnSubmission,
} from "../api/types";
import type { ClassroomQaController, QaAnswerAudioHandle } from "./classroomQaController";
import {
  INITIAL_CLASSROOM_QA_STATE,
  reduceClassroomQa,
  type ClassroomQaEvent,
  type ClassroomQaState,
} from "./classroomQaState";

export type StaticResourceQaDependencies = {
  resourceKey: string;
  loadSession: () => Promise<ResourceQaSession>;
  submitTurn: (request: ResourceQaTurnRequest) => Promise<ResourceQaTurnSubmission>;
  loadAudio: (path: string) => Promise<string>;
  createAudio: (url: string) => QaAnswerAudioHandle;
  speakBrowser: (text: string) => Promise<"ended" | "failed">;
  cancelBrowserSpeech: () => void;
  createClientTurnId: () => string;
  revokeObjectUrl: (url: string) => void;
  resourceVersion?: number;
  anchor?: ResourceQaAnchor | null;
};

export class StaticResourceQaCoordinator implements ClassroomQaController {
  private currentState: ClassroomQaState = { ...INITIAL_CLASSROOM_QA_STATE };
  private readonly listeners = new Set<() => void>();
  private operationToken = 0;
  private disposed = false;
  private answerAudio: QaAnswerAudioHandle | null = null;
  private objectUrl: string | null = null;

  readonly supportsPlaybackInterruption = false;

  constructor(private readonly dependencies: StaticResourceQaDependencies) {}

  get state(): ClassroomQaState { return this.currentState; }
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => this.listeners.delete(listener); };
  getSnapshot = () => this.currentState;

  async loadSession(): Promise<void> {
    const token = this.operationToken;
    const resourceKey = this.dependencies.resourceKey;
    try {
      const session = await this.dependencies.loadSession();
      if (this.ownsOperation(token, resourceKey)) {
        this.dispatch({ type: "session_loaded", turns: session.turns });
      }
    } catch {
      // History is supplementary; submitting still provides an actionable error.
    }
  }

  async submitQuestion(question: string): Promise<void> {
    if (this.disposed || this.currentState.phase !== "ready") return;
    const normalized = question.trim();
    if (!normalized || normalized.length > 1000) return;
    const clientTurnId = this.dependencies.createClientTurnId();
    this.dispatch({ type: "submit", question: normalized, clientTurnId });
    await this.runSubmission(clientTurnId, normalized, false);
  }

  stopAnswer(): void {
    if (this.disposed) return;
    this.operationToken += 1;
    this.answerAudio?.stop();
    this.dependencies.cancelBrowserSpeech();
    this.cleanupMedia();
    const clientTurnId = this.currentState.activeTurn?.clientTurnId;
    if (clientTurnId) {
      this.dispatch({ type: "answer_finished", clientTurnId });
      this.dispatch({ type: "resume_complete" });
    }
  }

  async retry(): Promise<void> {
    const active = this.currentState.activeTurn;
    if (this.disposed || this.currentState.phase !== "error" || !active) return;
    this.dispatch({ type: "retry" });
    await this.runSubmission(active.clientTurnId, active.question, true);
  }

  resetForNavigation(): void {
    if (this.disposed) return;
    this.operationToken += 1;
    this.answerAudio?.stop();
    this.dependencies.cancelBrowserSpeech();
    this.cleanupMedia();
    this.dispatch({ type: "reset" });
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

  private async runSubmission(clientTurnId: string, question: string, _retry: boolean): Promise<void> {
    const token = ++this.operationToken;
    const resourceKey = this.dependencies.resourceKey;
    try {
      const submission = await this.dependencies.submitTurn({
        client_turn_id: clientTurnId,
        question,
        resource_version: this.dependencies.resourceVersion ?? 1,
        context_scope: "full_resource",
        anchor: this.dependencies.anchor ?? null,
      });
      if (!this.ownsOperation(token, resourceKey)) return;
      this.dispatch({ type: "turn_received", clientTurnId, turn: submission.turn });
      if (submission.turn.tts_status === "ready" && submission.turn.audio_url) {
        const played = await this.playAudio(submission.turn.audio_url, clientTurnId, token, resourceKey);
        if (played === "ended" || !this.ownsOperation(token, resourceKey)) return;
      }
      await this.playBrowser(
        `${submission.turn.answer_text}\n${submission.turn.transition_text}`,
        clientTurnId,
        token,
        resourceKey,
      );
    } catch (error) {
      if (!this.ownsOperation(token, resourceKey)) return;
      this.dispatch({
        type: "fail",
        clientTurnId,
        message: error instanceof Error ? error.message : "资料问答失败",
      });
    }
  }

  private async playAudio(path: string, clientTurnId: string, token: number, resourceKey: string) {
    try {
      const url = await this.dependencies.loadAudio(path);
      if (!this.ownsOperation(token, resourceKey)) {
        this.dependencies.revokeObjectUrl(url);
        return "failed" as const;
      }
      this.objectUrl = url;
      this.answerAudio = this.dependencies.createAudio(url);
      this.dispatch({ type: "answer_playing", clientTurnId });
      const result = await this.answerAudio.play();
      if (result === "ended" && this.ownsOperation(token, resourceKey)) this.finish(clientTurnId);
      else this.cleanupMedia();
      return result;
    } catch {
      this.cleanupMedia();
      return "failed" as const;
    }
  }

  private async playBrowser(text: string, clientTurnId: string, token: number, resourceKey: string) {
    if (!this.ownsOperation(token, resourceKey)) return;
    this.dispatch({ type: "answer_playing", clientTurnId });
    const result = await this.dependencies.speakBrowser(text);
    if (!this.ownsOperation(token, resourceKey)) return;
    if (result === "ended") this.finish(clientTurnId);
    else this.dispatch({ type: "fail", clientTurnId, message: "语音播放失败，请查看文字回答。" });
  }

  private finish(clientTurnId: string) {
    this.cleanupMedia();
    this.dispatch({ type: "answer_finished", clientTurnId });
    this.dispatch({ type: "resume_complete" });
  }

  private ownsOperation(token: number, resourceKey: string) {
    return !this.disposed && token === this.operationToken && resourceKey === this.dependencies.resourceKey;
  }

  private cleanupMedia() {
    this.answerAudio?.dispose();
    this.answerAudio = null;
    if (this.objectUrl) {
      this.dependencies.revokeObjectUrl(this.objectUrl);
      this.objectUrl = null;
    }
  }

  private dispatch(event: ClassroomQaEvent) {
    if (this.disposed) return;
    const next = reduceClassroomQa(this.currentState, event);
    if (next === this.currentState) return;
    this.currentState = next;
    this.listeners.forEach((listener) => listener());
  }
}

type UseStaticResourceQaOptions = {
  courseId: string;
  kind: ResourceQaKind;
  resourceId: string;
  resourceVersion: number;
  anchor?: ResourceQaAnchor | null;
};

export function useStaticResourceQa(options: UseStaticResourceQaOptions): ClassroomQaController {
  const resourceKey = `${options.kind}:${options.resourceId}:${options.resourceVersion}`;
  const coordinator = useMemo(() => new StaticResourceQaCoordinator({
    resourceKey,
    resourceVersion: options.resourceVersion,
    anchor: options.anchor,
    loadSession: () => getResourceQaSession(options.courseId, options.kind, options.resourceId, options.resourceVersion),
    submitTurn: (request) => submitResourceQaTurn(options.courseId, options.kind, options.resourceId, request),
    loadAudio: fetchResourceQaAudioBlobUrl,
    createAudio: (url) => new BrowserQaAudio(url),
    speakBrowser,
    cancelBrowserSpeech: () => window.speechSynthesis?.cancel(),
    createClientTurnId: () => globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2),
    revokeObjectUrl: (url) => URL.revokeObjectURL(url),
  }), [options.anchor, options.courseId, options.kind, options.resourceId, options.resourceVersion, resourceKey]);
  const state = useSyncExternalStore(coordinator.subscribe, coordinator.getSnapshot, coordinator.getSnapshot);
  useEffect(() => {
    void coordinator.loadSession();
    return () => coordinator.dispose();
  }, [coordinator]);
  return useMemo(() => ({
    state,
    supportsPlaybackInterruption: false,
    submitQuestion: (question) => coordinator.submitQuestion(question),
    stopAnswer: () => coordinator.stopAnswer(),
    retry: () => coordinator.retry(),
    resetForNavigation: () => coordinator.resetForNavigation(),
  }), [coordinator, state]);
}

class BrowserQaAudio implements QaAnswerAudioHandle {
  private readonly audio: HTMLAudioElement;
  private settle: ((result: "ended" | "failed") => void) | null = null;
  constructor(url: string) { this.audio = new Audio(url); }
  play() {
    return new Promise<"ended" | "failed">((resolve) => {
      const finish = (result: "ended" | "failed") => {
        this.audio.onended = null; this.audio.onerror = null; this.settle = null; resolve(result);
      };
      this.settle = finish;
      this.audio.onended = () => finish("ended");
      this.audio.onerror = () => finish("failed");
      this.audio.play().catch(() => finish("failed"));
    });
  }
  stop() { this.audio.pause(); this.settle?.("ended"); }
  dispose() { this.audio.pause(); this.audio.onended = null; this.audio.onerror = null; }
}

function speakBrowser(text: string): Promise<"ended" | "failed"> {
  if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === "undefined") return Promise.resolve("failed");
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.onend = () => resolve("ended");
    utterance.onerror = () => resolve("failed");
    window.speechSynthesis.speak(utterance);
  });
}
