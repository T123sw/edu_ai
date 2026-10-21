import { AgentComposer } from './AgentComposer';
import { citationUrl } from '../liveLearning/citationNavigation';
import '../liveLearning/reportReading.css';
import ReactMarkdown from 'react-markdown';
import { useAnswerTurns, answerErrorMessage, type ReadingSnapshot } from '../liveLearning/agentTurns';
import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { agentReply, uid, updateRoom, type Classroom, type LearningResource, type LearningState, type Message } from "./model";
import { agentContext } from "./learningMemory";
import { Icon } from "./ui";
import { useCourseSession } from '../liveLearning/learningClient';

export function LearningAgent({ room, resource, setState, onEngage, onAsk, readingSnapshot, referenceRequest = 0, onClearReference }: {
  room: Classroom; resource: LearningResource; setState: Dispatch<SetStateAction<LearningState>>;
  onSelect: (id: string) => void; onEngage: () => void;
  readingSnapshot?: ReadingSnapshot;
  referenceRequest?: number;
  onClearReference?: () => void;
  onSelfAssessment?: (value: 'understood' | 'needs_review' | 'unset') => void;
  selfAssessmentPending?: boolean;
  onAsk?: (chapterId: string, resourceId: string, text: string) => Promise<void>;
}) {
  const chapter = room.chapters.find(c => c.resources.some(r => r.id === resource.id))!;
  const session = useCourseSession(room.id, chapter.id, !!room.sessionPersistence, room.sessionOwner || '');
  const turns = useAnswerTurns(room.id, chapter.id, !!room.agentRuntime, room.sessionOwner || '');
  const turnStatus = turns.turns.map(t => `${t.turn_id}:${t.status}`).join(',');
  useEffect(() => { if (room.agentRuntime) void session.refresh(); }, [turnStatus, room.agentRuntime]); // eslint-disable-line react-hooks/exhaustive-deps
  const messages = room.sessionPersistence ? session.messages : room.messages;
  const conversationKey = JSON.stringify([room.sessionOwner, room.id]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const error = errors[conversationKey];
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const conversation = useRef<HTMLDivElement>(null);
  const olderScrollHeight = useRef<number | null>(null);
  const question = drafts[conversationKey] || "";
  const composer = useRef<HTMLTextAreaElement>(null);
  const referenceKind = useRef(readingSnapshot?.locator?.kind);
  const referencePrompt = useRef(readingSnapshot?.question_prompt);
  referencePrompt.current = readingSnapshot?.question_prompt;
  referenceKind.current = readingSnapshot?.locator?.kind;
  const referenceTopic = useRef(conversationKey);
  referenceTopic.current = conversationKey;
  useEffect(() => {
    if (!referenceRequest) return;
    const topic = referenceTopic.current;
    setDrafts(s => ({ ...s, [topic]: referencePrompt.current || s[topic] || (referenceKind.current === 'quiz' ? '请解释这道题。' : '请解释这段内容。') }));
    composer.current?.focus();
  }, [referenceRequest]);
  useEffect(() => {
    const el = conversation.current;
    if (el) el.scrollTop = olderScrollHeight.current === null ? el.scrollHeight : el.scrollHeight - olderScrollHeight.current;
    olderScrollHeight.current = null;
  }, [conversationKey, messages.length, pending]);
  useEffect(() => {
    const active = timers.current;
    return () => active.forEach(clearTimeout);
  }, []);
  function ask(text: string) {
    if (!text.trim() || pending[conversationKey] || turns.active || timers.current.has(conversationKey)) return;
    const capturedChapter = chapter.id;
    if (room.agentRuntime) {
      if (!readingSnapshot) { setErrors(s => ({ ...s, [conversationKey]: '请先打开可用资料' })); return; }
      setPending(s => ({ ...s, [conversationKey]: true })); onEngage();
      void turns.submit(text.trim(), structuredClone(readingSnapshot)).then(() => {
        setDrafts(s => ({ ...s, [conversationKey]: '' })); setErrors(s => ({ ...s, [conversationKey]: undefined }));
      }).catch(e => setErrors(s => ({ ...s, [conversationKey]: e.message }))).finally(() => setPending(s => ({ ...s, [conversationKey]: false })));
      return;
    }
    if (onAsk) {
      setPending(s => ({ ...s, [conversationKey]: true })); setErrors(s => ({ ...s, [conversationKey]: undefined })); onEngage();
      void onAsk(capturedChapter, resource.id, text.trim()).then(async () => {
        setDrafts(s => ({ ...s, [conversationKey]: "" }));
      })
        .catch(cause => setErrors(s => ({ ...s, [conversationKey]: cause instanceof Error ? cause.message : "发送失败，请重试" })))
        .finally(() => { setPending(s => ({ ...s, [conversationKey]: false })); if (room.sessionPersistence) void session.refresh(); });
      return;
    }
    const context = agentContext(room, capturedChapter);
    const overview = context.memory.filter(m => m.chapterId !== capturedChapter && m.status !== "未开始");
    const recall = overview.length ? `其他知识点的学习记忆：${overview.map(m => `「${m.title}」${m.status}（${m.facts}）`).join("；")}。` : "其他知识点尚无学习记录，可以按目录逐步探索。";
    const answer = `${agentReply(room, resource, text.trim())}\n\n${recall}`;
    const message: Message = { id: uid(), role: "user", text: text.trim(), chapterId: capturedChapter, resourceId: resource.id, resourceTitle: resource.topic };
    setState(s => updateRoom(s, room.id, r => ({ ...r, messages: [...r.messages, message], updatedAt: Date.now() })));
    setDrafts(s => ({ ...s, [conversationKey]: "" }));
    setPending(s => ({ ...s, [conversationKey]: true }));
    onEngage();
    timers.current.set(conversationKey, setTimeout(() => {
      setState(s => updateRoom(s, room.id, r => ({ ...r, messages: [...r.messages, { ...message, id: uid(), role: "assistant", text: answer }] })));
      timers.current.delete(conversationKey);
      setPending(s => ({ ...s, [conversationKey]: false }));
    }, 750));
  }
  return <aside className="sl-agent" aria-label="课程对话">
    <div className="sl-rail-heading"><h2><span className="sl-agent-symbol"><Icon name="spark" size={18} /></span>学习 Agent</h2><span className="sl-local-tag">全程陪伴</span></div>
    <div className="sl-chat-history" ref={conversation} role="log" aria-label="当前课程对话记录" data-session-id={session.sessionId}>
      {session.hasOlder && <button disabled={session.loading} onClick={() => { olderScrollHeight.current = conversation.current?.scrollHeight ?? null; void session.loadOlder(); }}>加载更早的对话</button>}
      {!room.sessionPersistence && <div className="sl-chat-bubble assistant"><span className="sl-chat-author"><Icon name="spark" size={14} />学习 Agent</span><p>我会一直在这里，陪你学完这堂课。</p><p>现在我们聊「{chapter.title}」。你可以随时提问；回来时，这里的对话会接着保留。</p></div>}
      {messages.map(m => <div key={m.id} data-message-kind={m.kind} className={`sl-chat-bubble ${m.role}`}><span className="sl-chat-author">{m.role === "user" ? "你" : "学习 Agent"}<small>{m.resourceTitle}</small></span>{m.answerResult ? <ReactMarkdown>{m.text}</ReactMarkdown> : <p>{m.text}</p>}{m.answerResult?.citations?.map(c => <small key={c.citation_id}><a target="_blank" rel="noopener noreferrer" href={citationUrl(c)}>来源：{c.title || c.resource_ref.material_id} · v{c.resource_ref.version}</a></small>)}</div>)}
      {turns.active && <div role="status">{turns.active.stage === "reading_resources" ? "正在读取资料…" : turns.active.status === "accepted" ? "问题已接收，等待处理…" : "正在组织回答…"}</div>}
      {pending[conversationKey] && <div className="sl-chat-thinking" role="status">{room.live ? "正在思考…" : "正在整理示例回复"}<span>•••</span></div>}
    </div>
    <div className="sl-chat-bottom">
      {turns.turns[0]?.committed_effects?.length && ['failed', 'canceled'].includes(turns.turns[0].status) ? <p role="status">本轮已有操作已保存；答疑未完成不会撤销这些操作。</p> : null}
      {room.agentRuntime && turns.turns[0]?.status === 'failed' && <p role="alert">{answerErrorMessage(turns.turns[0].error_code)}<button onClick={() => void turns.control(turns.turns[0].turn_id, 'retry')}>重试本次答疑</button></p>}
      {room.agentRuntime && turns.error && <p role="alert">{turns.error}</p>}
      {error && <p className="sl-error" role="alert">{error}</p>}
      {room.sessionPersistence && session.error && <p className="sl-error" role="alert">{session.error}<button onClick={() => void session.retry()}>重新读取会话</button></p>}
      <div className="sl-quick-questions">{["举个例子", "接下来学什么？"].map(q => <button key={q} disabled={pending[conversationKey] || !!turns.active} onClick={() => ask(q)}>{q}</button>)}</div>
      {room.agentRuntime && readingSnapshot?.selected_text && <div className="sl-reference-card" role="note" aria-label="已引用报告片段">
        <strong>{readingSnapshot.practice?.draft ? '已引用未提交的作答草稿' : readingSnapshot.practice?.attempt_id ? '已引用这次提交的作答' : '将结合选中文本回答'}</strong><span> · {resource.title}</span>
        <button type="button" aria-label="取消引用" onClick={onClearReference}>×</button>
        <blockquote>{readingSnapshot.selected_text}</blockquote>
      </div>}
      <AgentComposer inputRef={composer} value={question} onChange={value => setDrafts(s => ({ ...s, [conversationKey]: value }))} onSend={() => ask(question)} onFocus={onEngage} disabled={!!pending[conversationKey] || !!turns.active} placeholder="随时提问，一起梳理这个知识点…" />
      <small>{room.live ? "对话自动保存到账号" : "本地示例回复"} · Enter 发送 / Shift + Enter 换行</small>
    </div>
  </aside>;
}
