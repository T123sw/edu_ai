import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { normalizeQuizMarkdown } from './quizPresentation';
import './quiz.css';
import { useAuthenticatedBlobUrl } from '../stitch/api/useAuthenticatedBlobUrl';

function QuizImage({ src, alt }: { src: string; alt?: string }) {
  const asset = useAuthenticatedBlobUrl(src);
  return <span className="quiz-image">{asset.url ? <img src={asset.url} alt={alt || '习题插图'} loading="lazy" /> : <span>{asset.error ? '插图暂时无法加载' : '正在读取插图…'}</span>}</span>;
}

/** Quiz prose and code have their own layout, independent of report styling. */
export function QuizMarkdown({ content }: { content: string }) {
  return <div className="quiz-markdown"><ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}
    components={{
      img: ({ src, alt }) => src ? <QuizImage src={src} alt={alt} /> : null,
      pre: ({ children }) => <pre className="quiz-code">{children}</pre>,
      table: ({ children }) => <div className="quiz-table"><table>{children}</table></div>,
    }}>{normalizeQuizMarkdown(content)}</ReactMarkdown></div>;
}
