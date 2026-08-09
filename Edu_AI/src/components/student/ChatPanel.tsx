import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import { sendChatReply } from "../../stitch/api/chat";
import { MaterialIcon, cx } from "../../stitch/shared";

type Source = { title?: string; url?: string; file_name?: string; content?: string };
type Message = { id: string; role: "user" | "assistant"; content: string; sources?: Source[] };

export default function StudentChatPanel({
  courseId,
  selectedDocumentIds,
}: {
  courseId: string;
  selectedDocumentIds: readonly string[];
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [allowRag, setAllowRag] = useState(true);
  const [allowWeb, setAllowWeb] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const question = input.trim();
    if (!question || sending) return;
    const userMessage: Message = { id: `user-${Date.now()}`, role: "user", content: question };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setSending(true);
    setError(null);
    try {
      const response = await sendChatReply({
        question,
        conversation_id: conversationId,
        course_id: courseId,
        allow_rag: allowRag || selectedDocumentIds.length > 0,
        allow_web: allowWeb,
        selected_doc_ids: [...selectedDocumentIds],
      });
      const extended = response as typeof response & { sources?: Source[] };
      const answer = response.message?.content || response.answer || "本次回答没有返回可显示的正文。";
      setConversationId(response.conversation?.conversation_id || conversationId);
      setMessages((current) => [...current, { id: `assistant-${Date.now()}`, role: "assistant", content: answer, sources: extended.sources ?? [] }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提问失败，请稍后重试");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="student-chat-panel" aria-label="AI问答">
      <header><div><small>当前课程问答</small><h2>和 AI 一起理解课程</h2></div>{messages.length > 0 ? <button onClick={() => { setMessages([]); setConversationId(null); }}>新对话</button> : null}</header>
      <div className="student-chat-panel__messages" aria-live="polite">
        {messages.length === 0 ? (
          <div className="student-chat-panel__welcome"><span><MaterialIcon name="auto_awesome" /></span><h3>从一个具体问题开始</h3><p>可以选择左侧资料，让回答聚焦指定内容；课程资料和个人资料都不会改变其原有归属。</p></div>
        ) : messages.map((message) => (
          <article key={message.id} className={cx("student-chat-panel__message", `is-${message.role}`)}>
            <div className="student-chat-panel__avatar">{message.role === "user" ? "我" : "AI"}</div>
            <div className="student-chat-panel__bubble">
              {message.role === "assistant" ? <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>{message.content}</ReactMarkdown> : <p>{message.content}</p>}
              {message.sources?.length ? <div className="student-chat-panel__sources"><strong>参考来源</strong>{message.sources.map((source, index) => source.url ? <a key={`${source.url}-${index}`} href={source.url} target="_blank" rel="noreferrer">[{index + 1}] {source.title || source.file_name || source.url}</a> : <span key={index}>[{index + 1}] {source.title || source.file_name || "课程资料"}</span>)}</div> : null}
            </div>
          </article>
        ))}
        {sending ? <div className="student-chat-panel__thinking"><span /><span /><span /> 正在组织回答并核对来源…</div> : null}
      </div>
      {error ? <div className="student-chat-panel__error" role="alert">{error}</div> : null}
      <div className="student-chat-panel__composer">
        {selectedDocumentIds.length > 0 ? <p>本轮已选择 {selectedDocumentIds.length} 份资料</p> : null}
        <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} placeholder="输入问题，Shift + Enter 换行" disabled={sending} />
        <footer>
          <div><button className={cx(allowRag && "is-active")} aria-pressed={allowRag} onClick={() => setAllowRag((value) => !value)}>RAG知识库</button><button className={cx(allowWeb && "is-active")} aria-pressed={allowWeb} onClick={() => setAllowWeb((value) => !value)}>Web搜索</button></div>
          <button className="student-chat-panel__send" disabled={!input.trim() || sending} onClick={() => void send()} aria-label="发送问题"><MaterialIcon name="send" /></button>
        </footer>
      </div>
    </section>
  );
}
