import type { ResourceLearningProgress as ResourceLearningProgressData } from '../../api/types';
import { resourceLearningLabels } from './resourceLearningPresentation';
import './resourceLearning.css';

export function ResourceLearningProgress({
  progress,
  compact = false,
  syncState,
}: {
  progress: ResourceLearningProgressData | null | undefined;
  compact?: boolean;
  syncState?: 'idle' | 'syncing' | 'synced' | 'failed';
}) {
  const labels = progress
    ? resourceLearningLabels(progress)
    : {
        coverage: '讲解完整度 0%',
        questions: '习题进度 0/—',
        status: '尚未开始',
      };
  const completedAt = progress?.completed_at
    ? new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }).format(new Date(progress.completed_at))
    : null;

  return (
    <div className={`resource-learning-progress${compact ? ' resource-learning-progress--compact' : ''}`}>
      <span>{labels.coverage}</span>
      <span>{labels.questions}</span>
      <strong>{labels.status}</strong>
      {syncState ? (
        <small aria-live="polite">
          {syncState === 'syncing'
            ? '同步中'
            : syncState === 'failed'
              ? '待重试'
              : syncState === 'synced'
                ? '已同步'
                : '准备记录'}
        </small>
      ) : null}
      {!compact && completedAt ? <small>首次完成于 {completedAt}</small> : null}
    </div>
  );
}
