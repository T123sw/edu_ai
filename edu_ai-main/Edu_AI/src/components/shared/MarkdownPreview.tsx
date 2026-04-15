import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface MarkdownPreviewProps {
  content: string;
}

const MarkdownPreview: React.FC<MarkdownPreviewProps> = ({ content }) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          if (!inline && match) {
            return (
              <SyntaxHighlighter
                style={vscDarkPlus as any}
                language={match[1]}
                PreTag="div"
                customStyle={{
                  margin: 0,
                  borderRadius: 8,
                  padding: 12,
                  fontSize: 13,
                  lineHeight: 1.6,
                }}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            );
          }
          return (
            <code
              className={className}
              style={{
                background: '#f5f5f5',
                padding: '0 6px',
                borderRadius: 4,
                fontSize: 13,
              }}
              {...props}
            >
              {children}
            </code>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
};

export default MarkdownPreview;

