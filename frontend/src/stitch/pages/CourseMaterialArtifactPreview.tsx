import { useMemo } from "react";
import { FlashcardRound } from "../../components/flashcards/FlashcardRound";
import { studyCards } from "../../components/flashcards/round";
import { PodcastPreview, ScenarioPreview } from "../../studio/LearningResourcePreview";
import { BlogArtifactPreview } from "../../components/generation/previews/BlogArtifactPreview";
import { MindMapCanvas, type MindMapNode } from "../../components/mindmap/MindMapCanvas";
import { courseMaterialToMarkdown } from "../api/courses";
import type { CourseMaterial } from "../api/types";
import { useAuthenticatedBlobUrl } from "../api/useAuthenticatedBlobUrl";
import { MarkdownPreview } from "../components/MarkdownPreview";
import { getQuizQuestions } from "./courseMaterialPreviewData";
import { getCourseMaterialPreviewKind } from "./resourcePreviewConstraints";
import { downloadMindMapJson } from "./mindMapExport";
import { downloadMaterialFile } from "./materialExport";

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

function QuizPreview({ material }: { material: CourseMaterial }) {
  const questions = getQuizQuestions(material);
  return (
    <div className="resource-quiz-preview">
      {questions.length ? questions.map((question, index) => (
        <article key={question.id || index}>
          <span>第 {index + 1} 题</span>
          <h3>{question.stem || "未命名题目"}</h3>
          {question.options?.length ? <ol style={{ listStyleType: "upper-alpha", paddingLeft: "1.5rem" }}>{question.options.map((option) => <li key={option}>{option}</li>)}</ol> : null}
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
  return <FlashcardRound cards={studyCards(cards)} />;
}

function MindMapPreview({ material }: { material: CourseMaterial }) {
  const payload = record(material.content);
  const candidate = record(payload.root) as MindMapNode;
  const root = candidate.title || candidate.children?.length ? candidate : null;
  return <MindMapCanvas root={root} label={material.title || "思维导图"} onExport={root ? () => downloadMindMapJson(material.content, material.title || "思维导图") : undefined} />;
}

function GamePreview({ material }: { material: CourseMaterial }) {
  const url = material.html_url || text(record(material.content).html_url);
  const asset = useAuthenticatedBlobUrl(url);
  if (!url) return <p className="resource-preview-empty">小游戏页面尚未生成，请稍后重试。</p>;
  if (asset.loading) return <p className="resource-preview-empty">小游戏加载中…</p>;
  if (asset.error || !asset.url) return <p role="alert" className="resource-preview-empty">小游戏加载失败，请稍后重试。</p>;
  return <div className="resource-game-preview"><iframe title={material.title || "小游戏预览"} src={asset.url} sandbox="allow-scripts allow-forms" /><a href={asset.url} target="_blank" rel="noreferrer">在新窗口打开小游戏</a></div>;
}

export function CourseMaterialArtifactPreview({ material, onReference, readingAnchors = false }: { material: CourseMaterial; onReference?: () => void; readingAnchors?: boolean }) {
  const previewKind = getCourseMaterialPreviewKind(material);
  const markdown = useMemo(() => courseMaterialToMarkdown(material), [material]);
  const exportButton = <><button type="button" onClick={() => downloadMaterialFile(material, markdown)} className="rounded-full border border-(--shell-border) bg-white px-4 py-2 text-sm font-bold">导出</button>{onReference && <button type="button" onClick={onReference} className="ml-2 rounded-full border border-(--shell-border) bg-white px-4 py-2 text-sm font-bold">引用</button>}</>;
  if (previewKind === "podcast") return <PodcastPreview key={`${material.material_id}:${material.version}`} material={material} />;
  if (previewKind === "scenario") return <ScenarioPreview key={`${material.material_id}:${material.version}`} material={material} />;
  if (previewKind === "blog") return <><div className="mb-3 flex justify-end">{exportButton}</div><BlogArtifactPreview material={material} markdown={markdown} /></>;
  if (previewKind === "quiz") return <><div className="mb-3 flex justify-end">{exportButton}</div><QuizPreview key={`${material.material_id}:${material.version}`} material={material} /></>;
  if (previewKind === "flashcard") return <>{onReference && <div className="mb-3 flex justify-end"><button type="button" onClick={onReference} className="rounded-full border border-(--shell-border) bg-white px-4 py-2 text-sm font-bold">引用</button></div>}<FlashcardPreview key={`${material.material_id}:${material.version}`} material={material} /></>;
  if (previewKind === "mind-map") return <>{onReference && <div className="mb-3 flex justify-end"><button type="button" onClick={onReference} className="rounded-full border border-(--shell-border) bg-white px-4 py-2 text-sm font-bold">引用</button></div>}<MindMapPreview key={`${material.material_id}:${material.version}`} material={material} /></>;
  if (previewKind === "game") return <><div className="mb-3 flex justify-end">{exportButton}</div><GamePreview material={material} /></>;
  if (previewKind === "rich-text") return <div className="edu-rich-preview resource-text-preview"><div className="resource-text-actions">{exportButton}</div><MarkdownPreview content={markdown} readingAnchors={readingAnchors} /></div>;
  return <div className="resource-preview-empty"><strong>暂无专用预览</strong><p>此资源暂时无法在线预览，请选择其他资源。</p></div>;
}
