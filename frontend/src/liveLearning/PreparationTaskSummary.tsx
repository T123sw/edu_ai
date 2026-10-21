import { preparationFailure, type PreparationTask } from './preparationProgress';
import './preparationTaskSummary.css';

export function PreparationTaskSummary({ task }: { task: PreparationTask }) {
  if (task.status !== 'failed') return null;
  const failure = preparationFailure(task);
  return <div className="prep-task-summary">
    <div className="prep-task-error"><strong>{failure.title}</strong><p>{failure.reason}</p><p>{failure.next_step}</p></div>
  </div>;
}
