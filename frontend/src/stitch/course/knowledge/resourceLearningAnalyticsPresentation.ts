export function resourceLearningQueueLabel(queue: string): string {
  return {
    not_started: '尚未开始',
    coverage_pending: '讲解与习题均待推进',
    coverage_ready_questions_pending: '讲解已达标，习题待完成',
    questions_ready_coverage_pending: '习题已完成，讲解待学习',
    completed: '已完成',
  }[queue] ?? queue;
}
