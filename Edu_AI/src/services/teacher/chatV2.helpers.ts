export interface ReportConfigInput {
  title?: string;
  focus_areas?: string[];
}

export interface V2ArtifactLike {
  artifact_id?: string;
  artifact_type?: string;
  title?: string;
  content?: unknown;
}

export interface V2ResponseLike {
  action?: { name?: string };
  artifacts?: V2ArtifactLike[];
}

export interface GeneratedFileLike {
  id: string;
  name: string;
  type: 'report';
  content: string;
  meta?: Record<string, unknown>;
}

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

  return artifacts
    .map((artifact): GeneratedFileLike | null => {
      const artifactType = String(artifact.artifact_type || '').trim();
      const artifactId = String(artifact.artifact_id || '').trim() || `artifact-${Date.now()}`;
      const title = String(artifact.title || '').trim();

      if (artifactType === 'report_outline') {
        return {
          id: artifactId,
          name: title || '报告大纲.md',
          type: 'report',
          content: formatOutlineContent(artifact.content),
          meta: {
            kind: 'outline',
          },
        };
      }

      if (artifactType === 'report') {
        return {
          id: artifactId,
          name: title || '报告.md',
          type: 'report',
          content: String(artifact.content || ''),
          meta: {
            kind: 'final_report',
          },
        };
      }

      return null;
    })
    .filter((item): item is GeneratedFileLike => item !== null);
}
