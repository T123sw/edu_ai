import React, { useMemo } from 'react';
import { ArrowLeftOutlined, RightOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import type { GeneratedFile } from '../../store/teacher/useStore';
import MarkdownPreview from '../shared/MarkdownPreview';
import './LessonPlanArtifactPreview.css';

type LessonPlanStep = {
  step: string;
  duration: string;
  goal: string;
  teacherActivities: string[];
  studentActivities: string[];
  assessment: string;
  content: string;
};

type NormalizedLessonPlan = {
  kind: 'outline' | 'final' | 'markdown' | 'generic';
  title: string;
  markdown: string;
  basicInfo: {
    audience: string;
    duration: string;
    lessonType: string;
  };
  objectives: string[];
  keyPoints: string[];
  hardPoints: string[];
  breakthroughStrategy: string;
  process: LessonPlanStep[];
  teachingMethods: string[];
  teachingAids: string[];
  boardPlan: string[];
  assessmentMethod: string;
  homework: string;
};

type Props = {
  file: GeneratedFile;
  kind: string;
  onBack: () => void;
  onToggleCollapsed: () => void;
  onContinueFromOutline: () => void;
};

function clean(value: unknown): string {
  return String(value ?? '').trim();
}

function tryParseJson(value: string): unknown {
  const text = clean(value);
  if (!text || !/^[\[{]/.test(text)) {
    return value;
  }
  try {
    return JSON.parse(text);
  } catch {
    return value;
  }
}

function asRecord(value: unknown): Record<string, any> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, any>) : {};
}

function readText(record: Record<string, any>, keys: string[]): string {
  for (const key of keys) {
    const value = clean(record[key]);
    if (value) {
      return value;
    }
  }
  return '';
}

function toTextList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .flatMap((item) => {
        if (item && typeof item === 'object') {
          const record = item as Record<string, unknown>;
          return clean(record.text || record.content || record.title || record.name || item);
        }
        return clean(item);
      })
      .filter(Boolean);
  }
  const text = clean(value);
  if (!text) {
    return [];
  }
  return text
    .split(/\n+/)
    .map((item) => clean(item.replace(/^[-*]\s*/, '')))
    .filter(Boolean);
}

function normalizeStep(item: unknown, index: number): LessonPlanStep {
  const record = asRecord(item);
  return {
    step: readText(record, ['step', 'title', 'name', 'stage']) || `环节 ${index + 1}`,
    duration: readText(record, ['duration', 'time', 'time_allocation']),
    goal: readText(record, ['goal', 'objective', 'target']),
    teacherActivities: [
      ...toTextList(record.teacherActivities),
      ...toTextList(record.teacher_activities),
      ...toTextList(record.teacher_actions),
    ],
    studentActivities: [
      ...toTextList(record.studentActivities),
      ...toTextList(record.student_activities),
      ...toTextList(record.student_actions),
    ],
    assessment: readText(record, ['assessment', 'evaluation', 'check']),
    content: readText(record, ['content', 'description', 'summary']),
  };
}

function normalizeLessonPlanContent(content: unknown, kind: string, fallbackTitle: string): NormalizedLessonPlan {
  const parsed = typeof content === 'string' ? tryParseJson(content) : content;
  const normalizedKind = clean(kind);

  if (typeof parsed === 'string') {
    return {
      kind: 'markdown',
      title: fallbackTitle,
      markdown: parsed,
      basicInfo: { audience: '', duration: '', lessonType: '' },
      objectives: [],
      keyPoints: [],
      hardPoints: [],
      breakthroughStrategy: '',
      process: [],
      teachingMethods: [],
      teachingAids: [],
      boardPlan: [],
      assessmentMethod: '',
      homework: '',
    };
  }

  const record = asRecord(parsed);
  const basicInfo = asRecord(record.basic_info || record.basicInfo);
  const keyAndHardPoints = asRecord(record.key_and_hard_points || record.keyAndHardPoints);
  const teachingSupport = asRecord(record.teaching_support || record.teachingSupport);
  const isOutline =
    normalizedKind === 'outline'
    || Boolean(record.basic_info)
    || Boolean(record.lesson_flow)
    || Boolean(record.teaching_objectives);
  const rawProcess =
    record.process
    || record.lesson_flow
    || record.teachingProcess
    || record.teaching_process
    || record.steps
    || [];

  return {
    kind: isOutline ? 'outline' : 'final',
    title: readText(record, ['title', 'topic', 'lesson_title']) || readText(basicInfo, ['topic', 'title']) || fallbackTitle,
    markdown: '',
    basicInfo: {
      audience: readText(record, ['audience', 'targetStudents']) || readText(basicInfo, ['audience', 'target_students']),
      duration: readText(record, ['duration', 'lessonDuration']) || readText(basicInfo, ['duration', 'lesson_duration']),
      lessonType: readText(record, ['lessonType', 'lesson_type', 'classType']) || readText(basicInfo, ['lesson_type', 'class_type']),
    },
    objectives: [
      ...toTextList(record.objectives),
      ...toTextList(record.teaching_objectives),
      ...toTextList(record.teachingObjectives),
    ],
    keyPoints: [
      ...toTextList(record.keyPoints),
      ...toTextList(record.key_points),
      ...toTextList(keyAndHardPoints.key_points),
    ],
    hardPoints: [
      ...toTextList(record.hardPoints),
      ...toTextList(record.hard_points),
      ...toTextList(keyAndHardPoints.hard_points),
    ],
    breakthroughStrategy:
      readText(record, ['breakthroughStrategy', 'breakthrough_strategy'])
      || readText(keyAndHardPoints, ['breakthrough_strategy', 'strategy']),
    process: Array.isArray(rawProcess) ? rawProcess.map((item, index) => normalizeStep(item, index)) : [],
    teachingMethods: [
      ...toTextList(record.teachingMethods),
      ...toTextList(record.teaching_methods),
      ...toTextList(teachingSupport.teaching_methods),
    ],
    teachingAids: [
      ...toTextList(record.teachingAids),
      ...toTextList(record.teaching_aids),
      ...toTextList(teachingSupport.teaching_aids),
    ],
    boardPlan: [
      ...toTextList(record.boardPlan),
      ...toTextList(record.board_plan),
      ...toTextList(record.blackboardDesign),
      ...toTextList(teachingSupport.board_plan),
    ],
    assessmentMethod:
      readText(record, ['assessmentMethod', 'assessment_method'])
      || readText(teachingSupport, ['assessment_method', 'assessment']),
    homework:
      readText(record, ['homework', 'afterClassTask', 'after_class_task'])
      || readText(teachingSupport, ['homework_preview', 'homework']),
  };
}

function TextList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <ul className="lesson-plan-artifact-preview__list">
      {items.map((item, index) => (
        <li key={`${index}-${item.slice(0, 18)}`}>{item}</li>
      ))}
    </ul>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="lesson-plan-artifact-preview__section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function ParagraphBlock({ text }: { text: string }) {
  if (!text) {
    return null;
  }
  return <p className="lesson-plan-artifact-preview__paragraph">{text}</p>;
}

function LessonStepView({ step, index }: { step: LessonPlanStep; index: number }) {
  const hasStructuredDetails =
    step.goal
    || step.teacherActivities.length > 0
    || step.studentActivities.length > 0
    || step.assessment;

  return (
    <section className="lesson-plan-artifact-preview__step">
      <div className="lesson-plan-artifact-preview__step-index">{index + 1}</div>
      <div className="lesson-plan-artifact-preview__step-body">
        <div className="lesson-plan-artifact-preview__step-head">
          <h4>{step.step}</h4>
          {step.duration ? <span>{step.duration}</span> : null}
        </div>
        {step.content ? <ParagraphBlock text={step.content} /> : null}
        {hasStructuredDetails ? (
          <dl className="lesson-plan-artifact-preview__step-details">
            {step.goal ? (
              <>
                <dt>目标</dt>
                <dd>{step.goal}</dd>
              </>
            ) : null}
            {step.teacherActivities.length > 0 ? (
              <>
                <dt>教师活动</dt>
                <dd>{step.teacherActivities.join('；')}</dd>
              </>
            ) : null}
            {step.studentActivities.length > 0 ? (
              <>
                <dt>学生活动</dt>
                <dd>{step.studentActivities.join('；')}</dd>
              </>
            ) : null}
            {step.assessment ? (
              <>
                <dt>评价</dt>
                <dd>{step.assessment}</dd>
              </>
            ) : null}
          </dl>
        ) : null}
      </div>
    </section>
  );
}

export default function LessonPlanArtifactPreview({
  file,
  kind,
  onBack,
  onToggleCollapsed,
  onContinueFromOutline,
}: Props) {
  const plan = useMemo(() => normalizeLessonPlanContent(file.content, kind, file.name), [file.content, file.name, kind]);
  const isOutline = plan.kind === 'outline';
  const metaItems = [
    plan.basicInfo.audience ? `适用对象：${plan.basicInfo.audience}` : '',
    plan.basicInfo.duration ? `课时：${plan.basicInfo.duration}` : '',
    plan.basicInfo.lessonType ? `课型：${plan.basicInfo.lessonType}` : '',
  ].filter(Boolean);
  const supportItems = [
    plan.teachingMethods.length > 0 ? ['教学方法', plan.teachingMethods.join('、')] : null,
    plan.teachingAids.length > 0 ? ['教学资源', plan.teachingAids.join('、')] : null,
    plan.boardPlan.length > 0 ? ['板书建议', plan.boardPlan.join('、')] : null,
    plan.assessmentMethod ? ['课堂评价', plan.assessmentMethod] : null,
  ].filter(Boolean) as string[][];

  return (
    <div className="lesson-plan-artifact-preview">
      <div className="lesson-plan-artifact-preview__toolbar">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack} className="lesson-plan-artifact-preview__back">
          返回
        </Button>
        <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作区" />
      </div>

      <div className="lesson-plan-artifact-preview__scroll">
        {plan.kind === 'markdown' ? (
          <div className="lesson-plan-artifact-preview__markdown">
            <MarkdownPreview content={plan.markdown} />
          </div>
        ) : (
          <article className="lesson-plan-artifact-preview__document">
            <header className="lesson-plan-artifact-preview__head">
              <div className="lesson-plan-artifact-preview__eyebrow">{isOutline ? '教案大纲' : '教案正文'}</div>
              <h2>{plan.title || file.name}</h2>
              {metaItems.length > 0 ? (
                <div className="lesson-plan-artifact-preview__meta">
                  {metaItems.map((item) => (
                    <span key={item}>{item}</span>
                  ))}
                </div>
              ) : null}
            </header>

            {isOutline ? (
              <div className="lesson-plan-artifact-preview__notice">
                <strong>当前预览的是教案大纲</strong>
                <span>确认教学目标、重难点和课堂流程后，可以继续生成完整教案正文。</span>
              </div>
            ) : null}

            {plan.objectives.length > 0 ? (
              <Section title="本课目标">
                <TextList items={plan.objectives} />
              </Section>
            ) : null}

            {(plan.keyPoints.length > 0 || plan.hardPoints.length > 0 || plan.breakthroughStrategy) ? (
              <Section title="重点与难点">
                <div className="lesson-plan-artifact-preview__focus-grid">
                  {plan.keyPoints.length > 0 ? (
                    <div>
                      <h4>教学重点</h4>
                      <TextList items={plan.keyPoints} />
                    </div>
                  ) : null}
                  {plan.hardPoints.length > 0 ? (
                    <div>
                      <h4>教学难点</h4>
                      <TextList items={plan.hardPoints} />
                    </div>
                  ) : null}
                </div>
                {plan.breakthroughStrategy ? (
                  <div className="lesson-plan-artifact-preview__strategy">
                    <span>突破策略</span>
                    <ParagraphBlock text={plan.breakthroughStrategy} />
                  </div>
                ) : null}
              </Section>
            ) : null}

            {plan.process.length > 0 ? (
              <Section title="课堂过程">
                <div className="lesson-plan-artifact-preview__timeline">
                  {plan.process.map((step, index) => (
                    <LessonStepView key={`${index}-${step.step}`} step={step} index={index} />
                  ))}
                </div>
              </Section>
            ) : null}

            {supportItems.length > 0 ? (
              <Section title="教学支持">
                <dl className="lesson-plan-artifact-preview__support">
                  {supportItems.map(([label, value]) => (
                    <React.Fragment key={label}>
                      <dt>{label}</dt>
                      <dd>{value}</dd>
                    </React.Fragment>
                  ))}
                </dl>
              </Section>
            ) : null}

            {plan.homework ? (
              <Section title="课后安排">
                <ParagraphBlock text={plan.homework} />
              </Section>
            ) : null}
          </article>
        )}
      </div>

      {isOutline ? (
        <div className="lesson-plan-artifact-preview__floating-action">
          <Button type="primary" onClick={onContinueFromOutline}>
            继续生成教案
          </Button>
        </div>
      ) : null}
    </div>
  );
}
