import { useEffect, useState } from 'react';

import { getResourceLearningAnalytics } from '../../api/resourceLearning';
import type { ResourceLearningAnalytics as AnalyticsData } from '../../api/types';
import { resourceLearningQueueLabel } from './resourceLearningAnalyticsPresentation';

export function ResourceLearningAnalytics({
  courseId,
  resourceId,
  version,
}: {
  courseId: string;
  resourceId: string;
  version: number;
}) {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    getResourceLearningAnalytics(courseId, resourceId, version)
      .then((data) => {
        if (!cancelled) setAnalytics(data);
      })
      .catch((reason) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : '学习分析加载失败');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, resourceId, version]);

  if (error) return <p className="resource-learning-analytics__error">{error}</p>;
  if (!analytics) return <p className="resource-learning-analytics__loading">正在加载学习分析…</p>;

  return (
    <section className="resource-learning-analytics" aria-label="课堂资源学习分析">
      <div className="resource-learning-analytics__summary">
        <Metric label="课程学生" value={analytics.enrolled_student_count} />
        <Metric label="已开始" value={analytics.started_student_count} />
        <Metric label="已完成" value={analytics.completed_student_count} />
        <Metric label="平均讲解完整度" value={`${Math.round(analytics.average_explanation_coverage_percent)}%`} />
        <Metric label="全部习题已作答" value={analytics.all_questions_answered_student_count} />
        <Metric label="演示访问人数" value={analytics.demo_view_student_count} />
      </div>

      <div className="resource-learning-analytics__queues">
        {Object.entries(analytics.queues).map(([queue, count]) => (
          <span key={queue}>{resourceLearningQueueLabel(queue)} <strong>{count}</strong></span>
        ))}
      </div>

      {analytics.question_analytics.length ? (
        <div className="resource-learning-analytics__questions">
          <strong>逐题分析</strong>
          {analytics.question_analytics.map((question) => (
            <p key={question.question_id}>
              {question.question_id}：作答 {question.response_rate.numerator}/{question.response_rate.denominator}，
              首次正确 {Math.round(question.first_correct_rate.percent)}%，
              最终正确 {Math.round(question.latest_correct_rate.percent)}%
            </p>
          ))}
        </div>
      ) : null}

      {analytics.knowledge_point_errors.length ? (
        <div className="resource-learning-analytics__knowledge">
          <strong>知识点错误</strong>
          {analytics.knowledge_point_errors.map((item) => (
            <span key={item.knowledge_point_id}>
              {item.knowledge_point_id} · {item.incorrect_student_count} 人
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <span><small>{label}</small><strong>{value}</strong></span>;
}
