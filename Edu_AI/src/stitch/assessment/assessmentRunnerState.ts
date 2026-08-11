import type { AssessmentAttempt, AssessmentFeedback } from "../api/types";

export type AssessmentRunnerState =
  | "ready"
  | "in_progress"
  | "pending_review"
  | "retry"
  | "passed"
  | "exhausted"
  | "revealed";

export function deriveAssessmentRunnerState(
  attempts: Array<Pick<AssessmentAttempt, "status" | "result">>,
  feedback: Pick<AssessmentFeedback, "attempts_used" | "max_attempts" | "result" | "answers_revealed_at"> | null,
): AssessmentRunnerState {
  if (feedback?.answers_revealed_at) return "revealed";
  const latest = attempts.at(-1);
  if (latest?.status === "in_progress") return "in_progress";
  if (latest?.status === "pending_review" || feedback?.result === "pending_review") return "pending_review";
  if (feedback?.result === "passed" || feedback?.result === "mastered") return "passed";
  if (feedback && feedback.attempts_used >= feedback.max_attempts) return "exhausted";
  if (latest?.result === "needs_retry" || feedback?.result === "needs_retry") return "retry";
  return "ready";
}
