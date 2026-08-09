import type { CourseMaterial } from "../../../stitch/api/types";
import { MarkdownPreview } from "../../../stitch/components/MarkdownPreview";

export function BlogArtifactPreview({
  material,
  markdown,
}: {
  material: CourseMaterial;
  markdown: string;
}) {
  return (
    <article className="edu-rich-preview generation-blog-preview">
      <header className="generation-blog-preview__header">
        <span>教学博客</span>
        <h3>{material.title || material.topic || "未命名教学博客"}</h3>
        {material.summary ? <p>{material.summary}</p> : null}
      </header>
      <MarkdownPreview content={markdown} />
    </article>
  );
}
