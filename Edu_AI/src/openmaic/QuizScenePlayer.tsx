import { useEffect, useMemo, useState } from 'react';
import type {
  ClassroomQuizQuestion,
  QuizClassroomContent,
} from '../stitch/api/types';
import {
  clearQuizDraft,
  gradeQuizQuestions,
  quizStorageKey,
  readQuizDraft,
  writeQuizDraft,
  type QuizAnswer,
  type QuizAnswers,
  type QuizQuestionStatus,
} from './quizScene';
import { SceneActionPlayback } from './SceneActionPlayback';
import type { PlaybackMode } from './playbackEngine';
import type { PlaybackRuntimeHandle } from './pagePlaybackController';

export interface QuizScenePlayerProps {
  courseId: string;
  classroomId: string;
  sceneId: string;
  title?: string;
  content: QuizClassroomContent;
  actions?: Array<Record<string, unknown>>;
  autoPlay?: boolean;
  onComplete?: () => void;
  onModeChange?: (mode: PlaybackMode) => void;
  onRuntimeReady?: (runtime: PlaybackRuntimeHandle | null) => void;
}

export function QuizScenePlayer({
  courseId,
  classroomId,
  sceneId,
  title,
  content,
  actions,
  autoPlay,
  onComplete,
  onModeChange,
  onRuntimeReady,
}: QuizScenePlayerProps) {
  const storageKey = useMemo(
    () => quizStorageKey(courseId, classroomId, sceneId),
    [classroomId, courseId, sceneId],
  );
  const initialDraft = useMemo(
    () =>
      typeof window === 'undefined'
        ? { answers: {}, submitted: false }
        : readQuizDraft(window.localStorage, storageKey),
    [storageKey],
  );
  const [answers, setAnswers] = useState<QuizAnswers>(initialDraft.answers);
  const [submitted, setSubmitted] = useState(initialDraft.submitted);
  const grade = useMemo(
    () =>
      submitted ? gradeQuizQuestions(content.questions, answers) : undefined,
    [answers, content.questions, submitted],
  );
  const resultByQuestion = useMemo(
    () =>
      new Map(
        grade?.results.map((result) => [result.questionId, result]) ?? [],
      ),
    [grade],
  );

  useEffect(() => {
    writeQuizDraft(window.localStorage, storageKey, { answers, submitted });
  }, [answers, storageKey, submitted]);

  const updateAnswer = (questionId: string, answer: QuizAnswer) => {
    setAnswers((current) => ({ ...current, [questionId]: answer }));
    setSubmitted(false);
  };
  const reset = () => {
    clearQuizDraft(window.localStorage, storageKey);
    setAnswers({});
    setSubmitted(false);
  };

  if (!content.questions.length) {
    return (
      <div className="flex h-full items-center justify-center bg-(--surface-subtle) text-sm text-(--muted-text)">
        该测验没有题目。
      </div>
    );
  }

  return (
    <SceneActionPlayback
      sceneId={sceneId}
      actions={actions}
      autoPlay={autoPlay}
      onComplete={onComplete}
      onModeChange={onModeChange}
      onRuntimeReady={onRuntimeReady}
    >
      <section className="h-full overflow-y-auto bg-[#f7f9fc] px-8 py-6">
        <header className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-(--accent-strong)">
              课堂测验
            </p>
            <h3 className="mt-1 text-xl font-black text-(--app-text)">
              {title || '知识检验'}
            </h3>
            <p className="mt-1 text-sm text-(--muted-text)">
              答案会自动保存，刷新页面后仍可继续。
            </p>
          </div>
          {grade ? (
            <div className="rounded-2xl bg-blue-50 px-5 py-3 text-center text-blue-800">
              <p className="text-xs font-semibold">客观题得分</p>
              <p className="mt-1 text-lg font-black">
                {grade.objectiveEarned}/{grade.objectivePossible}
              </p>
            </div>
          ) : null}
        </header>

        <div className="space-y-4">
          {content.questions.map((question, index) => (
            <QuestionCard
              key={question.id}
              index={index}
              question={question}
              answer={answers[question.id]}
              submitted={submitted}
              status={resultByQuestion.get(question.id)?.status}
              onChange={(answer) => updateAnswer(question.id, answer)}
            />
          ))}
        </div>

        <div className="sticky bottom-0 mt-5 flex justify-end gap-3 border-t border-slate-200 bg-[#f7f9fc]/95 py-4 backdrop-blur">
          <button
            type="button"
            onClick={reset}
            className="rounded-full border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700"
          >
            重新作答
          </button>
          <button
            type="button"
            onClick={() => setSubmitted(true)}
            className="rounded-full bg-(--accent-strong) px-6 py-2.5 text-sm font-semibold text-white shadow-sm"
          >
            提交并查看解析
          </button>
        </div>
      </section>
    </SceneActionPlayback>
  );
}

function QuestionCard({
  index,
  question,
  answer,
  submitted,
  status,
  onChange,
}: {
  index: number;
  question: ClassroomQuizQuestion;
  answer: QuizAnswer | undefined;
  submitted: boolean;
  status: QuizQuestionStatus | undefined;
  onChange: (answer: QuizAnswer) => void;
}) {
  const selectedValues = Array.isArray(answer) ? answer : [];
  const statusText = getStatusText(status);

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-7 min-w-7 items-center justify-center rounded-full bg-blue-50 text-sm font-bold text-blue-700">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="font-semibold leading-7 text-slate-900">
              {question.question}
            </p>
            <span className="text-xs text-slate-500">
              {question.points ?? 1} 分
            </span>
          </div>

          {question.type === 'single' ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {(question.options ?? []).map((option) => (
                <label
                  key={option.value}
                  className="flex cursor-pointer items-start gap-2 rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-700 hover:border-blue-300"
                >
                  <input
                    type="radio"
                    name={question.id}
                    value={option.value}
                    checked={answer === option.value}
                    onChange={() => onChange(option.value)}
                    className="mt-0.5"
                  />
                  <span>
                    <strong>{option.value}.</strong> {option.label}
                  </span>
                </label>
              ))}
            </div>
          ) : question.type === 'multiple' ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {(question.options ?? []).map((option) => (
                <label
                  key={option.value}
                  className="flex cursor-pointer items-start gap-2 rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-700 hover:border-blue-300"
                >
                  <input
                    type="checkbox"
                    value={option.value}
                    checked={selectedValues.includes(option.value)}
                    onChange={(event) =>
                      onChange(
                        event.target.checked
                          ? [...selectedValues, option.value]
                          : selectedValues.filter(
                              (value) => value !== option.value,
                            ),
                      )
                    }
                    className="mt-0.5"
                  />
                  <span>
                    <strong>{option.value}.</strong> {option.label}
                  </span>
                </label>
              ))}
            </div>
          ) : question.type === 'short_answer' ? (
            <textarea
              value={typeof answer === 'string' ? answer : ''}
              onChange={(event) => onChange(event.target.value)}
              placeholder="在这里输入你的答案"
              className="mt-3 min-h-24 w-full resize-y rounded-xl border border-slate-200 p-3 text-sm outline-none focus:border-blue-400"
            />
          ) : (
            <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-700">
              当前播放器暂不支持题型 “{question.type}”。
            </p>
          )}

          {submitted ? (
            <div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm">
              {statusText ? (
                <p className={`font-semibold ${statusText.className}`}>
                  {statusText.label}
                </p>
              ) : null}
              {question.answer?.length ? (
                <p className="mt-1 text-slate-700">
                  正确答案：{question.answer.join('、')}
                </p>
              ) : null}
              {question.commentPrompt ? (
                <p className="mt-2 whitespace-pre-wrap text-slate-600">
                  自评标准：{question.commentPrompt}
                </p>
              ) : null}
              {question.analysis ? (
                <p className="mt-2 whitespace-pre-wrap text-slate-600">
                  解析：{question.analysis}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function getStatusText(
  status: QuizQuestionStatus | undefined,
): { label: string; className: string } | undefined {
  switch (status) {
    case 'correct':
      return { label: '回答正确', className: 'text-emerald-700' };
    case 'incorrect':
      return { label: '回答有误', className: 'text-rose-700' };
    case 'self_review':
      return { label: '请结合标准自行检查', className: 'text-blue-700' };
    case 'unsupported':
      return { label: '该题型暂不自动判分', className: 'text-amber-700' };
    default:
      return undefined;
  }
}
