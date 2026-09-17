import { useEffect, useState } from "react";
import {
  advanceJobs,
  seedState,
  sharedSeeds,
  type Classroom,
  type LearningState,
} from "./model";

export const storageKey = (owner: string) =>
  `edu-self-learning:v1:${encodeURIComponent(owner)}`;
const SHARED_KEY = "edu-self-learning:shared:v1";
const object = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === "object";
function validRoom(v: unknown): v is Classroom {
  return (
    object(v) &&
    typeof v.id === "string" &&
    typeof v.title === "string" &&
    typeof v.goal === "string" &&
    typeof v.tone === "string" &&
    typeof v.selectedId === "string" &&
    (v.understanding === undefined || (object(v.understanding) && Object.values(v.understanding).every(value => value === "review" || value === "understood"))) &&
    typeof v.updatedAt === "number" &&
    Number.isFinite(v.updatedAt) &&
    object(v.progress) &&
    Object.values(v.progress).every(
      (e) =>
        object(e) &&
        typeof e.completed === "boolean" &&
        typeof e.position === "number" &&
        Number.isFinite(e.position) &&
        e.position >= 0 &&
        typeof e.note === "string",
    ) &&
    Array.isArray(v.messages) &&
    v.messages.every(
      (m) =>
        object(m) &&
        typeof m.text === "string" &&
        typeof m.id === "string" &&
        (m.role === "user" || m.role === "assistant") &&
        typeof m.resourceId === "string" &&
        typeof m.resourceTitle === "string",
    ) &&
    Array.isArray(v.chapters) &&
    v.chapters.length > 0 &&
    v.chapters.every(
      (c) =>
        object(c) &&
        typeof c.id === "string" &&
        typeof c.title === "string" &&
        Array.isArray(c.resources) &&
        c.resources.length > 0 &&
        c.resources.every(validResource),
    )
  );
}
function validResource(v: unknown): boolean {
  return (
    object(v) &&
    typeof v.id === "string" &&
    typeof v.title === "string" &&
    typeof v.topic === "string" &&
    ["report", "video", "slides", "quiz"].includes(String(v.kind)) &&
    typeof v.ready === "boolean" &&
    typeof v.minutes === "number" &&
    typeof v.createdAt === "number"
  );
}
export function restoreState(
  raw: string | null,
  showcase = false,
): LearningState {
  try {
    const v: unknown = JSON.parse(raw || "null");
    if (
      object(v) &&
      v.version === 1 &&
      Array.isArray(v.rooms) &&
      v.rooms.every(validRoom) &&
      Array.isArray(v.resources) &&
      v.resources.every(validResource) &&
      Array.isArray(v.jobs) &&
      v.jobs.every(
        (j) =>
          object(j) &&
          typeof j.id === "string" &&
          typeof j.title === "string" &&
          ["running", "done", "cancelled"].includes(String(j.status)) &&
          typeof j.elapsed === "number" &&
          typeof j.duration === "number" &&
          Number.isFinite(j.duration) &&
          Number.isFinite(j.elapsed) &&
          j.duration > 0 &&
          j.elapsed >= 0 &&
          j.elapsed <= j.duration &&
          (!j.roomId || typeof j.roomId === "string") &&
          (!j.resource || validResource(j.resource)),
      )
    )
      return v as LearningState;
  } catch {
    /* Invalid demo data never blocks access to the preview. */
  }
  return seedState(showcase);
}
export function useLearningStore(owner: string, showcase = false) {
  const sharedKey = owner.startsWith("review:") ? `${SHARED_KEY}:review` : SHARED_KEY;
  const [state, setState] = useState<LearningState>(() => {
    try {
      return restoreState(localStorage.getItem(storageKey(owner)), showcase);
    } catch {
      return seedState(showcase);
    }
  });
  const [storageError, setStorageError] = useState(false);
  const [shared, setShared] = useState<Classroom[]>(() => {
    try {
      const v: unknown = JSON.parse(localStorage.getItem(sharedKey) || "null");
      if (Array.isArray(v) && v.every(validRoom)) return v;
    } catch {
      /* Use demo catalog. */
    }
    return sharedSeeds();
  });
  useEffect(() => {
    try {
      localStorage.setItem(storageKey(owner), JSON.stringify(state));
      setStorageError(false);
    } catch {
      setStorageError(true);
    }
  }, [owner, state]);
  useEffect(() => {
    try {
      localStorage.setItem(sharedKey, JSON.stringify(shared));
    } catch {
      setStorageError(true);
    }
  }, [shared, sharedKey]);
  useEffect(() => {
    const timer = window.setInterval(
      () => setState((s) => advanceJobs(s, 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, []);
  return { state, setState, shared, setShared, storageError };
}
