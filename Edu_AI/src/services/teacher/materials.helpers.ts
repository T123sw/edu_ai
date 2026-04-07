type GeneratedFileLike = {
  id: string;
  name?: string;
  type?: string;
  content?: unknown;
  meta?: Record<string, any>;
};

type CourseMaterialLike = {
  id: string;
  name?: string;
  type?: string;
  content?: unknown;
  courseId?: string;
  isPinned?: boolean;
  pinnedAt?: string;
  addedAt?: string;
  version?: Record<string, unknown>;
  generationState?: Record<string, unknown>;
  outline?: unknown;
};

const toTimestamp = (value: unknown): number => {
  if (typeof value !== 'string' || !value.trim()) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const sortByPinnedMeta = <T extends { pinned: boolean; pinnedAt?: string; addedAt?: string; index: number }>(
  items: T[],
): T[] =>
  [...items].sort((left, right) => {
    if (left.pinned !== right.pinned) {
      return left.pinned ? -1 : 1;
    }

    const pinnedAtDiff = toTimestamp(right.pinnedAt) - toTimestamp(left.pinnedAt);
    if (pinnedAtDiff !== 0) {
      return pinnedAtDiff;
    }

    const addedAtDiff = toTimestamp(right.addedAt) - toTimestamp(left.addedAt);
    if (addedAtDiff !== 0) {
      return addedAtDiff;
    }

    return left.index - right.index;
  });

const sortByRecentActivityMeta = <T extends { pinnedAt?: string; addedAt?: string; index: number }>(items: T[]): T[] =>
  [...items].sort((left, right) => {
    const leftActivityAt = Math.max(toTimestamp(left.addedAt), toTimestamp(left.pinnedAt));
    const rightActivityAt = Math.max(toTimestamp(right.addedAt), toTimestamp(right.pinnedAt));
    const activityDiff = rightActivityAt - leftActivityAt;
    if (activityDiff !== 0) {
      return activityDiff;
    }

    const addedAtDiff = toTimestamp(right.addedAt) - toTimestamp(left.addedAt);
    if (addedAtDiff !== 0) {
      return addedAtDiff;
    }

    return left.index - right.index;
  });

const isCourseMaterialGeneratedFile = (file: GeneratedFileLike): boolean =>
  String(file.meta?.origin || '').trim() === 'course_material';

const isConversationGeneratedFile = (file: GeneratedFileLike): boolean =>
  !isCourseMaterialGeneratedFile(file) && Boolean(String(file.meta?.conversationId || '').trim());

export function normalizeGeneratedFileId(id: string): string {
  const normalized = String(id || '').trim();
  if (!normalized) {
    return '';
  }
  return normalized.replace(/:/g, '__').replace(/[<>"/\\|?*]/g, '_');
}

export function sortCourseMaterials<T extends CourseMaterialLike>(materials: T[]): T[] {
  return sortByPinnedMeta(
    materials.map((item, index) => ({
      ...item,
      pinned: Boolean(item.isPinned),
      index,
    })),
  ).map(({ pinned: _pinned, index: _index, ...item }) => item as T);
}

export function upsertCourseMaterialInList<T extends CourseMaterialLike>(materials: T[], material: T): T[] {
  const existing = materials.find((item) => item.id === material.id);
  const nextItem = existing
    ? {
        ...existing,
        ...material,
        isPinned: material.isPinned ?? existing.isPinned,
        pinnedAt: material.pinnedAt ?? existing.pinnedAt,
      }
    : material;

  return sortCourseMaterials([
    ...materials.filter((item) => item.id !== material.id),
    nextItem,
  ]);
}

export function pinCourseMaterialInList<T extends CourseMaterialLike>(
  materials: T[],
  id: string,
  isPinned: boolean,
  pinnedAt?: string,
): T[] {
  return sortCourseMaterials(
    materials.map((item) =>
      item.id === id
        ? {
            ...item,
            isPinned,
            pinnedAt: isPinned ? pinnedAt || new Date().toISOString() : undefined,
          }
        : item,
    ),
  );
}

export function sortGeneratedFiles<T extends GeneratedFileLike>(files: T[]): T[] {
  return sortByRecentActivityMeta(
    files.map((item, index) => ({
      ...item,
      pinnedAt:
        typeof item.meta?.pinnedAt === 'string'
          ? item.meta.pinnedAt
          : undefined,
      addedAt:
        typeof item.meta?.addedAt === 'string'
          ? item.meta.addedAt
          : undefined,
      index,
    })),
  ).map(({ pinnedAt: _pinnedAt, addedAt: _addedAt, index: _index, ...item }) => item as T);
}

export function isArtifactReferenceEligible(file: GeneratedFileLike | null | undefined): boolean {
  return String(file?.type || '').trim() === 'report';
}

export function replaceConversationGeneratedFiles<T extends GeneratedFileLike>(files: T[], nextFiles: T[]): T[] {
  return sortGeneratedFiles([
    ...nextFiles,
    ...files.filter((file) => !isConversationGeneratedFile(file)),
  ]);
}

export function clearConversationGeneratedFiles<T extends GeneratedFileLike>(files: T[]): T[] {
  return sortGeneratedFiles(files.filter((file) => !isConversationGeneratedFile(file)));
}

export function upsertGeneratedFileInList<T extends GeneratedFileLike>(files: T[], file: T): T[] {
  const existing = files.find((item) => item.id === file.id);
  const nextFile = existing
    ? {
        ...existing,
        ...file,
        meta: {
          ...(existing.meta || {}),
          ...(file.meta || {}),
        },
      }
    : {
        ...file,
        meta: {
          ...(file.meta || {}),
          addedAt:
            typeof file.meta?.addedAt === 'string'
              ? file.meta.addedAt
              : new Date().toISOString(),
        },
      };

  if (existing) {
    nextFile.meta = {
      ...(nextFile.meta || {}),
      addedAt:
        typeof nextFile.meta?.addedAt === 'string'
          ? nextFile.meta.addedAt
          : typeof existing.meta?.addedAt === 'string'
            ? existing.meta.addedAt
            : new Date().toISOString(),
    };
  }

  return sortGeneratedFiles([
    ...files.filter((item) => item.id !== file.id),
    nextFile,
  ]);
}

export function pinGeneratedFileInList<T extends GeneratedFileLike>(
  files: T[],
  id: string,
  isPinned: boolean,
  pinnedAt?: string,
): T[] {
  return sortGeneratedFiles(
    files.map((item) =>
      item.id === id
        ? {
            ...item,
            meta: {
              ...(item.meta || {}),
              isPinned,
              pinnedAt: isPinned ? pinnedAt || new Date().toISOString() : undefined,
            },
          }
        : item,
    ),
  );
}

export function toGeneratedFileFromCourseMaterial<T extends CourseMaterialLike>(material: T): GeneratedFileLike | null {
  const id = normalizeGeneratedFileId(String(material.id || '').trim());
  const type = String(material.type || '').trim();
  if (!id || !type) {
    return null;
  }

  return {
    id,
    name: String(material.name || '未命名'),
    type,
    content: material.content,
    meta: {
      origin: 'course_material',
      courseId: material.courseId,
      isPinned: Boolean(material.isPinned),
      pinnedAt: material.pinnedAt,
      addedAt: material.addedAt,
      originalArtifactId: id,
      versionId: String(material.version?.version_id || '').trim() || undefined,
      versionNumber:
        typeof material.version?.version_number === 'number'
          ? material.version.version_number
          : undefined,
      parentArtifactId: String(material.version?.parent_artifact_id || '').trim() || undefined,
      rootArtifactId: String(material.version?.root_artifact_id || '').trim() || undefined,
      generationState:
        material.generationState && typeof material.generationState === 'object'
          ? material.generationState
          : undefined,
      outlineContent: material.outline,
    },
  };
}

type ArtifactVersionLike = {
  versionId?: string;
  versionNumber?: number;
};

export function formatArtifactVersionText(version?: ArtifactVersionLike | null): string {
  const versionNumber =
    typeof version?.versionNumber === 'number' && Number.isFinite(version.versionNumber)
      ? Math.max(1, Math.floor(version.versionNumber))
      : undefined;
  const versionId =
    typeof version?.versionId === 'string' && version.versionId.trim()
      ? version.versionId.trim()
      : versionNumber
        ? `v${versionNumber}`
        : '';

  if (!versionId) {
    return '';
  }

  if (!versionNumber || versionNumber <= 1) {
    return versionId;
  }

  return `${versionId}（基于v${versionNumber - 1} 修改）`;
}
