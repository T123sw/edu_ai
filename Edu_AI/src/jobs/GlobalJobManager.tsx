import { useEffect } from "react";
import { notification } from "antd";
import { listJobs } from "./api";
import { JobCenterDrawer } from "./JobCenterDrawer";
import { JobLeaderLease, getJobPollDelay } from "./jobPolling";
import { jobKindLabel } from "./jobPresentation";
import { jobStore } from "./jobStore";
import type { JobRecord, JobListResponse } from "./types";

const BROADCAST_CHANNEL = "edu-ai-job-center-v2";

type JobBroadcastMessage = {
  type: "snapshot";
  payload: JobListResponse;
};

export function GlobalJobManager({ enabled }: { enabled: boolean }) {
  useEffect(() => {
    if (!enabled) {
      jobStore.getState().reset();
      return;
    }

    let disposed = false;
    let timer: number | null = null;
    let requestInFlight = false;
    const tabId =
      typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `tab-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const lease = new JobLeaderLease(window.localStorage, tabId);
    const channel =
      typeof BroadcastChannel === "undefined"
        ? null
        : new BroadcastChannel(BROADCAST_CHANNEL);

    const clearTimer = () => {
      if (timer !== null) window.clearTimeout(timer);
      timer = null;
    };

    const schedule = (delay: number) => {
      clearTimer();
      timer = window.setTimeout(() => void poll(), delay);
    };

    const publish = (payload: JobListResponse) => {
      channel?.postMessage({
        type: "snapshot",
        payload,
      } satisfies JobBroadcastMessage);
    };

    const mergeSnapshot = (
      payload: JobListResponse,
      notifyTerminal: boolean,
    ) => {
      const transitions = jobStore.getState().mergeJobs(payload.items);
      jobStore.getState().recordPollSuccess(payload.server_time);
      jobStore.getState().setHydrated(true);
      if (notifyTerminal) {
        transitions.forEach(({ job }) => notifyJobTerminal(job));
      }
    };

    const nextDelay = () => {
      const state = jobStore.getState();
      const jobs = state.orderedIds.map((id) => state.jobs[id]);
      return getJobPollDelay({
        visible: document.visibilityState === "visible",
        hasRunning: jobs.some(
          (job) =>
            job.status === "running" || job.status === "cancel_requested",
        ),
        hasQueued: jobs.some((job) => job.status === "queued"),
        failures: state.pollFailures,
      });
    };

    async function poll() {
      if (disposed || requestInFlight) return;
      clearTimer();
      if (!lease.claim()) {
        jobStore.getState().setPolling(false);
        schedule(4_000);
        return;
      }

      requestInFlight = true;
      jobStore.getState().setPolling(true);
      try {
        const payload = await listJobs({ limit: 50 });
        if (disposed) return;
        mergeSnapshot(payload, true);
        publish(payload);
      } catch {
        if (!disposed) jobStore.getState().recordPollFailure();
      } finally {
        requestInFlight = false;
        if (!disposed) {
          const delay = nextDelay();
          if (delay === null) {
            jobStore.getState().setPolling(false);
            lease.release();
          } else {
            schedule(delay);
          }
        }
      }
    }

    const wake = () => {
      if (disposed) return;
      schedule(0);
    };
    const onChannelMessage = (event: MessageEvent<JobBroadcastMessage>) => {
      if (event.data?.type !== "snapshot") return;
      mergeSnapshot(event.data.payload, false);
      if (nextDelay() !== null) schedule(4_000);
    };

    channel?.addEventListener("message", onChannelMessage);
    window.addEventListener("focus", wake);
    window.addEventListener("edu-ai:job-created", wake);
    document.addEventListener("visibilitychange", wake);
    void poll();

    return () => {
      disposed = true;
      clearTimer();
      lease.release();
      channel?.removeEventListener("message", onChannelMessage);
      channel?.close();
      window.removeEventListener("focus", wake);
      window.removeEventListener("edu-ai:job-created", wake);
      document.removeEventListener("visibilitychange", wake);
      jobStore.getState().setPolling(false);
      jobStore.getState().reset();
    };
  }, [enabled]);

  return enabled ? <JobCenterDrawer /> : null;
}

function notifyJobTerminal(job: JobRecord) {
  const title =
    typeof job.input_summary.title === "string"
      ? job.input_summary.title
      : jobKindLabel(job.kind);
  if (job.status === "succeeded") {
    notification.success({
      message: `${jobKindLabel(job.kind)}已完成`,
      description: `${title} 已保存，可在任务中心打开结果。`,
      placement: "topRight",
    });
  } else if (job.status === "partially_succeeded") {
    notification.warning({
      message: `${jobKindLabel(job.kind)}部分完成`,
      description: job.message || `${title} 有部分结果需要处理。`,
      placement: "topRight",
    });
  } else if (job.status === "failed") {
    notification.error({
      message: `${jobKindLabel(job.kind)}失败`,
      description: job.error_message || job.message || `${title} 生成失败。`,
      placement: "topRight",
    });
  }

  if (
    job.result_ref?.resource_type === "course_material" &&
    job.result_ref.course_id
  ) {
    window.dispatchEvent(
      new CustomEvent("edu-ai:course-material-updated", {
        detail: {
          courseId: job.result_ref.course_id,
          materialId: job.result_ref.material_id,
        },
      }),
    );
  }

  const knowledgeCourseId =
    job.result_ref?.resource_type === "knowledge_document"
      ? job.result_ref.course_id
      : job.kind === "rag_import"
        ? job.course_id
        : undefined;
  if (knowledgeCourseId) {
    window.dispatchEvent(
      new CustomEvent("edu-ai:knowledge-document-updated", {
        detail: {
          courseId: knowledgeCourseId,
          documentId:
            job.result_ref?.document_id || job.input_summary.document_id,
        },
      }),
    );
  }
}
