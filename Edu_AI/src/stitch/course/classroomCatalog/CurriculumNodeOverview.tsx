import type { ClassroomCatalogLeaf } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { catalogLeafSummary, catalogResourceLabel, catalogResourceStatus } from "./catalogPresentation";

type Props = { leaf: ClassroomCatalogLeaf | null; mode: "manage" | "learn"; totalLeafCount: number; onGenerate: () => void; onSelectResource: (resourceId: string) => void };

export function CurriculumNodeOverview({ leaf, mode, totalLeafCount, onGenerate, onSelectResource }: Props) {
  if (!leaf) return <section className="curriculum-node-overview is-course">
    <span className="curriculum-node-overview__icon"><MaterialIcon name="school" /></span>
    <p className="curriculum-node-overview__eyebrow">课程学习空间</p><h2>从课程目录开始学习</h2>
    <p>左侧按章节整理了 {totalLeafCount} 个知识小节。展开小节即可查看 AI 课堂、学习指南和练习。</p>
    {mode === "manage" ? <button type="button" className="catalog-primary-action" onClick={onGenerate}><MaterialIcon name="auto_awesome" />生成学习资源</button> : null}
  </section>;
  const next = leaf.resources.find((item) => item.progress?.status !== "completed") ?? leaf.resources[0];
  return <section className="curriculum-node-overview">
    <p className="curriculum-node-overview__eyebrow">{leaf.chapter_title || "课程小节"}</p><h2>{leaf.title}</h2><p>{catalogLeafSummary(leaf)}</p>
    <div className="curriculum-node-overview__resource-grid">
      {leaf.resources.map((resource) => <button key={resource.material_id} type="button" onClick={() => onSelectResource(resource.material_id)}><span>{catalogResourceLabel(resource)}</span><small>{catalogResourceStatus(resource)}</small></button>)}
      {!leaf.resources.length ? <div className="catalog-empty-card">这个小节暂时还没有可用资料。</div> : null}
    </div>
    {mode === "manage" ? <button type="button" className="catalog-primary-action" onClick={onGenerate}><MaterialIcon name="auto_awesome" />生成或更新学习资源</button>
      : next ? <button type="button" className="catalog-primary-action" onClick={() => onSelectResource(next.material_id)}><MaterialIcon name="arrow_forward" />继续学习</button> : null}
  </section>;
}
