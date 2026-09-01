import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface MarkdownPreviewProps {
  content: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';
const AUTH_STORAGE_KEY = 'edu-ai-auth';

function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as { token?: string };
    return parsed.token || null;
  } catch {
    return null;
  }
}

function isProtectedApiImage(src: string): boolean {
  return src.startsWith('/api/images/searched/') || src.startsWith('/api/rag/image');
}

function resolveApiUrl(src: string): string {
  if (/^https?:\/\//i.test(src)) return src;
  return `${API_BASE_URL}${src.startsWith('/') ? src : `/${src}`}`;
}

function MarkdownImage({ src, alt }: { src?: string; alt?: string }) {
  const rawSrc = String(src || '').trim();
  const [displaySrc, setDisplaySrc] = useState(rawSrc);

  useEffect(() => {
    if (!rawSrc || !isProtectedApiImage(rawSrc)) {
      setDisplaySrc(rawSrc);
      return;
    }

    const token = getAuthToken();
    if (!token) {
      setDisplaySrc(rawSrc);
      return;
    }

    let objectUrl = '';
    let cancelled = false;
    fetch(resolveApiUrl(rawSrc), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => {
        if (!response.ok) throw new Error(`image load failed: ${response.status}`);
        return response.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setDisplaySrc(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setDisplaySrc(rawSrc);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [rawSrc]);

  if (!rawSrc) return null;

  return (
    <img
      src={displaySrc}
      alt={alt || ''}
      style={{
        maxWidth: '100%',
        maxHeight: '52vh',
        objectFit: 'contain',
        display: 'block',
        margin: '16px auto',
        borderRadius: 8,
        background: '#f5f5f5',
      }}
    />
  );
}

const MarkdownPreview: React.FC<MarkdownPreviewProps> = ({ content }) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        img({ src, alt }) {
          return <MarkdownImage src={src} alt={alt} />;
        },
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

