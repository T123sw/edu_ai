import { useJobStore } from "../../../jobs/jobStore";

export function GenerationTaskStatus({ jobId }: { jobId: string | null }) {
  const job = useJobStore((state) => jobId ? state.jobs[jobId] : undefined);
  if (!jobId) return null;
  return (
    <section className="generation-task-status" aria-live="polite">
      <strong>{job?.status === "succeeded" ? "生成完成" : job?.status === "failed" ? "生成失败" : "已进入后台生成"}</strong>
      <p>{job?.message || `任务 ${jobId} 已保存，可在任务中心继续查看。`}</p>
      {job ? <progress max={100} value={job.progress} /> : null}
    </section>
  );
}
