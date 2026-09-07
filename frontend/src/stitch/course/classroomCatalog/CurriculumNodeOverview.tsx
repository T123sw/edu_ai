import type { ClassroomCatalogLeaf } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { catalogLeafSummary } from "./catalogPresentation";

type Props = { leaf: ClassroomCatalogLeaf | null; mode: "manage" | "learn"; totalLeafCount: number; onGenerate: () => void };
export function CurriculumNodeOverview({ leaf, mode, totalLeafCount, onGenerate }: Props) {
  return <section className="curriculum-node-overview">
    <header className="curriculum-overview-hero">
      <div className="curriculum-overview-hero__copy">
        <p className="curriculum-node-overview__eyebrow">{leaf?.chapter_title || "AI 课堂 · 课程学习空间"}</p>
        <h2>{leaf?.title || "让每一个知识点，都学得明白"}</h2>
        <p>{leaf ? "从课堂讲解到自主练习，在这里完成本节学习。" : "从左侧选择一个小节，开启讲解、阅读与练习相结合的学习之旅。"}</p>
        <span className="curriculum-overview-meta"><MaterialIcon name="account_tree" />{leaf ? catalogLeafSummary(leaf) : `${totalLeafCount} 个知识小节 · 按章节有序学习`}</span>
      </div>
      <div className="curriculum-overview-hero__art" aria-hidden="true"><span /><span /><MaterialIcon name="school" className="curriculum-hero-icon" /></div>
    </header>
    <footer className="curriculum-overview-footer"><div><MaterialIcon name="auto_awesome" /><p><strong>{mode === "manage" ? "准备好本节的学习内容" : "学习中的疑问，随时解答"}</strong><span>{mode === "manage" ? "生成资源后，预览内容并审核发布给学生。" : "打开学习资源后，可在右侧向 AI 提问。"}</span></p></div>
      {mode === "manage" ? <button type="button" className="catalog-primary-action" onClick={onGenerate}><MaterialIcon name="add" />{leaf ? "生成或更新学习资源" : "生成学习资源"}</button> : null}
    </footer>
  </section>;
}
