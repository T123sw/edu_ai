import { useMemo, useState } from "react";
import {
  Button,
  Modal,
  Progress,
  Tooltip,
  Typography,
  message,
} from "antd";
import { PlayCircleOutlined } from "@ant-design/icons";
import {
  CLASSROOM_STEP_LABELS,
  generateClassroom,
} from "../../stitch/api/classroom";
import { buildClassroomPlayerHash } from "../../openmaic/classroomGenerationFlow";
import {
  registerCreatedJob,
  useCourseJobs,
} from "../../jobs/jobStore";
import { isActiveJob } from "../../jobs/types";
import "./ClassroomGenerationEntry.css";
import { classroomDefinition } from "../generation/definitions/classroom";
import { ClassroomForm } from "../generation/forms/ClassroomForm";

const { Text } = Typography;

type Props = {
  courseId?: string;
};

export function ClassroomGenerationEntry({ courseId }: Props) {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState(() => classroomDefinition.defaultConfig());
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const classroomJobs = useCourseJobs(courseId, "generate_classroom");
  const job = useMemo(
    () =>
      classroomJobs.find((candidate) => candidate.edu_job_id === selectedJobId) ??
      classroomJobs.find(isActiveJob) ??
      null,
    [classroomJobs, selectedJobId],
  );
  const isBusy = Boolean(job && isActiveJob(job));
  const classroomId =
    job?.status === "succeeded" &&
    typeof job.result_ref?.classroom_id === "string"
      ? job.result_ref.classroom_id
      : null;

  const openModal = () => {
    if (!courseId) {
      message.warning("请先选择一门课程");
      return;
    }
    setError(null);
    setOpen(true);
  };

  const submit = async () => {
    if (!courseId || Object.keys(classroomDefinition.validate(config)).length > 0 || submitting || isBusy) return;

    setSubmitting(true);
    setError(null);
    try {
      const created = await generateClassroom(courseId, classroomDefinition.serialize({ courseId, source: { mode: "course_auto", selectedDocumentIds: [] }, config }) as Parameters<typeof generateClassroom>[1]);
      registerCreatedJob(created);
      setSelectedJobId(created.edu_job_id);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "AI 课堂生成失败，请重试",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const openPlayer = () => {
    if (!courseId || !classroomId) return;
    setOpen(false);
    window.location.hash = buildClassroomPlayerHash(courseId, classroomId);
  };

  const progressStatus =
    job?.status === "failed"
      ? "exception"
      : job?.status === "succeeded"
        ? "success"
        : "active";
  const jobError = job?.error_message || job?.error;

  return (
    <>
      <section className="classroom-generation-entry" aria-label="AI 课堂生成">
        <div className="classroom-generation-entry__icon" aria-hidden="true">
          <PlayCircleOutlined />
        </div>
        <div className="classroom-generation-entry__copy">
          <strong>AI 课堂</strong>
          <span>输入主题，自动生成可播放、可导出的课堂。</span>
        </div>
        <Tooltip title={courseId ? undefined : "请先选择一门课程"}>
          <span className="classroom-generation-entry__button-wrap">
            <Button
              className="classroom-generation-entry__button"
              type="primary"
              onClick={openModal}
              disabled={!courseId}
            >
              {isBusy ? "查看进度" : "开始备课"}
            </Button>
          </span>
        </Tooltip>
      </section>

      <Modal
        title="生成 AI 课堂"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        destroyOnHidden={false}
      >
        <div className="classroom-generation-entry__modal-body">
          <Text type="secondary">
            输入本节课的主题和重点。任务提交后可以关闭窗口或刷新页面，进度会保留在任务中心。
          </Text>
          <ClassroomForm value={config} onChange={setConfig} errors={classroomDefinition.validate(config)} />

          {job ? (
            <div
              className="classroom-generation-entry__progress"
              role="status"
              aria-live="polite"
            >
              <div className="classroom-generation-entry__progress-heading">
                <Text strong>
                  {CLASSROOM_STEP_LABELS[job.step] ?? job.step}
                </Text>
                <Text type="secondary">{job.progress}%</Text>
              </div>
              <Progress
                percent={job.progress}
                status={progressStatus}
                showInfo={false}
              />
              <Text type="secondary">
                {job.message || "系统正在后台准备课堂，请稍候…"}
              </Text>
              {job.status === "failed" ? (
                <Text type="danger">{jobError || "生成失败，请在任务中心重试"}</Text>
              ) : null}
              {job.status === "canceled" ? (
                <Text type="secondary">任务已取消，可以重新填写需求。</Text>
              ) : null}
            </div>
          ) : null}

          {error ? (
            <Text
              className="classroom-generation-entry__error"
              type="danger"
              role="alert"
            >
              {error}
            </Text>
          ) : null}

          <div className="classroom-generation-entry__modal-actions">
            <Button onClick={() => setOpen(false)}>
              {isBusy ? "转到后台" : "关闭"}
            </Button>
            {classroomId ? (
              <Button type="primary" onClick={openPlayer}>
                立即播放
              </Button>
            ) : (
              <Button
                type="primary"
                loading={submitting}
                disabled={isBusy || Object.keys(classroomDefinition.validate(config)).length > 0}
                onClick={() => void submit()}
              >
                {isBusy ? "正在后台生成" : error ? "重新提交" : "开始生成"}
              </Button>
            )}
          </div>
        </div>
      </Modal>
    </>
  );
}
