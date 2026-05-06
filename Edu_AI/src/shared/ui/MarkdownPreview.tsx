import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

export function MarkdownPreview({ content }: { content: string }) {
  return (
    <div className="markdown-preview text-sm leading-7 text-[var(--app-text)]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
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

            return <code className="rounded-md bg-[var(--surface-subtle)] px-1.5 py-1 text-[12px]">{children}</code>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
