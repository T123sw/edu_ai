import assert from "node:assert/strict";
import test from "node:test";
import type { ResourceQaSession, ResourceQaTurnSubmission } from "../api/types";
import { StaticResourceQaCoordinator } from "./useStaticResourceQa.ts";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

const turnA = {
  turn_id: "turn-a",
  client_turn_id: "client-a",
  question: "A 的问题",
  answer_text: "A 的回答",
  transition_text: "继续 A",
  tts_status: "failed" as const,
  audio_url: null,
  created_at: "2026-09-01T00:00:00Z",
};

function session(resourceId: string, turns = []) : ResourceQaSession {
  return {
    session_id: `session-${resourceId}`,
    course_id: "course-1",
    resource_kind: "study_guide",
    resource_id: resourceId,
    resource_version: 1,
    owner_user_id: "student-a",
    status: "ready",
    turns,
  };
}

function coordinator(resourceKey: string, options: {
  load?: () => Promise<ResourceQaSession>;
  submit?: () => Promise<ResourceQaTurnSubmission>;
} = {}) {
  return new StaticResourceQaCoordinator({
    resourceKey,
    loadSession: options.load ?? (() => Promise.resolve(session(resourceKey))),
    submitTurn: options.submit ?? (() => Promise.resolve({ session_id: "s", turn: turnA })),
    loadAudio: () => Promise.reject(new Error("no audio")),
    createAudio: () => ({ play: () => Promise.resolve("ended" as const), stop() {}, dispose() {} }),
    speakBrowser: () => Promise.resolve("ended" as const),
    cancelBrowserSpeech() {},
    createClientTurnId: () => "client-a",
    revokeObjectUrl() {},
  });
}

test("late answers from resource A cannot pollute resource B and A history reloads", async () => {
  const pendingA = deferred<ResourceQaTurnSubmission>();
  const resourceA = coordinator("A", { submit: () => pendingA.promise });
  const submitA = resourceA.submitQuestion("A 的问题");
  resourceA.dispose();

  const resourceB = coordinator("B");
  await resourceB.loadSession();
  pendingA.resolve({ session_id: "session-A", turn: turnA });
  await submitA;

  assert.equal(resourceB.state.turns.some((turn) => turn.answer_text === "A 的回答"), false);
  assert.equal(resourceA.state.turns.length, 0);

  const resourceAAgain = coordinator("A", { load: () => Promise.resolve(session("A", [turnA])) });
  await resourceAAgain.loadSession();
  assert.deepEqual(resourceAAgain.state.turns, [turnA]);
});

test("static resource controller never claims playback interruption support", () => {
  const value = coordinator("A");
  assert.equal(value.supportsPlaybackInterruption, false);
});
