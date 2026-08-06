import { useMemo, useState } from "react";
import { BlogArtifactPreview } from "../../components/teacher/generation/previews/BlogArtifactPreview";
import { PptArtifactPreview } from "../../components/teacher/generation/previews/PptArtifactPreview";
import { courseMaterialToMarkdown } from "../api/courses";
import type { CourseMaterial } from "../api/types";
import { MarkdownPreview } from "../components/MarkdownPreview";
import { getCourseMaterialPreviewKind } from "./resourcePreviewConstraints";

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

function QuizPreview({ material }: { material: CourseMaterial }) {
  const questions = Array.isArray(material.questions) ? material.questions : [];
  return (
    <div className="resource-quiz-preview">
      {questions.length ? questions.map((question, index) => (
        <article key={question.id || index}>
          <span>第 {index + 1} 题</span>
          <h3>{question.stem || "未命名题目"}</h3>
          {question.options?.length ? <ol>{question.options.map((option) => <li key={option}>{option}</li>)}</ol> : null}
          <details><summary>查看答案与解析</summary><p><strong>答案：</strong>{question.answer || "未提供"}</p>{question.explanation ? <p><strong>解析：</strong>{question.explanation}</p> : null}</details>
        </article>
      )) : <p className="resource-preview-empty">当前习题暂无可展示的题目。</p>}
    </div>
  );
}

function FlashcardPreview({ material }: { material: CourseMaterial }) {
  const content = record(material.content);
  const cards = Array.isArray(material.flashcards)
    ? material.flashcards
    : Array.isArray(content.cards)
      ? content.cards.map(record)
      : [];
  const [flipped, setFlipped] = useState<Record<number, boolean>>({});
  return (
    <div className="resource-flashcard-grid">
      {cards.length ? cards.map((rawCard, index) => {
        const card = record(rawCard);
        const front = text(card.front) || text(card.question) || "未命名卡片";
        const back = text(card.back) || text(card.answer) || "暂无答案";
        return <button key={index} type="button" aria-pressed={Boolean(flipped[index])} onClick={() => setFlipped((value) => ({ ...value, [index]: !value[index] }))}><small>{flipped[index] ? "背面" : "正面"}</small><strong>{flipped[index] ? back : front}</strong><span>点击翻面</span></button>;
      }) : <p className="resource-preview-empty">当前闪卡暂无可展示内容。</p>}
    </div>
  );
}

type MindNode = { title?: string; summary?: string; children?: MindNode[] };

function MindBranch({ node, depth = 0 }: { node: MindNode; depth?: number }) {
  return <li><span><strong>{node.title || "未命名节点"}</strong>{node.summary ? <small>{node.summary}</small> : null}</span>{node.children?.length ? <ul>{node.children.map((child, index) => <MindBranch key={`${child.title}-${index}`} node={child} depth={depth + 1} />)}</ul> : null}</li>;
}

function MindMapPreview({ material }: { material: CourseMaterial }) {
  const payload = record(material.content);
  const root = record(payload.root) as MindNode;
  const hasRoot = Boolean(root.title || root.children?.length);
  const [zoom, setZoom] = useState(1);
  return <section className="resource-mind-map"><div className="resource-mind-map__controls"><button type="button" onClick={() => setZoom((value) => Math.max(0.6, value - 0.2))}>缩小</button><span>{Math.round(zoom * 100)}%</span><button type="button" onClick={() => setZoom((value) => Math.min(1.8, value + 0.2))}>放大</button><button type="button" onClick={() => setZoom(1)}>复位</button></div><div className="resource-mind-map__viewport"><div style={{ transform: `scale(${zoom})` }}>{hasRoot ? <ul><MindBranch node={root} /></ul> : <p className="resource-preview-empty">当前思维导图暂无节点。</p>}</div></div></section>;
}

function GamePreview({ material }: { material: CourseMaterial }) {
  const url = material.html_url || text(record(material.content).html_url);
  return url ? <div className="resource-game-preview"><iframe title={material.title || "小游戏预览"} src={url} sandbox="allow-scripts allow-forms" /><a href={url} target="_blank" rel="noreferrer">在新窗口打开小游戏</a></div> : <p className="resource-preview-empty">小游戏页面尚未生成，请稍后重试。</p>;
}

export function CourseMaterialArtifactPreview({ material }: { material: CourseMaterial }) {
  const previewKind = getCourseMaterialPreviewKind(material);
  const markdown = useMemo(() => courseMaterialToMarkdown(material), [material]);
  if (previewKind === "blog") return <BlogArtifactPreview material={material} markdown={markdown} />;
  if (previewKind === "ppt") return <PptArtifactPreview material={material} />;
  if (previewKind === "quiz") return <QuizPreview material={material} />;
  if (previewKind === "flashcard") return <FlashcardPreview material={material} />;
  if (previewKind === "mind-map") return <MindMapPreview material={material} />;
  if (previewKind === "game") return <GamePreview material={material} />;
  if (previewKind === "rich-text") return <div className="edu-rich-preview"><MarkdownPreview content={markdown} /></div>;
  return <div className="resource-preview-empty"><strong>暂无专用预览</strong><p>该资源仍保留在课程资源列表中，不会跳转到错误页面。</p></div>;
}
