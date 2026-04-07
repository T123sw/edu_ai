export interface ReportConfigInput {
  title?: string;
  focus_areas?: string[];
}

export interface V2ArtifactLike {
  artifact_id?: string;
  artifact_type?: string;
  title?: string;
  content?: unknown;
  version?: Record<string, unknown>;
  generation_state?: Record<string, unknown>;
}

export interface V2ResponseLike {
  action?: { name?: string };
  artifacts?: V2ArtifactLike[];
}

export interface ConversationDetailLike {
  conversation_id?: string;
  state?: {
    workflow_state?: {
      artifacts?: V2ArtifactLike[];
    };
  };
}

export interface GeneratedFileLike {
  id: string;
  name: string;
  type: 'report';
  content: string;
  meta?: Record<string, unknown>;
}

import { normalizeGeneratedFileId } from './materials.helpers.ts';

function formatOutlineContent(content: unknown): string {
  if (!Array.isArray(content)) {
    return String(content ?? '');
  }

  return content
    .map((chapter: any, index: number) => {
      const chapterNo = Number(chapter?.chapter_id) || index + 1;
      const chapterTitle = String(chapter?.chapter_title || chapter?.title || `第${chapterNo}章`);
      const chapterGoal = chapter?.chapter_goal ? `目标：${String(chapter.chapter_goal)}` : '';
      const sections = Array.isArray(chapter?.sections)
        ? chapter.sections
            .map((section: any, sectionIndex: number) => {
              const sectionId = String(section?.section_id || `${chapterNo}.${sectionIndex + 1}`);
              const sectionTitle = String(section?.title || `小节${sectionIndex + 1}`);
              return `- ${sectionId} ${sectionTitle}`;
            })
            .join('\n')
        : '';

      return [`${chapterNo}. ${chapterTitle}`, chapterGoal, sections].filter(Boolean).join('\n');
    })
    .join('\n\n');
}

function extractMarkdownTitle(content: unknown): string {
  const text = String(content ?? '');
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    const match = trimmed.match(/^#{1,6}\s+(.+)$/);
    if (!match) {
      continue;
    }
    const title = match[1].trim();
    if (!['正文', '报告', '分析报告'].includes(title)) {
      return title;
    }
  }
  return '';
}

function isLowInfoReportTitle(value: string): boolean {
  const normalized = String(value || '').trim().replace(/\.md$/i, '').trim().toLowerCase();
  return ['', '报告', '分析报告', '正文', 'report'].includes(normalized);
}

function buildReportFileName(baseTitle: string, fallbackName: string): string {
  const normalized = String(baseTitle || '').trim().replace(/\.md$/i, '');
  if (!normalized || isLowInfoReportTitle(normalized)) {
    return fallbackName;
  }
  return `${normalized}.md`;
}

function mergeReportArtifacts(artifacts: V2ArtifactLike[]): GeneratedFileLike[] {
  const outlineArtifact = artifacts.find(
    (artifact) => String(artifact.artifact_type || '').trim() === 'report_outline',
  );
  const reportArtifact = artifacts.find(
    (artifact) => String(artifact.artifact_type || '').trim() === 'report',
  );

  const outlineContent = outlineArtifact ? formatOutlineContent(outlineArtifact.content) : '';

  if (reportArtifact) {
    const artifactId = normalizeGeneratedFileId(String(reportArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
    const artifactTitle = String(reportArtifact.title || '').trim();
    const markdownTitle = extractMarkdownTitle(reportArtifact.content);
    const title = buildReportFileName(
      !isLowInfoReportTitle(artifactTitle) ? artifactTitle : markdownTitle,
      markdownTitle ? `${markdownTitle}.md` : '报告.md',
    );
    return [
      {
        id: artifactId,
        name: title,
        type: 'report',
        content: String(reportArtifact.content || ''),
        meta: {
          kind: 'final_report',
          outlineContent: outlineContent || undefined,
          outlineArtifactId: outlineArtifact?.artifact_id || undefined,
          originalArtifactId: String(reportArtifact.artifact_id || '').trim() || undefined,
          versionId: String(reportArtifact.version?.version_id || '').trim() || undefined,
          versionNumber:
            typeof reportArtifact.version?.version_number === 'number'
              ? reportArtifact.version.version_number
              : undefined,
          parentArtifactId: String(reportArtifact.version?.parent_artifact_id || '').trim() || undefined,
          rootArtifactId: String(reportArtifact.version?.root_artifact_id || '').trim() || undefined,
          generationState:
            reportArtifact.generation_state && typeof reportArtifact.generation_state === 'object'
              ? reportArtifact.generation_state
              : undefined,
        },
      },
    ];
  }

  if (outlineArtifact) {
    const artifactId = normalizeGeneratedFileId(String(outlineArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
    const title = buildReportFileName(String(outlineArtifact.title || '').trim(), '报告大纲.md');
    return [
      {
        id: artifactId,
        name: title,
        type: 'report',
        content: outlineContent,
        meta: {
          kind: 'outline',
          originalArtifactId: String(outlineArtifact.artifact_id || '').trim() || undefined,
          versionId: String(outlineArtifact.version?.version_id || '').trim() || undefined,
          versionNumber:
            typeof outlineArtifact.version?.version_number === 'number'
              ? outlineArtifact.version.version_number
              : undefined,
          parentArtifactId: String(outlineArtifact.version?.parent_artifact_id || '').trim() || undefined,
          rootArtifactId: String(outlineArtifact.version?.root_artifact_id || '').trim() || undefined,
        },
      },
    ];
  }

  return [];
}

export function buildReportQuestionFromConfig(config: ReportConfigInput): string {
  const parts: string[] = ['请基于当前会话和我选中的资料生成一份报告。'];
  const title = String(config.title || '').trim();
  const focusAreas = Array.isArray(config.focus_areas)
    ? config.focus_areas.map((item) => String(item || '').trim()).filter(Boolean)
    : [];

  if (title) {
    parts.push(`报告标题：${title}。`);
  }
  if (focusAreas.length > 0) {
    parts.push(`重点关注：${focusAreas.join('、')}。`);
  }

  return parts.join('');
}

export function extractGeneratedFilesFromV2Response(response: V2ResponseLike): GeneratedFileLike[] {
  const artifacts = Array.isArray(response.artifacts) ? response.artifacts : [];
  return mergeReportArtifacts(artifacts);
}

export function restoreGeneratedFilesFromConversationDetail(
  detail: ConversationDetailLike,
): GeneratedFileLike[] {
  const conversationId = String(detail.conversation_id || '').trim();
  const files = mergeReportArtifacts(
    Array.isArray(detail.state?.workflow_state?.artifacts)
      ? detail.state?.workflow_state?.artifacts || []
      : [],
  );

  return files.map((file) => ({
    ...file,
    meta: {
      ...(file.meta || {}),
      origin: 'conversation',
      conversationId: conversationId || undefined,
    },
  }));
}
