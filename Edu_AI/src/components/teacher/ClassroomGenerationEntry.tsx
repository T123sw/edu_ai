import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Button,
  Input,
  Modal,
  Progress,
  Tooltip,
  Typography,
  message,
} from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import {
  CLASSROOM_STEP_LABELS,
  generateClassroom,
  getJobStatus,
} from '../../stitch/api/classroom';
import type { EduJob } from '../../stitch/api/types';
import {
  buildClassroomPlayerHash,
  waitForClassroomGenerationJob,
} from '../../openmaic/classroomGenerationFlow';
import {
  clearPendingClassroomGeneration,
  readPendingClassroomGeneration,
  savePendingClassroomGeneration,
} from '../../openmaic/classroomGenerationRecovery';
import './ClassroomGenerationEntry.css';

const { Text } = Typography;

type Props = {
  courseId?: string;
};

export function ClassroomGenerationEntry({ courseId }: Props) {
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState('');
  const [job, setJob] = useState<EduJob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const activeJobIdRef = useRef<string | null>(null);
  const latestJobRef = useRef<EduJob | null>(null);

  const trackJob = useCallback(
    async (
      initialJob: EduJob,
      activeCourseId: string,
      activeTopic: string,
      controller: AbortController,
    ) => {
      activeJobIdRef.current = initialJob.edu_job_id;
      latestJobRef.current = initialJob;
      setTopic(activeTopic);
      setJob(initialJob);
      setSubmitting(true);
      setError(null);
      setOpen(true);

      const handleProgress = (currentJob: EduJob) => {
        latestJobRef.current = currentJob;
        setJob(currentJob);
        savePendingClassroomGeneration(window.localStorage, {
          courseId: activeCourseId,
          topic: activeTopic,
          job: currentJob,
          savedAt: new Date().toISOString(),
        });
      };

      try {
        const result = await waitForClassroomGenerationJob(initialJob, {
          getStatus: getJobStatus,
          signal: controller.signal,
          onProgress: handleProgress,
        });

        clearPendingClassroomGeneration(
          window.localStorage,
          activeCourseId,
          initialJob.edu_job_id,
        );
        setOpen(false);
        window.location.hash = buildClassroomPlayerHash(
          result.course_id,
          result.classroom_id,
        );
      } catch (caught) {
        if (!controller.signal.aborted) {
          const latestStatus = latestJobRef.current?.status;
          if (latestStatus === 'failed' || latestStatus === 'succeeded') {
            clearPendingClassroomGeneration(
              window.localStorage,
              activeCourseId,
              initialJob.edu_job_id,
            );
          }
          setError(
            caught instanceof Error
              ? caught.message
              : 'AI 课堂生成失败，请重试',
          );
        }
      } finally {
        if (
          activeJobIdRef.current === initialJob.edu_job_id &&
          abortRef.current === controller
        ) {
          activeJobIdRef.current = null;
        }
        if (abortRef.current === controller) {
          abortRef.current = null;
          setSubmitting(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    if (courseId && !activeJobIdRef.current) {
      const pending = readPendingClassroomGeneration(
        window.localStorage,
        courseId,
      );
      if (pending) {
        const controller = new AbortController();
        abortRef.current?.abort();
        abortRef.current = controller;
        void trackJob(pending.job, courseId, pending.topic, controller);
      }
    }

    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
      activeJobIdRef.current = null;
    };
  }, [courseId, trackJob]);

  const openModal = () => {
    if (!courseId) {
      message.warning('请先选择一门课程');
      return;
    }

    setError(null);
    setJob(null);
    setOpen(true);
  };

  const closeModal = () => {
    if (submitting) {
      return;
    }

    abortRef.current?.abort();
    abortRef.current = null;
    setOpen(false);
  };

  const submit = async () => {
    const requirement = topic.trim();
    if (!courseId || !requirement || submitting) {
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setSubmitting(true);
    setError(null);
    setJob(null);

    let initialJob: EduJob;
    try {
      initialJob = await generateClassroom(courseId, {
        requirement,
        enable_tts: true,
      });
      savePendingClassroomGeneration(window.localStorage, {
        courseId,
        topic: requirement,
        job: initialJob,
        savedAt: new Date().toISOString(),
      });
    } catch (caught) {
      if (!controller.signal.aborted) {
        setError(
          caught instanceof Error
            ? caught.message
            : 'AI 课堂生成失败，请重试',
        );
      }
      if (abortRef.current === controller) {
        abortRef.current = null;
        setSubmitting(false);
      }
      return;
    }

    if (controller.signal.aborted) {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setSubmitting(false);
      }
      return;
    }

    await trackJob(initialJob, courseId, requirement, controller);
  };

  const resume = async () => {
    if (
      !courseId ||
      !job ||
      (job.status !== 'queued' && job.status !== 'running') ||
      submitting
    ) {
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    await trackJob(job, courseId, topic.trim(), controller);
  };

  const canResume =
    Boolean(error) &&
    (job?.status === 'queued' || job?.status === 'running') &&
    !submitting;

  const progressStatus =
    job?.status === 'failed'
      ? 'exception'
      : job?.status === 'succeeded'
        ? 'success'
        : 'active';

  return (
    <>
      <section
        className="classroom-generation-entry"
        aria-label="AI 课堂生成"
      >
        <div className="classroom-generation-entry__icon" aria-hidden="true">
          <PlayCircleOutlined />
        </div>
        <div className="classroom-generation-entry__copy">
          <strong>AI 课堂</strong>
          <span>输入主题，自动生成可播放、可导出的课堂。</span>
        </div>
        <Tooltip title={courseId ? undefined : '请先选择一门课程'}>
          <span className="classroom-generation-entry__button-wrap">
            <Button
              className="classroom-generation-entry__button"
              type="primary"
              onClick={openModal}
              disabled={!courseId}
            >
              开始备课
            </Button>
          </span>
        </Tooltip>
      </section>

      <Modal
        title="生成 AI 课堂"
        open={open}
        onCancel={closeModal}
        footer={null}
        closable={!submitting}
        maskClosable={!submitting}
        destroyOnHidden={false}
      >
        <div className="classroom-generation-entry__modal-body">
          <Text type="secondary">
            输入本节课的主题和重点，系统会结合当前课程资料生成课件、配音并自动开始教学。
          </Text>
          <Input.TextArea
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            placeholder="例如：讲解冒泡排序的基本原理、执行过程和时间复杂度"
            rows={4}
            disabled={submitting}
            maxLength={500}
            showCount
            autoFocus
          />

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
                {job.message || '系统正在后台准备课堂，请稍候…'}
              </Text>
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
            <Button onClick={closeModal} disabled={submitting}>
              取消
            </Button>
            <Button
              type="primary"
              loading={submitting}
              disabled={!canResume && !topic.trim()}
              onClick={() => void (canResume ? resume() : submit())}
            >
              {submitting
                ? '正在生成课堂'
                : canResume
                  ? '恢复轮询'
                : error
                  ? '重新生成'
                  : '开始生成'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
