import type { AssessmentRatio } from "../api/types";

export function formatAssessmentRatio(value: AssessmentRatio): string {
  return `${Math.round(value.rate * 100)}%（${value.numerator}/${value.denominator}）`;
}

export function getAssessmentQueueLabel(status: string): string {
  return {
    not_started: "未开始",
    in_progress: "作答中",
    pending_review: "待教师复核",
    retry_available: "可重做未通过",
    attempts_exhausted: "次数用尽未通过",
    passed: "已通过",
    mastered: "掌握良好",
  }[status] ?? status;
}
