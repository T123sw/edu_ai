import type { PptOutlineSlide } from "../definitions/ppt";
import { lines } from "../forms/formFields";

export function PptOutlineEditor({ value, onChange, error }: { value: PptOutlineSlide[]; onChange: (value: PptOutlineSlide[]) => void; error?: string }) {
  const update = (index: number, patch: Partial<PptOutlineSlide>) => onChange(value.map((slide, current) => current === index ? { ...slide, ...patch } : slide));
  const move = (index: number, offset: number) => {
    const target = index + offset;
    if (target < 0 || target >= value.length) return;
    const next = [...value];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };
  return <fieldset className="ppt-outline-editor"><legend>PPT 逐页大纲</legend>{value.map((slide, index) => <section key={slide.id} className="ppt-outline-editor__slide" aria-label={`第 ${index + 1} 页大纲`}><header><strong>第 {index + 1} 页</strong><div><button type="button" aria-label={`第 ${index + 1} 页上移`} disabled={index === 0} onClick={() => move(index, -1)}>↑</button><button type="button" aria-label={`第 ${index + 1} 页下移`} disabled={index === value.length - 1} onClick={() => move(index, 1)}>↓</button><button type="button" aria-label={`删除第 ${index + 1} 页`} disabled={value.length === 1} onClick={() => onChange(value.filter((_, current) => current !== index))}>删除</button></div></header><label><span>页面标题 *</span><input value={slide.title} onChange={(event) => update(index, { title: event.target.value })} /></label><label><span>关键点（每行一项）</span><textarea value={slide.keyPoints.join("\n")} onChange={(event) => update(index, { keyPoints: lines(event.target.value) })} /></label><label><span>讲者备注</span><textarea value={slide.speakerNotes} onChange={(event) => update(index, { speakerNotes: event.target.value })} /></label><label><span>画面指令</span><input value={slide.visualInstruction} onChange={(event) => update(index, { visualInstruction: event.target.value })} /></label></section>)}<button type="button" className="ppt-outline-editor__add" onClick={() => onChange([...value, { id: `slide-${value.length + 1}-${Date.now()}`, title: "新页面", keyPoints: [], speakerNotes: "", visualInstruction: "" }])}>添加一页</button>{error ? <small role="alert">{error}</small> : null}</fieldset>;
}
