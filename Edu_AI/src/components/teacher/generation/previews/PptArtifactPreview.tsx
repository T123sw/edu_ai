import { useMemo, useState } from "react";
import type { CourseMaterial } from "../../../../stitch/api/types";

type Slide = { title: string; bullets: string[]; notes: string };

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown): string {
  return typeof value === "string" || typeof value === "number"
    ? String(value).trim()
    : "";
}

function readSlides(material: CourseMaterial): Slide[] {
  const content = record(material.content);
  const source = Array.isArray(content.slides) ? content.slides : [];
  return source.map((item, index) => {
    const slide = record(item);
    const rawBullets = Array.isArray(slide.bullets)
      ? slide.bullets
      : Array.isArray(slide.key_points)
        ? slide.key_points
        : [];
    return {
      title: text(slide.title) || `第 ${index + 1} 页`,
      bullets: rawBullets.map(text).filter(Boolean),
      notes: text(slide.notes) || text(slide.speaker_notes),
    };
  });
}

export function PptArtifactPreview({ material }: { material: CourseMaterial }) {
  const slides = useMemo(() => readSlides(material), [material]);
  const [index, setIndex] = useState(0);
  const slide = slides[Math.min(index, Math.max(0, slides.length - 1))];

  if (!slide) {
    return <p className="resource-preview-empty">当前 PPT 暂无可展示的页面内容。</p>;
  }

  return (
    <section className="ppt-artifact-preview" aria-label="PPT 分页预览">
      <div className="ppt-artifact-preview__slide">
        <span className="ppt-artifact-preview__number">第 {index + 1} 页</span>
        <h3>{slide.title}</h3>
        {slide.bullets.length ? (
          <ul>{slide.bullets.map((item, itemIndex) => <li key={`${itemIndex}-${item}`}>{item}</li>)}</ul>
        ) : <p>此页暂无要点。</p>}
        {slide.notes ? <aside><strong>讲解备注</strong><p>{slide.notes}</p></aside> : null}
      </div>
      <div className="ppt-artifact-preview__pager">
        <button type="button" onClick={() => setIndex((value) => Math.max(0, value - 1))} disabled={index === 0}>上一页</button>
        <span>{index + 1} / {slides.length}</span>
        <button type="button" onClick={() => setIndex((value) => Math.min(slides.length - 1, value + 1))} disabled={index >= slides.length - 1}>下一页</button>
      </div>
    </section>
  );
}
