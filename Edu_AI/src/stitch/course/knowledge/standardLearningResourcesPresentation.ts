import type {
  StandardResourceBatch,
  StandardResourceKind,
  StandardResourceLeaf,
  StandardResourceSlot,
} from "../../api/types";
import { buildClassroomPlayerHash } from "../../../openmaic/classroomGenerationFlow";

export type StandardResourceLeafGroup = {
  chapterId: string;
  chapterTitle: string;
  leaves: StandardResourceLeaf[];
};

export const STANDARD_RESOURCE_KIND_META: Record<
  StandardResourceKind,
  { label: string; icon: string; description: string }
> = {
  classroom: {
    label: "AI 课堂",
    icon: "smart_display",
    description: "以场景化讲解帮助学生建立理解",
  },
  study_guide: {
    label: "学习指南",
    icon: "menu_book",
    description: "梳理核心概念、示例与复习清单",
  },
  practice: {
    label: "练习",
    icon: "quiz",
    description: "通过题目检查理解与应用情况",
  },
};

export function groupStandardResourceLeaves(
  leaves: StandardResourceLeaf[],
): StandardResourceLeafGroup[] {
  const groups = new Map<string, StandardResourceLeafGroup>();
  for (const leaf of leaves) {
    const chapterId = String(leaf.chapter_id || "ungrouped");
    const chapterTitle = String(leaf.chapter_title || "其他知识点");
    const current = groups.get(chapterId);
    if (current) {
      current.leaves.push(leaf);
    } else {
      groups.set(chapterId, { chapterId, chapterTitle, leaves: [leaf] });
    }
  }
  return [...groups.values()];
}

export function standardBatchProgress(batch: StandardResourceBatch): {
  percent: number;
  label: string;
} {
  const finished = batch.succeeded_items + batch.failed_items;
  const percent = batch.total_items
    ? Math.round((finished / batch.total_items) * 100)
    : 0;
  if (batch.status === "completed") return { percent: 100, label: "全部生成完成" };
  if (batch.status === "failed") return { percent: 100, label: "生成失败" };
  if (batch.status === "partial") {
    return { percent: 100, label: `${batch.succeeded_items} 项完成，${batch.failed_items} 项失败` };
  }
  return {
    percent,
    label: `已完成 ${finished}/${batch.total_items} 项`,
  };
}

export function standardReviewLabel(status: string): string {
  return {
    not_generated: "未生成",
    pending: "待审核",
    approved: "已发布",
    rejected: "已退回",
  }[status] || status;
}

export function getStandardResourceDetailTarget(
  courseId: string,
  slot: StandardResourceSlot,
): { kind: "route"; href: string } | { kind: "dialog" } {
  return slot.standard_kind === "classroom"
    ? { kind: "route", href: buildClassroomPlayerHash(courseId, slot.material_id) }
    : { kind: "dialog" };
}

export function standardResourceBody(slot: StandardResourceSlot): string {
  const resource = (slot.resource || {}) as Record<string, unknown>;
  for (const key of ["final_markdown", "markdown", "report_content", "text", "content"]) {
    const value = resource[key];
    if (typeof value === "string" && value.trim()) return value;
    if (value && typeof value === "object") return JSON.stringify(value, null, 2);
  }
  return "该课程资料已经生成，暂无可展示的正文内容。";
}

export function canApproveStandardResource(
  canManage: boolean,
  slot: StandardResourceSlot,
): boolean {
  return canManage && slot.review_status === "pending" && Boolean(slot.resource);
}

export function standardSelectionSummary(selectedLeafCount: number) {
  const leafCount = Math.max(0, selectedLeafCount);
  const resourceCount = leafCount * 3;
  return {
    leafCount,
    resourceCount,
    label: `已选择 ${leafCount} 个知识点，将生成 ${resourceCount} 项资源`,
  };
}

export function toggleStandardResourceLeafScope(
  current: ReadonlySet<string>,
  scopeLeafIds: readonly string[],
) {
  const next = new Set(current);
  const scopeIsSelected = scopeLeafIds.length > 0
    && scopeLeafIds.every((leafId) => next.has(leafId));

  for (const leafId of scopeLeafIds) {
    if (scopeIsSelected) next.delete(leafId);
    else next.add(leafId);
  }
  return next;
}

export function standardResourceLeavesForKnowledgeScope(
  leaves: StandardResourceLeaf[],
  scopeNodeIds: ReadonlySet<string>,
): StandardResourceLeaf[] {
  return leaves.filter(
    (leaf) => scopeNodeIds.has(leaf.leaf_id)
      && leaf.slots.some((slot) => Boolean(slot.resource)),
  );
}
