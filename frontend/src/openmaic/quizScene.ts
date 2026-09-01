import type { ClassroomQuizQuestion } from '../stitch/api/types';

export type QuizAnswer = string | string[];
export type QuizAnswers = Record<string, QuizAnswer>;
export type QuizQuestionStatus =
  | 'correct'
  | 'incorrect'
  | 'self_review'
  | 'unsupported';

export interface QuizQuestionResult {
  questionId: string;
  status: QuizQuestionStatus;
  earned: number;
  possible: number;
}

export interface QuizGradeSummary {
  results: QuizQuestionResult[];
  objectiveEarned: number;
  objectivePossible: number;
}

export interface QuizDraft {
  answers: QuizAnswers;
  submitted: boolean;
}

export interface ResourceQuestionSubmission {
  answers: QuizAnswers;
}

export function buildResourceQuestionSubmission(
  questions: ClassroomQuizQuestion[],
  answers: QuizAnswers,
): ResourceQuestionSubmission {
  const submittedAnswers = Object.fromEntries(
    questions.flatMap((question) => {
      const answer = answers[question.id];
      if (typeof answer === 'string') {
        const normalized = answer.trim();
        return normalized ? [[question.id, normalized] as const] : [];
      }
      if (Array.isArray(answer)) {
        const normalized = [...new Set(answer.map((value) => value.trim()).filter(Boolean))];
        return normalized.length ? [[question.id, normalized] as const] : [];
      }
      return [];
    }),
  );

  const hasMissingRequiredAnswer = questions.some(
    (question) =>
      question.required !== false && submittedAnswers[question.id] === undefined,
  );
  if (hasMissingRequiredAnswer) {
    throw new Error('请完成所有必答题后再提交');
  }
  return { answers: submittedAnswers };
}

export interface QuizStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): unknown;
  removeItem(key: string): unknown;
}

const EMPTY_DRAFT: QuizDraft = { answers: {}, submitted: false };

export function gradeQuizQuestions(
  questions: ClassroomQuizQuestion[],
  answers: QuizAnswers,
): QuizGradeSummary {
  let objectiveEarned = 0;
  let objectivePossible = 0;
  const results = questions.map<QuizQuestionResult>((question) => {
    const possible = Math.max(0, question.points ?? 1);
    if (question.type === 'short_answer') {
      return {
        questionId: question.id,
        status: 'self_review',
        earned: 0,
        possible,
      };
    }
    if (
      (question.type !== 'single' && question.type !== 'multiple') ||
      !question.answer?.length
    ) {
      return {
        questionId: question.id,
        status: 'unsupported',
        earned: 0,
        possible,
      };
    }

    objectivePossible += possible;
    const expected = normalizedValues(question.answer);
    const supplied =
      question.type === 'single'
        ? normalizedValues(
            typeof answers[question.id] === 'string'
              ? [answers[question.id] as string]
              : [],
          )
        : normalizedValues(
            Array.isArray(answers[question.id])
              ? (answers[question.id] as string[])
              : [],
          );
    const correct =
      expected.length === supplied.length &&
      expected.every((value, index) => value === supplied[index]);
    if (correct) objectiveEarned += possible;
    return {
      questionId: question.id,
      status: correct ? 'correct' : 'incorrect',
      earned: correct ? possible : 0,
      possible,
    };
  });

  return { results, objectiveEarned, objectivePossible };
}

export function quizStorageKey(
  courseId: string,
  classroomId: string,
  sceneId: string,
): string {
  return [
    'edu-ai:classroom-quiz:v1',
    encodeURIComponent(courseId),
    encodeURIComponent(classroomId),
    encodeURIComponent(sceneId),
  ].join(':');
}

export function readQuizDraft(storage: QuizStorage, key: string): QuizDraft {
  try {
    const raw = storage.getItem(key);
    if (!raw) return { ...EMPTY_DRAFT, answers: {} };
    const parsed: unknown = JSON.parse(raw);
    if (!isQuizDraft(parsed)) {
      storage.removeItem(key);
      return { ...EMPTY_DRAFT, answers: {} };
    }
    return parsed;
  } catch {
    try {
      storage.removeItem(key);
    } catch {
      // Storage availability must never block classroom playback.
    }
    return { ...EMPTY_DRAFT, answers: {} };
  }
}

export function writeQuizDraft(
  storage: QuizStorage,
  key: string,
  draft: QuizDraft,
): void {
  try {
    storage.setItem(key, JSON.stringify(draft));
  } catch {
    // Private browsing and storage quotas are safe degradation paths.
  }
}

export function clearQuizDraft(storage: QuizStorage, key: string): void {
  try {
    storage.removeItem(key);
  } catch {
    // Storage availability must never block classroom playback.
  }
}

function normalizedValues(values: string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))].sort();
}

function isQuizDraft(value: unknown): value is QuizDraft {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<QuizDraft>;
  if (
    typeof candidate.submitted !== 'boolean' ||
    !candidate.answers ||
    typeof candidate.answers !== 'object' ||
    Array.isArray(candidate.answers)
  ) {
    return false;
  }
  return Object.values(candidate.answers).every(
    (answer) =>
      typeof answer === 'string' ||
      (Array.isArray(answer) &&
        answer.every((item) => typeof item === 'string')),
  );
}
