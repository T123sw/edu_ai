import React from 'react';
import { ArrowLeftOutlined, RightOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import type { GeneratedFile } from '../../store/teacher/useStore';
import type { QuizResponse } from '../../services/teacher/api';
import './QuizArtifactPreview.css';

type Props = {
  file: GeneratedFile;
  quiz: QuizResponse;
  questions: QuizResponse['questions'];
  totalCount: number;
  checkedCount: number;
  correctCount: number;
  accuracy: number;
  progressPercent: number;
  safeQuizIndex: number;
  currentQuestion?: QuizResponse['questions'][number];
  currentQuestionId: string;
  currentQuestionType: string;
  currentUserAnswer: string;
  currentHasChecked: boolean;
  currentIsCorrect: boolean;
  quizChecked: Record<string, boolean>;
  onBack: () => void;
  onToggleCollapsed: () => void;
  onReset: () => void;
  onCheckAll: () => void;
  onGoToIndex: (index: number) => void;
  onAnswerChange: (value: string, autoCheck?: boolean) => void;
  onSubmitCurrent: () => void;
};

function normalizeAnswer(value: string) {
  return String(value || '').trim().toLowerCase();
}

function extractChoiceKey(value: string) {
  const normalized = normalizeAnswer(value);
  const match = normalized.match(/^([a-d])[\.\s、\)]/i) || normalized.match(/^([a-d])$/i);
  return match ? match[1].toUpperCase() : '';
}

function isOptionCorrect(question: QuizResponse['questions'][number], option: string) {
  const optionKey = extractChoiceKey(option);
  const answerKey = extractChoiceKey(question.answer || '');
  if (optionKey && answerKey) {
    return optionKey === answerKey;
  }
  return normalizeAnswer(option) === normalizeAnswer(question.answer || '');
}

function typeLabel(type: string) {
  if (type === 'judge') return '判断题';
  if (type === 'choice') return '选择题';
  return '简答题';
}

function answerStatusClass({
  checked,
  selected,
  correct,
}: {
  checked: boolean;
  selected: boolean;
  correct: boolean;
}) {
  if (!checked) {
    return selected ? 'quiz-artifact-preview__option quiz-artifact-preview__option--selected' : 'quiz-artifact-preview__option';
  }
  if (selected && correct) {
    return 'quiz-artifact-preview__option quiz-artifact-preview__option--correct';
  }
  if (selected && !correct) {
    return 'quiz-artifact-preview__option quiz-artifact-preview__option--wrong';
  }
  if (!selected && correct) {
    return 'quiz-artifact-preview__option quiz-artifact-preview__option--answer';
  }
  return 'quiz-artifact-preview__option';
}

export default function QuizArtifactPreview({
  file,
  quiz,
  questions,
  totalCount,
  checkedCount,
  correctCount,
  accuracy,
  progressPercent,
  safeQuizIndex,
  currentQuestion,
  currentQuestionId,
  currentQuestionType,
  currentUserAnswer,
  currentHasChecked,
  currentIsCorrect,
  quizChecked,
  onBack,
  onToggleCollapsed,
  onReset,
  onCheckAll,
  onGoToIndex,
  onAnswerChange,
  onSubmitCurrent,
}: Props) {
  const isChoice = currentQuestionType === 'choice' && Array.isArray(currentQuestion?.options);
  const isJudge = currentQuestionType === 'judge';

  return (
    <div className="quiz-artifact-preview">
      <div className="quiz-artifact-preview__toolbar">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack} className="quiz-artifact-preview__back">
          返回
        </Button>
        <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作区" />
      </div>

      <div className="quiz-artifact-preview__scroll">
        <article className="quiz-artifact-preview__document">
          <header className="quiz-artifact-preview__head">
            <div className="quiz-artifact-preview__eyebrow">习题练习</div>
            <h2>{quiz.title || file.name}</h2>
          </header>

          <section className="quiz-artifact-preview__stats">
            <div className="quiz-artifact-preview__stats-row">
              <div className="quiz-artifact-preview__stat">
                <span>总题数</span>
                <strong>{totalCount}</strong>
              </div>
              <div className="quiz-artifact-preview__stat">
                <span>已判题</span>
                <strong>{checkedCount}</strong>
              </div>
              <div className="quiz-artifact-preview__stat">
                <span>答对</span>
                <strong>{correctCount}</strong>
              </div>
              <div className="quiz-artifact-preview__stat">
                <span>正确率</span>
                <strong>{accuracy}%</strong>
              </div>
            </div>
            <div className="quiz-artifact-preview__actions">
              <Button onClick={onReset}>重做本测验</Button>
              <Button onClick={onCheckAll}>一键查看答案</Button>
            </div>
          </section>

          {currentQuestion ? (
            <section className="quiz-artifact-preview__question-shell">
              <div className="quiz-artifact-preview__question-head">
                <div>
                  <div className="quiz-artifact-preview__question-index">第 {safeQuizIndex + 1} / {totalCount} 题</div>
                  <h3>{currentQuestion.stem}</h3>
                </div>
                <span className="quiz-artifact-preview__type-tag">{typeLabel(currentQuestionType)}</span>
              </div>

              <div className="quiz-artifact-preview__progress-track" aria-hidden="true">
                <div className="quiz-artifact-preview__progress-value" style={{ width: `${progressPercent}%` }} />
              </div>

              <div className="quiz-artifact-preview__body">
                {isChoice ? (
                  <div className="quiz-artifact-preview__options">
                    {(currentQuestion.options || []).map((option, index) => {
                      const selected = currentUserAnswer === option;
                      const correct = isOptionCorrect(currentQuestion, option);
                      return (
                        <button
                          key={`${currentQuestionId}_${index}`}
                          type="button"
                          className={answerStatusClass({ checked: currentHasChecked, selected, correct })}
                          onClick={() => onAnswerChange(option, true)}
                        >
                          <span className="quiz-artifact-preview__option-marker">{String.fromCharCode(65 + index)}</span>
                          <span className="quiz-artifact-preview__option-text">{option}</span>
                        </button>
                      );
                    })}
                  </div>
                ) : isJudge ? (
                  <div className="quiz-artifact-preview__judge-options">
                    {['正确', '错误'].map((value) => {
                      const selected = currentUserAnswer === value;
                      const correct = normalizeAnswer(value) === normalizeAnswer(currentQuestion.answer || '');
                      return (
                        <button
                          key={value}
                          type="button"
                          className={answerStatusClass({ checked: currentHasChecked, selected, correct })}
                          onClick={() => onAnswerChange(value, true)}
                        >
                          <span className="quiz-artifact-preview__option-text">{value}</span>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="quiz-artifact-preview__subjective">
                    <textarea
                      value={currentUserAnswer}
                      rows={6}
                      placeholder="请输入答案"
                      onChange={(e) => onAnswerChange(e.target.value, false)}
                    />
                    <div className="quiz-artifact-preview__subjective-actions">
                      <Button type="primary" onClick={onSubmitCurrent}>
                        提交并判题
                      </Button>
                    </div>
                  </div>
                )}

                {currentHasChecked ? (
                  <div className={`quiz-artifact-preview__feedback${currentIsCorrect ? ' quiz-artifact-preview__feedback--correct' : ' quiz-artifact-preview__feedback--wrong'}`}>
                    <div className="quiz-artifact-preview__feedback-title">
                      {currentIsCorrect ? '回答正确' : '回答错误'}
                    </div>
                    <div className="quiz-artifact-preview__feedback-item">
                      <span>正确答案</span>
                      <strong>{currentQuestion.answer || '-'}</strong>
                    </div>
                    <div className="quiz-artifact-preview__feedback-item">
                      <span>解析</span>
                      <p>{currentQuestion.explanation || '暂无解析'}</p>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="quiz-artifact-preview__footer">
                <Button disabled={safeQuizIndex <= 0} onClick={() => onGoToIndex(safeQuizIndex - 1)}>
                  上一题
                </Button>
                <div className="quiz-artifact-preview__pager">
                  {questions.map((item, index) => {
                    const itemId = String(item.id || index + 1);
                    const checked = !!quizChecked[itemId];
                    return (
                      <button
                        key={itemId}
                        type="button"
                        className={`quiz-artifact-preview__pager-item${index === safeQuizIndex ? ' quiz-artifact-preview__pager-item--active' : ''}${checked ? ' quiz-artifact-preview__pager-item--checked' : ''}`}
                        onClick={() => onGoToIndex(index)}
                      >
                        {index + 1}
                      </button>
                    );
                  })}
                </div>
                <Button disabled={safeQuizIndex >= totalCount - 1} onClick={() => onGoToIndex(safeQuizIndex + 1)}>
                  下一题
                </Button>
              </div>
            </section>
          ) : (
            <section className="quiz-artifact-preview__empty">
              暂无题目，请重新生成习题。
            </section>
          )}
        </article>
      </div>
    </div>
  );
}
