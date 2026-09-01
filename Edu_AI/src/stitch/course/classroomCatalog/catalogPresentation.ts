import type {
  ClassroomCatalogLeaf,
  ClassroomCatalogResource,
} from "../../api/types";
import { buildRoleCourseHash } from "../../shared/routes/roleCourseRouteResolver";


export type CurriculumTreeNode = {
  key: string;
  title: string;
  kind: "branch" | "leaf";
  children: CurriculumTreeNode[];
  leaf?: ClassroomCatalogLeaf;
};


export function buildCurriculumResourceTree(
  leaves: ClassroomCatalogLeaf[],
): CurriculumTreeNode[] {
  const roots: CurriculumTreeNode[] = [];
  for (const leaf of leaves) {
    const path = leaf.path_titles.length > 1
      ? leaf.path_titles.slice(1, -1)
      : [];
    let children = roots;
    const accumulated: string[] = [];
    for (const title of path) {
      accumulated.push(title);
      const key = `branch:${accumulated.join("/")}`;
      let branch = children.find((item) => item.kind === "branch" && item.key === key);
      if (!branch) {
        branch = { key, title, kind: "branch", children: [] };
        children.push(branch);
      }
      children = branch.children;
    }
    children.push({
      key: `leaf:${leaf.leaf_id}`,
      title: leaf.title,
      kind: "leaf",
      children: [],
      leaf,
    });
  }
  return roots;
}


export function filterCurriculumTree(
  tree: CurriculumTreeNode[],
  query: string,
): CurriculumTreeNode[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return tree;

  const filterNode = (node: CurriculumTreeNode): CurriculumTreeNode | null => {
    const selfMatches = node.title.toLocaleLowerCase().includes(normalized)
      || node.leaf?.resources.some((resource) =>
        catalogResourceLabel(resource).toLocaleLowerCase().includes(normalized)) === true;
    if (selfMatches) return node;
    const children = node.children
      .map(filterNode)
      .filter((item): item is CurriculumTreeNode => item !== null);
    return children.length ? { ...node, children } : null;
  };

  return tree.map(filterNode).filter((item): item is CurriculumTreeNode => item !== null);
}


export function catalogResourceLabel(resource: ClassroomCatalogResource): string {
  const fallback = {
    classroom: "AI课堂",
    study_guide: "学习指南",
    practice: "练习题",
  }[resource.standard_kind];
  return String(resource.resource?.title || fallback);
}


export function catalogResourceStatus(resource: ClassroomCatalogResource): string {
  if (resource.progress?.status === "completed") return "已完成";
  if (resource.progress?.status === "in_progress") return "学习中";
  if (resource.progress?.status === "not_started") return "未开始";
  if (resource.review_status === "pending") return "待审核";
  if (resource.review_status === "rejected") return "已退回";
  if (resource.approved_version != null) return "已发布";
  return "未生成";
}


export function catalogLeafSummary(leaf: ClassroomCatalogLeaf): string {
  if (leaf.learning_summary) {
    return leaf.learning_summary.total === 0
      ? "暂无资料"
      : `已完成 ${leaf.learning_summary.completed}/${leaf.learning_summary.total}`;
  }
  if (leaf.summary) {
    return `待审核 ${leaf.summary.pending} · 已发布 ${leaf.summary.published}`;
  }
  return leaf.resources.length ? `共 ${leaf.resources.length} 项资料` : "暂无资料";
}


export function readCatalogTarget(hash: string): {
  nodeId: string | null;
  resourceId: string | null;
} {
  const query = String(hash || "").split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  return {
    nodeId: params.get("node_id"),
    resourceId: params.get("resource_id"),
  };
}


export function buildCatalogHash(
  role: "student" | "teacher",
  courseId: string,
  nodeId?: string | null,
  resourceId?: string | null,
): string {
  return buildRoleCourseHash(role, "classroom-studio", courseId, {
    node_id: nodeId,
    resource_id: resourceId,
  });
}
