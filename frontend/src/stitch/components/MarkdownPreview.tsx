import { reportAnchors } from "../../components/shared/reportAnchors";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import SyntaxHighlighter from "react-syntax-highlighter/dist/esm/prism";
import vscDarkPlus from "react-syntax-highlighter/dist/esm/styles/prism/vsc-dark-plus";
import { useAuthenticatedBlobUrl } from "../api/useAuthenticatedBlobUrl";
import { normalizeKnowledgeMarkdown } from "./knowledgeMarkdown";
import { reportReadingAnchors } from '../../liveLearning/reportReading';
import './markdownPreview.css';

type MarkdownPreviewProps = {
  content: string;
  imageUrls?: Record<string, string>;
  readingAnchors?: boolean;
};

function MarkdownImage({ src, alt }: { src: string; alt?: string }) {
  const asset = useAuthenticatedBlobUrl(src);
  return (
    <span className="my-5 block overflow-hidden rounded-2xl border border-(--app-border) bg-(--surface-subtle) p-3 text-center">
      {asset.loading ? <span className="block py-8 text-sm text-(--app-text-muted)">图片加载中…</span> : null}
      {asset.error ? <span role="alert" className="block py-8 text-sm text-red-600">图片加载失败：{asset.error}</span> : null}
      {asset.url ? <img src={asset.url} alt={alt || "教学插图"} className="mx-auto block max-h-[520px] max-w-full object-contain" loading="lazy" /> : null}
      {alt && <span className="mt-2 block text-xs text-(--app-text-muted)">{alt}</span>}
    </span>
  );
}

export function MarkdownPreview({ content, imageUrls = {}, readingAnchors = false }: MarkdownPreviewProps) {
  return (
    <div className="markdown-preview markdown-document">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[reportAnchors, ...(readingAnchors ? [reportReadingAnchors] : []), rehypeKatex]}
        components={{
          img({ src, alt }) {
            const resolved = src ? (imageUrls[src] || src) : "";
            return resolved ? <MarkdownImage src={resolved} alt={alt || undefined} /> : null;
          },
          table({ children, node: _node, ...props }) {
            return <div className="markdown-table-scroll" tabIndex={0} role="region" aria-label="表格，可横向滚动"><table {...props}>{children}</table></div>;
          },
          th({ children, node: _node, ...props }) {
            return <th {...props}>{children}</th>;
          },
          td({ children, node: _node, ...props }) {
            return <td {...props}>{children}</td>;
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
