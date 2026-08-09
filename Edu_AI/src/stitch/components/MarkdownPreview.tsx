import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useAuthenticatedBlobUrl } from "../api/useAuthenticatedBlobUrl";
import { normalizeKnowledgeMarkdown } from "./knowledgeMarkdown";

type MarkdownPreviewProps = {
  content: string;
  imageUrls?: Record<string, string>;
};

function MarkdownImage({ src, alt }: { src: string; alt?: string }) {
  const asset = useAuthenticatedBlobUrl(src);
  return (
    <figure className="my-5 overflow-hidden rounded-2xl border border-(--app-border) bg-(--surface-subtle) p-3 text-center">
      {asset.loading ? <p className="py-8 text-sm text-(--app-text-muted)">图片加载中…</p> : null}
      {asset.error ? <p role="alert" className="py-8 text-sm text-red-600">图片加载失败：{asset.error}</p> : null}
      {asset.url ? <img src={asset.url} alt={alt || "教学插图"} className="mx-auto max-h-[520px] max-w-full object-contain" loading="lazy" /> : null}
      {alt && <figcaption className="mt-2 text-xs text-(--app-text-muted)">{alt}</figcaption>}
    </figure>
  );
}

export function MarkdownPreview({ content, imageUrls = {} }: MarkdownPreviewProps) {
  return (
    <div className="markdown-preview text-sm leading-7 text-(--app-text)">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          img({ src, alt }) {
            const resolved = src ? (imageUrls[src] || src) : "";
            return resolved ? <MarkdownImage src={resolved} alt={alt || undefined} /> : null;
          },
          table({ children }) {
            return <div className="my-5 overflow-x-auto"><table className="min-w-full border-collapse">{children}</table></div>;
          },
          th({ children }) {
            return <th className="border border-(--app-border) bg-(--surface-subtle) px-3 py-2 text-left">{children}</th>;
          },
          td({ children }) {
            return <td className="border border-(--app-border) px-3 py-2 align-top">{children}</td>;
          },
          code(props) {
            const { className, children } = props;
            const match = /language-(\w+)/.exec(className || "");

            if (match) {
              return (
                <SyntaxHighlighter
                  style={vscDarkPlus as never}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{
                    margin: "16px 0",
                    borderRadius: "18px",
                    padding: "16px",
                    fontSize: "13px",
                    lineHeight: "1.65",
                    background: "#0f172a",
                  }}
                >
                  {String(children).replace(/\n$/, "")}
                </SyntaxHighlighter>
              );
            }

            return <code className="rounded-md bg-(--surface-subtle) px-1.5 py-1 text-[12px]">{children}</code>;
          },
        }}
      >
        {normalizeKnowledgeMarkdown(content)}
      </ReactMarkdown>
    </div>
  );
}
