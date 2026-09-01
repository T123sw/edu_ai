import React, { useMemo } from 'react';
import { ArrowLeftOutlined, MessageOutlined, RightOutlined } from '@ant-design/icons';
import { Button, Space } from 'antd';
import type { GeneratedFile } from '../../store/teacher/useStore';
import MarkdownPreview from '../shared/MarkdownPreview';
import './ReportArtifactPreview.css';

type ReportPreviewMode = 'body' | 'outline-solid';

type Props = {
  file: GeneratedFile;
  outlineContent?: unknown;
  previewMode: ReportPreviewMode;
  canToggleOutline: boolean;
  canAddToChat: boolean;
  onPreviewModeChange: (mode: ReportPreviewMode) => void;
  onBack: () => void;
  onToggleCollapsed: () => void;
  onAddToChat: () => void;
  onGenerateFromOutline: () => void;
};

type ReportSection = {
  title: string;
  content?: string;
  points: string[];
  subsections: ReportSection[];
};

type OutlineChapter = {
  title: string;
  sections: ReportSection[];
};

type RenderableReport =
  | { kind: 'markdown'; markdown: string }
  | {
      kind: 'outline-solid';
      title: string;
      chapters: OutlineChapter[];
    }
  | {
      kind: 'report';
      title: string;
      summary: string;
      introduction: string;
      sections: ReportSection[];
      keyFindings: string[];
      conclusions: string;
      recommendations: string[];
    }
  | { kind: 'generic'; title: string; sections: ReportSection[] };

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

function toTextList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .flatMap((item) => {
        if (item && typeof item === 'object') {
          const record = item as Record<string, unknown>;
          return clean(record.text || record.content || record.title || item);
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

function readText(record: Record<string, any>, keys: string[]): string {
  for (const key of keys) {
    const value = clean(record[key]);
    if (value) {
      return value;
    }
  }
  return '';
}

function getMarkdownFromRecord(record: Record<string, any>): string {
  const directMarkdown = readText(record, ['markdown', 'final_markdown', 'report_content', 'content_markdown', 'report']);
  if (directMarkdown) {
    return directMarkdown;
  }
  for (const key of ['content', 'body', 'text']) {
    if (typeof record[key] === 'string') {
      const value = clean(record[key]);
      if (value && !/^[\[{]/.test(value)) {
        return value;
      }
    }
  }
  return '';
}

function normalizeSection(item: unknown, index: number): ReportSection {
  const record = asRecord(item);
  const title = readText(record, ['title', 'section_title', 'chapter_title', 'heading', 'name']) || `第 ${index + 1} 部分`;
  const content = readText(record, ['content', 'body', 'summary', 'description']);
  const points = [
    ...toTextList(record.points),
    ...toTextList(record.key_points),
    ...toTextList(record.bullets),
    ...toTextList(record.items),
  ];
  const rawSubsections = Array.isArray(record.subsections)
    ? record.subsections
    : Array.isArray(record.sections)
      ? record.sections
      : [];

  return {
    title,
    content,
    points,
    subsections: rawSubsections.map((section, subIndex) => normalizeSection(section, subIndex)),
  };
}

function normalizeOutline(value: unknown, fallbackTitle: string): RenderableReport {
  const rawChapters = Array.isArray(value)
    ? value
    : Array.isArray(asRecord(value).outline)
      ? asRecord(value).outline
      : Array.isArray(asRecord(value).chapters)
        ? asRecord(value).chapters
        : [];

  const chapters = rawChapters.map((chapter, index) => {
    const record = asRecord(chapter);
    const title = readText(record, ['chapter_title', 'title', 'heading', 'name']) || `第 ${index + 1} 章`;
    const rawSections = Array.isArray(record.sections) ? record.sections : [];
    const sections = rawSections.length > 0 ? rawSections.map((section, sectionIndex) => normalizeSection(section, sectionIndex)) : [];
    return { title, sections };
  });

  return {
    kind: 'outline-solid',
    title: fallbackTitle,
    chapters,
  };
}

function outlineFromMarkdown(markdown: string, fallbackTitle: string): RenderableReport {
  const lines = String(markdown || '').split(/\r?\n/);
  let title = fallbackTitle;
  const chapters: OutlineChapter[] = [];
  let currentChapter: OutlineChapter | null = null;

  lines.forEach((line) => {
    const match = /^(#{1,6})\s+(.+)$/.exec(line.trim());
    if (!match) {
      return;
    }
    const level = match[1].length;
    const heading = clean(match[2].replace(/#+$/, ''));
    if (!heading) {
      return;
    }
    if (level === 1 && title === fallbackTitle) {
      title = heading;
      return;
    }
    if (level <= 2) {
      currentChapter = { title: heading, sections: [] };
      chapters.push(currentChapter);
      return;
    }
    if (!currentChapter) {
      currentChapter = { title: '正文结构', sections: [] };
      chapters.push(currentChapter);
    }
    currentChapter.sections.push({
      title: heading,
      points: [],
      subsections: [],
    });
  });

  if (chapters.length === 0) {
    chapters.push({
      title: '正文结构',
      sections: [
        {
          title: title || '报告正文',
          points: ['当前正文未识别到标题层级，可回到正文视图查看完整内容。'],
          subsections: [],
        },
      ],
    });
  }

  return {
    kind: 'outline-solid',
    title,
    chapters,
  };
}

function outlineFromSections(sections: ReportSection[], title: string): RenderableReport {
  const chapters = sections.map((section) => ({
    title: section.title,
    sections: section.subsections.length > 0
      ? section.subsections
      : section.points.length > 0
        ? [{ title: '要点', points: section.points, subsections: [] }]
        : [],
  }));

  return {
    kind: 'outline-solid',
    title,
    chapters: chapters.length > 0 ? chapters : [{ title: '正文结构', sections: [] }],
  };
}

function normalizeReport(value: unknown, fallbackTitle: string): RenderableReport {
  const record = asRecord(value);
  const title = readText(record, ['title', 'report_title', 'name']) || fallbackTitle;
  const rawMainSections =
    record.mainContent
    || record.main_content
    || record.sections
    || record.chapters
    || record.body_sections
    || [];
  const sections = Array.isArray(rawMainSections)
    ? rawMainSections.map((section, index) => normalizeSection(section, index))
    : [];

  return {
    kind: 'report',
    title,
    summary: readText(record, ['summary', 'executive_summary', 'abstract']),
    introduction: readText(record, ['introduction', 'intro', 'background']),
    sections,
    keyFindings: toTextList(record.keyFindings || record.key_findings || record.findings),
    conclusions: readText(record, ['conclusions', 'conclusion']),
    recommendations: toTextList(record.recommendations || record.suggestions),
  };
}

function normalizeGeneric(value: unknown, fallbackTitle: string): RenderableReport {
  const record = asRecord(value);
  const sections = Object.entries(record)
    .filter(([, entryValue]) => entryValue !== null && entryValue !== undefined && clean(entryValue))
    .map(([key, entryValue], index) => {
      const title = key.replace(/_/g, ' ');
      if (Array.isArray(entryValue)) {
        return {
          title,
          points: toTextList(entryValue),
          subsections: [],
        };
      }
      if (entryValue && typeof entryValue === 'object') {
        return normalizeSection({ title, sections: Object.entries(entryValue).map(([name, content]) => ({ title: name, content })) }, index);
      }
      return {
        title,
        content: clean(entryValue),
        points: [],
        subsections: [],
      };
    });
  return { kind: 'generic', title: fallbackTitle, sections };
}

function normalizeReportContent(content: unknown, fallbackTitle: string, preferOutline = false): RenderableReport {
  const parsed = typeof content === 'string' ? tryParseJson(content) : content;

  if (typeof parsed === 'string') {
    if (preferOutline) {
      return outlineFromMarkdown(parsed, fallbackTitle);
    }
    return { kind: 'markdown', markdown: parsed };
  }

  if (Array.isArray(parsed)) {
    return normalizeOutline(parsed, fallbackTitle);
  }

  const record = asRecord(parsed);
  const embeddedMarkdown = getMarkdownFromRecord(record);
  if (embeddedMarkdown) {
    if (preferOutline) {
      return outlineFromMarkdown(embeddedMarkdown, readText(record, ['title', 'name']) || fallbackTitle);
    }
    return { kind: 'markdown', markdown: embeddedMarkdown };
  }

  if (preferOutline && (record.summary || record.sections || record.mainContent || record.main_content || record.chapters)) {
    const normalizedReport = normalizeReport(record, fallbackTitle);
    if (normalizedReport.kind === 'report') {
      return outlineFromSections(normalizedReport.sections, normalizedReport.title);
    }
  }

  if (
    record.summary
    || record.executive_summary
    || record.introduction
    || record.mainContent
    || record.main_content
    || record.sections
    || record.keyFindings
    || record.conclusions
    || record.chapters
  ) {
    return normalizeReport(record, fallbackTitle);
  }

  if (Array.isArray(record.outline) || Array.isArray(record.report_outline)) {
    return normalizeOutline(record.outline || record.report_outline, readText(record, ['title', 'name']) || fallbackTitle);
  }

  return normalizeGeneric(record, fallbackTitle);
}

function textPreview(value: string) {
  return value.split(/\n{2,}/).map((paragraph, index) => (
    <p key={`${index}-${paragraph.slice(0, 16)}`} className="report-artifact-preview__paragraph">
      {paragraph}
    </p>
  ));
}

function SectionView({ section, index, depth = 0 }: { section: ReportSection; index: number; depth?: number }) {
  return (
    <section className="report-artifact-preview__section">
      <div className="report-artifact-preview__section-heading">
        <span className="report-artifact-preview__section-number">{index + 1}</span>
        <h3 className={depth > 0 ? 'report-artifact-preview__subsection-title' : 'report-artifact-preview__section-title'}>
          {section.title}
        </h3>
      </div>
      {section.content ? textPreview(section.content) : null}
      {section.points.length > 0 ? (
        <ul className="report-artifact-preview__list">
          {section.points.map((point, pointIndex) => (
            <li key={`${pointIndex}-${point.slice(0, 16)}`}>{point}</li>
          ))}
        </ul>
      ) : null}
      {section.subsections.length > 0 ? (
        <div className="report-artifact-preview__subsections">
          {section.subsections.map((subsection, subsectionIndex) => (
            <SectionView key={`${subsectionIndex}-${subsection.title}`} section={subsection} index={subsectionIndex} depth={depth + 1} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function StructuredReportView({ report }: { report: RenderableReport }) {
  if (report.kind === 'markdown') {
    return (
      <div className="report-artifact-preview__markdown">
        <MarkdownPreview content={report.markdown} />
      </div>
    );
  }

  if (report.kind === 'outline-solid') {
    return (
      <article className="report-artifact-preview__document">
        <div className="report-artifact-preview__document-head">
          <div className="report-artifact-preview__eyebrow">报告大纲</div>
          <h2>{report.title}</h2>
        </div>
        <div className="report-artifact-preview__timeline">
          {report.chapters.map((chapter, chapterIndex) => (
            <section key={`${chapterIndex}-${chapter.title}`} className="report-artifact-preview__chapter">
              <div className="report-artifact-preview__chapter-marker">{chapterIndex + 1}</div>
              <div className="report-artifact-preview__chapter-body">
                <h3>{chapter.title}</h3>
                {chapter.sections.length > 0 ? (
                  <div className="report-artifact-preview__outline-sections">
                    {chapter.sections.map((section, sectionIndex) => (
                      <SectionView key={`${sectionIndex}-${section.title}`} section={section} index={sectionIndex} />
                    ))}
                  </div>
                ) : (
                  <p className="report-artifact-preview__muted">这一章暂未拆分小节。</p>
                )}
              </div>
            </section>
          ))}
        </div>
      </article>
    );
  }

  return (
    <article className="report-artifact-preview__document">
      <div className="report-artifact-preview__document-head">
        <div className="report-artifact-preview__eyebrow">{report.kind === 'generic' ? '结构化内容' : '报告正文'}</div>
        <h2>{report.title}</h2>
      </div>
      {'summary' in report && report.summary ? (
        <section className="report-artifact-preview__lead">
          <h3>摘要</h3>
          {textPreview(report.summary)}
        </section>
      ) : null}
      {'introduction' in report && report.introduction ? (
        <section className="report-artifact-preview__plain-block">
          <h3>引言</h3>
          {textPreview(report.introduction)}
        </section>
      ) : null}
      {'sections' in report && report.sections.length > 0 ? (
        <div className="report-artifact-preview__sections">
          {report.sections.map((section, index) => (
            <SectionView key={`${index}-${section.title}`} section={section} index={index} />
          ))}
        </div>
      ) : null}
      {'keyFindings' in report && report.keyFindings.length > 0 ? (
        <section className="report-artifact-preview__plain-block">
          <h3>关键发现</h3>
          <ul className="report-artifact-preview__list">
            {report.keyFindings.map((item, index) => (
              <li key={`${index}-${item.slice(0, 16)}`}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {'conclusions' in report && report.conclusions ? (
        <section className="report-artifact-preview__lead">
          <h3>结论</h3>
          {textPreview(report.conclusions)}
        </section>
      ) : null}
      {'recommendations' in report && report.recommendations.length > 0 ? (
        <section className="report-artifact-preview__plain-block">
          <h3>建议</h3>
          <ul className="report-artifact-preview__list">
            {report.recommendations.map((item, index) => (
              <li key={`${index}-${item.slice(0, 16)}`}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}

export default function ReportArtifactPreview({
  file,
  outlineContent,
  previewMode,
  canToggleOutline,
  canAddToChat,
  onPreviewModeChange,
  onBack,
  onToggleCollapsed,
  onAddToChat,
  onGenerateFromOutline,
}: Props) {
  const isOutlineFile = String(file.meta?.kind || '').trim() === 'outline-solid';
  const effectiveContent = previewMode === 'outline-solid' && canToggleOutline && outlineContent ? outlineContent : file.content;
  const report = useMemo(
    () => normalizeReportContent(effectiveContent, file.name, previewMode === 'outline-solid' && canToggleOutline),
    [effectiveContent, file.name, previewMode, canToggleOutline],
  );

  return (
    <div className="report-artifact-preview edu-rich-preview">
      <div className="report-artifact-preview__toolbar">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack} className="report-artifact-preview__back">
          返回
        </Button>
        <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作台" />
      </div>

      <div className="report-artifact-preview__actions">
        {canToggleOutline ? (
          <Space.Compact className="report-artifact-preview__switch">
            <Button type={previewMode === 'body' ? 'primary' : 'default'} onClick={() => onPreviewModeChange('body')}>
              正文
            </Button>
            <Button type={previewMode === 'outline-solid' ? 'primary' : 'default'} onClick={() => onPreviewModeChange('outline-solid')}>
              大纲
            </Button>
          </Space.Compact>
        ) : <span />}
        {canAddToChat ? (
          <Button className="report-artifact-preview__add-chat" icon={<MessageOutlined />} onClick={onAddToChat}>
            添加到对话
          </Button>
        ) : null}
      </div>

      <div className="report-artifact-preview__scroll">
        <StructuredReportView report={report} />
      </div>

      {isOutlineFile ? (
        <div className="report-artifact-preview__floating-action">
          <Button type="primary" onClick={onGenerateFromOutline}>
            生成报告
          </Button>
        </div>
      ) : null}
    </div>
  );
}
