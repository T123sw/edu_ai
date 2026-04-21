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
  type: 'report' | 'ppt' | 'lesson_plan' | 'quiz' | 'game';
  content: unknown;
  meta?: Record<string, unknown>;
}

import { normalizeGeneratedFileId } from './materials.helpers.ts';
import { resolvePptAssetUrl } from './pptAssets.ts';

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

function formatPptOutlineContent(content: unknown): string {
  const deck = content && typeof content === 'object' ? (content as Record<string, unknown>) : {};
  const deckTitle = String(deck.deck_title || deck.title || '').trim();
  const deckSubtitle = String(deck.deck_subtitle || deck.subtitle || '').trim();
  const slides = Array.isArray(deck.slides) ? deck.slides : [];

  const lines: string[] = [];
  if (deckTitle) {
    lines.push(`# ${deckTitle}`);
  }
  if (deckSubtitle) {
    lines.push(`> ${deckSubtitle}`);
  }
  if (slides.length > 0) {
    if (lines.length > 0) {
      lines.push('');
    }
    slides.forEach((slide: any, index: number) => {
      const slideNo = Number(slide?.slide_index) || index + 1;
      const title = String(slide?.title || `第 ${slideNo} 页`).trim();
      const role = String(slide?.role || '').trim();
      const goal = String(slide?.goal || '').trim();
      const keyPoints = Array.isArray(slide?.key_points)
        ? slide.key_points.map((item: unknown) => String(item || '').trim()).filter(Boolean)
        : [];

      lines.push(`## ${slideNo}. ${title}`);
      if (role) {
        lines.push(`- 角色：${role}`);
      }
      if (goal) {
        lines.push(`- 目标：${goal}`);
      }
      keyPoints.forEach((item) => {
        lines.push(`- ${item}`);
      });
      lines.push('');
    });
  }

  return lines.join('\n').trim();
}

function buildPptFileName(baseTitle: string, fallbackName: string): string {
  const normalized = String(baseTitle || '').trim();
  if (!normalized) {
    return fallbackName;
  }
  return normalized;
}

function mergePptArtifacts(artifacts: V2ArtifactLike[]): GeneratedFileLike[] {
  const outlineArtifact = artifacts.find(
    (artifact) => String(artifact.artifact_type || '').trim() === 'ppt_outline',
  );
  const markdownArtifact = artifacts.find(
    (artifact) => String(artifact.artifact_type || '').trim() === 'ppt_content_markdown',
  );
  const deckArtifact = artifacts.find(
    (artifact) => String(artifact.artifact_type || '').trim() === 'ppt_deck',
  );

  const outlineContent = outlineArtifact ? formatPptOutlineContent(outlineArtifact.content) : '';
  const markdownContent = String(markdownArtifact?.content || '').trim();

  if (deckArtifact) {
    const artifactId = normalizeGeneratedFileId(String(deckArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
    const deckContent = deckArtifact.content && typeof deckArtifact.content === 'object'
      ? (deckArtifact.content as Record<string, unknown>)
      : {};
    const title = buildPptFileName(
      String(deckArtifact.title || '').trim(),
      `${String(deckContent.deck_title || 'PPT').trim() || 'PPT'}.pptx`,
    );
    return [
      {
        id: artifactId,
        name: title,
        type: 'ppt',
        content: deckContent,
        meta: {
          kind: 'ppt_deck',
          outlineContent: outlineContent || undefined,
          contentMarkdown: markdownContent || undefined,
          originalArtifactId: String(deckArtifact.artifact_id || '').trim() || undefined,
          htmlPreviewUrl: resolvePptAssetUrl(deckContent.html_full_url || deckContent.html_url),
          pptxUrl: resolvePptAssetUrl(deckContent.pptx_url),
          manifestUrl: resolvePptAssetUrl(deckContent.manifest_url),
          jobId: String(deckContent.job_id || '').trim() || undefined,
          revisionId: String(deckContent.revision_id || '').trim() || undefined,
          generationState:
            deckArtifact.generation_state && typeof deckArtifact.generation_state === 'object'
              ? deckArtifact.generation_state
              : undefined,
        },
      },
    ];
  }

  if (markdownArtifact) {
    const artifactId = normalizeGeneratedFileId(String(markdownArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
    const title = buildPptFileName(String(markdownArtifact.title || '').trim(), 'PPT-content.md');
    return [
      {
        id: artifactId,
        name: title,
        type: 'ppt',
        content: markdownContent,
        meta: {
          kind: 'ppt_content_markdown',
          outlineContent: outlineContent || undefined,
          originalArtifactId: String(markdownArtifact.artifact_id || '').trim() || undefined,
          generationState:
            markdownArtifact.generation_state && typeof markdownArtifact.generation_state === 'object'
              ? markdownArtifact.generation_state
              : undefined,
        },
      },
    ];
  }

  if (outlineArtifact) {
    const artifactId = normalizeGeneratedFileId(String(outlineArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
    const title = buildPptFileName(String(outlineArtifact.title || '').trim(), 'PPT-大纲.md');
    return [
      {
        id: artifactId,
        name: title,
        type: 'ppt',
        content: outlineContent,
        meta: {
          kind: 'ppt_outline',
          originalArtifactId: String(outlineArtifact.artifact_id || '').trim() || undefined,
          generationState:
            outlineArtifact.generation_state && typeof outlineArtifact.generation_state === 'object'
              ? outlineArtifact.generation_state
              : undefined,
        },
      },
    ];
  }

  return [];
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

function buildJsonFileName(baseTitle: string, fallbackName: string): string {
  const normalized = String(baseTitle || '').trim();
  if (!normalized) {
    return fallbackName;
  }
  return /\.json$/i.test(normalized) ? normalized : `${normalized}.json`;
}

function mergeLessonPlanArtifacts(artifacts: V2ArtifactLike[]): GeneratedFileLike[] {
  const outlineArtifact = artifacts.find(
    (artifact) => String(artifact.artifact_type || '').trim() === 'lesson_plan_outline',
  );
  const lessonPlanArtifact = artifacts.find(
    (artifact) => String(artifact.artifact_type || '').trim() === 'lesson_plan',
  );

  if (lessonPlanArtifact) {
    const artifactId = normalizeGeneratedFileId(String(lessonPlanArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
    const content = lessonPlanArtifact.content && typeof lessonPlanArtifact.content === 'object'
      ? (lessonPlanArtifact.content as Record<string, unknown>)
      : {};
    const title = buildJsonFileName(
      String(lessonPlanArtifact.title || '').trim(),
      `${String(content.title || '教案').trim() || '教案'}.json`,
    );
    return [
      {
        id: artifactId,
        name: title,
        type: 'lesson_plan',
        content,
        meta: {
          kind: 'final_lesson_plan',
          outlineContent: outlineArtifact?.content || undefined,
          outlineArtifactId: outlineArtifact?.artifact_id || undefined,
          originalArtifactId: String(lessonPlanArtifact.artifact_id || '').trim() || undefined,
          generationState:
            lessonPlanArtifact.generation_state && typeof lessonPlanArtifact.generation_state === 'object'
              ? lessonPlanArtifact.generation_state
              : undefined,
        },
      },
    ];
  }

  if (outlineArtifact) {
    const artifactId = normalizeGeneratedFileId(String(outlineArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
    const content = outlineArtifact.content && typeof outlineArtifact.content === 'object'
      ? (outlineArtifact.content as Record<string, unknown>)
      : {};
    const title = buildJsonFileName(String(outlineArtifact.title || '').trim(), '教案大纲.json');
    return [
      {
        id: artifactId,
        name: title,
        type: 'lesson_plan',
        content,
        meta: {
          kind: 'outline',
          originalArtifactId: String(outlineArtifact.artifact_id || '').trim() || undefined,
          generationState:
            outlineArtifact.generation_state && typeof outlineArtifact.generation_state === 'object'
              ? outlineArtifact.generation_state
              : undefined,
        },
      },
    ];
  }

  return [];
}

function mergeQuizArtifacts(artifacts: V2ArtifactLike[]): GeneratedFileLike[] {
  const quizArtifact = artifacts.find(
    (artifact) => String(artifact.artifact_type || '').trim() === 'quiz',
  );
  if (!quizArtifact) {
    return [];
  }

  const artifactId = normalizeGeneratedFileId(String(quizArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
  const content = quizArtifact.content && typeof quizArtifact.content === 'object'
    ? (quizArtifact.content as Record<string, unknown>)
    : {};
  const title = buildJsonFileName(
    String(quizArtifact.title || '').trim(),
    `${String(content.title || '习题').trim() || '习题'}.json`,
  );

  return [
    {
      id: artifactId,
      name: title,
      type: 'quiz',
      content,
      meta: {
        kind: 'quiz',
        originalArtifactId: String(quizArtifact.artifact_id || '').trim() || undefined,
        generationState:
          quizArtifact.generation_state && typeof quizArtifact.generation_state === 'object'
            ? quizArtifact.generation_state
            : undefined,
      },
    },
  ];
}

function mergeGameArtifacts(artifacts: V2ArtifactLike[]): GeneratedFileLike[] {
  const gameArtifact = artifacts.find(
    (artifact) => String(artifact.artifact_type || '').trim() === 'game',
  );
  if (!gameArtifact) {
    return [];
  }

  const artifactId = normalizeGeneratedFileId(String(gameArtifact.artifact_id || '').trim()) || `artifact-${Date.now()}`;
  const content = gameArtifact.content && typeof gameArtifact.content === 'object'
    ? (gameArtifact.content as Record<string, unknown>)
    : {};

  return [
    {
      id: artifactId,
      name: String(gameArtifact.title || '小游戏.html').trim() || '小游戏.html',
      type: 'game',
      content,
      meta: {
        kind: 'game',
        htmlUrl: String(content.html_url || '').trim() || undefined,
        gameType: String(content.game_type || '').trim() || undefined,
        templateId: String(content.template_id || '').trim() || undefined,
        originalArtifactId: String(gameArtifact.artifact_id || '').trim() || undefined,
        generationState:
          gameArtifact.generation_state && typeof gameArtifact.generation_state === 'object'
            ? gameArtifact.generation_state
            : undefined,
      },
    },
  ];
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
  return [
    ...mergeReportArtifacts(artifacts),
    ...mergePptArtifacts(artifacts),
    ...mergeLessonPlanArtifacts(artifacts),
    ...mergeQuizArtifacts(artifacts),
    ...mergeGameArtifacts(artifacts),
  ];
}

export function restoreGeneratedFilesFromConversationDetail(
  detail: ConversationDetailLike,
): GeneratedFileLike[] {
  const conversationId = String(detail.conversation_id || '').trim();
  const artifacts = Array.isArray(detail.state?.workflow_state?.artifacts)
    ? detail.state?.workflow_state?.artifacts || []
    : [];
  const files = [
    ...mergeReportArtifacts(artifacts),
    ...mergePptArtifacts(artifacts),
    ...mergeLessonPlanArtifacts(artifacts),
    ...mergeQuizArtifacts(artifacts),
    ...mergeGameArtifacts(artifacts),
  ];

  return files.map((file) => ({
    ...file,
    meta: {
      ...(file.meta || {}),
      origin: 'conversation',
      conversationId: conversationId || undefined,
    },
  }));
}
