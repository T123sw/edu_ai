import { useMemo } from "react";
import { useStore } from "zustand";
import { createStore, type StoreApi } from "zustand/vanilla";
import {
  isActiveJob,
  isTerminalJob,
  type JobRecord,
} from "./types";

export type JobTransition = {
  previous: JobRecord;
  job: JobRecord;
};

export type JobStoreState = {
  jobs: Record<string, JobRecord>;
  orderedIds: string[];
  unreadTerminalIds: string[];
  activeCount: number;
  hydrated: boolean;
  polling: boolean;
  pollFailures: number;
  lastPolledAt: string | null;
  mergeJobs: (jobs: JobRecord[]) => JobTransition[];
  markRead: (jobId: string) => void;
  markAllRead: () => void;
  setHydrated: (hydrated: boolean) => void;
  setPolling: (polling: boolean) => void;
  recordPollSuccess: (serverTime?: string) => void;
  recordPollFailure: () => void;
  jobsForCourse: (courseId: string, kind?: string) => JobRecord[];
  reset: () => void;
};

const EMPTY_STATE = {
  jobs: {},
  orderedIds: [],
  unreadTerminalIds: [],
  activeCount: 0,
  hydrated: false,
  polling: false,
  pollFailures: 0,
  lastPolledAt: null,
} satisfies Pick<
  JobStoreState,
  | "jobs"
  | "orderedIds"
  | "unreadTerminalIds"
  | "activeCount"
  | "hydrated"
  | "polling"
  | "pollFailures"
  | "lastPolledAt"
>;

export function createJobStore(): StoreApi<JobStoreState> {
  return createStore<JobStoreState>((set, get) => ({
    ...EMPTY_STATE,
    mergeJobs(incoming) {
      const current = get();
      const nextJobs = { ...current.jobs };
      const unread = new Set(current.unreadTerminalIds);
      const transitions: JobTransition[] = [];

      for (const candidate of incoming) {
        const previous = nextJobs[candidate.edu_job_id];
        if (
          previous &&
          (previous.updated_at > candidate.updated_at ||
            (previous.updated_at === candidate.updated_at &&
              previous.version > candidate.version))
        ) {
          continue;
        }
        nextJobs[candidate.edu_job_id] = candidate;
        if (
          previous &&
          isActiveJob(previous) &&
          isTerminalJob(candidate)
        ) {
          transitions.push({ previous, job: candidate });
          unread.add(candidate.edu_job_id);
        }
      }

      const orderedIds = Object.values(nextJobs)
        .sort((left, right) =>
          right.updated_at.localeCompare(left.updated_at) ||
          right.edu_job_id.localeCompare(left.edu_job_id),
        )
        .map((job) => job.edu_job_id);
      const activeCount = orderedIds.reduce(
        (count, id) => count + (isActiveJob(nextJobs[id]) ? 1 : 0),
        0,
      );
      set({
        jobs: nextJobs,
        orderedIds,
        unreadTerminalIds: [...unread],
        activeCount,
      });
      return transitions;
    },
    markRead(jobId) {
      set((state) => ({
        unreadTerminalIds: state.unreadTerminalIds.filter((id) => id !== jobId),
      }));
    },
    markAllRead() {
      set({ unreadTerminalIds: [] });
    },
    setHydrated(hydrated) {
      set({ hydrated });
    },
    setPolling(polling) {
      set({ polling });
    },
    recordPollSuccess(serverTime) {
      set({
        pollFailures: 0,
        lastPolledAt: serverTime || new Date().toISOString(),
      });
    },
    recordPollFailure() {
      set((state) => ({ pollFailures: state.pollFailures + 1 }));
    },
    jobsForCourse(courseId, kind) {
      const state = get();
      return state.orderedIds
        .map((id) => state.jobs[id])
        .filter(
          (job) =>
            job.course_id === courseId && (!kind || job.kind === kind),
        );
    },
    reset() {
      set({ ...EMPTY_STATE });
    },
  }));
}

export const jobStore = createJobStore();

export function useJobStore<T>(selector: (state: JobStoreState) => T): T {
  return useStore(jobStore, selector);
}

export function registerCreatedJob(job: JobRecord): void {
  jobStore.getState().mergeJobs([job]);
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("edu-ai:job-created", { detail: { jobId: job.edu_job_id } }),
    );
  }
}

export function useCourseJobs(courseId: string | undefined, kind?: string) {
  const jobs = useJobStore((state) => state.jobs);
  const orderedIds = useJobStore((state) => state.orderedIds);
  return useMemo(
    () =>
      courseId
        ? orderedIds
            .map((id) => jobs[id])
            .filter(
              (job) =>
                job.course_id === courseId && (!kind || job.kind === kind),
            )
        : [],
    [courseId, jobs, kind, orderedIds],
  );
}
