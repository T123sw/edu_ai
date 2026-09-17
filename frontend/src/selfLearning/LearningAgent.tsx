import { useAnswerTurns, type ReadingSnapshot } from '../liveLearning/agentTurns';
import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { agentReply, resourceEvidence, kindLabel, uid, updateRoom, type Classroom, type LearningResource, type LearningState, type Message } from "./model";
import { agentContext, chapterMessages, learningMemory } from "./learningMemory";
import { Icon } from "./ui";
import { useTopicSession } from '../liveLearning/learningClient';

export function LearningAgent({ room, resource, setState, onSelect, onEngage, onAsk, onSelfAssessment, selfAssessmentPending, readingSnapshot }: {
  room: Classroom; resource: LearningResource; setState: Dispatch<SetStateAction<LearningState>>;
  onSelect: (id: string) => void; onEngage: () => void;
  readingSnapshot?: ReadingSnapshot;
  onSelfAssessment?: (value: 'understood' | 'needs_review' | 'unset') => void;
  selfAssessmentPending?: boolean;
  onAsk?: (chapterId: string, resourceId: string, text: string) => Promise<void>;
}) {
  const chapter = room.chapters.find(c => c.resources.some(r => r.id === resource.id))!;
  const session = useTopicSession(room.id, chapter.id, !!room.sessionPersistence, room.sessionOwner || '');
  const turns = useAnswerTurns(room.id, chapter.id, !!room.agentRuntime, room.sessionOwner || '');
  const turnStatus = turns.turns.map(t => `${t.turn_id}:${t.status}`).join(',');
  useEffect(() => { if (room.agentRuntime) void session.refresh(); }, [turnStatus, room.agentRuntime]); // eslint-disable-line react-hooks/exhaustive-deps
  const messages = room.sessionPersistence ? session.messages : chapterMessages(room, chapter.id);
  const memory = learningMemory(room);
  const evidence = resourceEvidence(room, resource);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const error = errors[chapter.id];
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const conversation = useRef<HTMLDivElement>(null);
  const olderScrollHeight = useRef<number | null>(null);
  const question = drafts[chapter.id] || "";
  useEffect(() => {
    const el = conversation.current;
    if (el) el.scrollTop = olderScrollHeight.current === null ? el.scrollHeight : el.scrollHeight - olderScrollHeight.current;
    olderScrollHeight.current = null;
  }, [chapter.id, messages.length, pending]);
  useEffect(() => {
    const active = timers.current;
    return () => active.forEach(clearTimeout);
  }, []);
  function ask(text: string) {
    if (!text.trim() || pending[chapter.id] || turns.active || timers.current.has(chapter.id)) return;
    const capturedChapter = chapter.id;
    if (room.agentRuntime) {
      if (!readingSnapshot) { setErrors(s => ({ ...s, [capturedChapter]: '请先打开可用资料' })); return; }
      setPending(s => ({ ...s, [capturedChapter]: true })); onEngage();
      void turns.submit(text.trim(), structuredClone(readingSnapshot)).then(() => {
        setDrafts(s => ({ ...s, [capturedChapter]: '' })); setErrors(s => ({ ...s, [capturedChapter]: undefined }));
      }).catch(e => setErrors(s => ({ ...s, [capturedChapter]: e.message }))).finally(() => setPending(s => ({ ...s, [capturedChapter]: false })));
      return;
    }
    if (onAsk) {
      setPending(s => ({ ...s, [capturedChapter]: true })); setErrors(s => ({ ...s, [capturedChapter]: undefined })); onEngage();
      void onAsk(capturedChapter, resource.id, text.trim()).then(async () => {
        setDrafts(s => ({ ...s, [capturedChapter]: "" }));
      })
        .catch(cause => setErrors(s => ({ ...s, [capturedChapter]: cause instanceof Error ? cause.message : "发送失败，请重试" })))
        .finally(() => { setPending(s => ({ ...s, [capturedChapter]: false })); if (room.sessionPersistence) void session.refresh(); });
      return;
    }
    const context = agentContext(room, capturedChapter);
    const overview = context.memory.filter(m => m.chapterId !== capturedChapter && m.status !== "未开始");
    const recall = overview.length ? `其他知识点的学习记忆：${overview.map(m => `「${m.title}」${m.status}（${m.facts}）`).join("；")}。` : "其他知识点尚无学习记录，可以按目录逐步探索。";
    const answer = `${agentReply(room, resource, text.trim())}\n\n${recall}`;
    const message: Message = { id: uid(), role: "user", text: text.trim(), chapterId: capturedChapter, resourceId: resource.id, resourceTitle: resource.topic };
    setState(s => updateRoom(s, room.id, r => ({ ...r, messages: [...r.messages, message], updatedAt: Date.now() })));
    setDrafts(s => ({ ...s, [capturedChapter]: "" }));
    setPending(s => ({ ...s, [capturedChapter]: true }));
    onEngage();
    timers.current.set(capturedChapter, setTimeout(() => {
      setState(s => updateRoom(s, room.id, r => ({ ...r, messages: [...r.messages, { ...message, id: uid(), role: "assistant", text: answer }] })));
      timers.current.delete(capturedChapter);
      setPending(s => ({ ...s, [capturedChapter]: false }));
    }, 750));
  }
  return <aside className="sl-agent" aria-label="知识点对话">
    <div className="sl-rail-heading"><h2><span className="sl-agent-symbol"><Icon name="spark" size={18} /></span>学习 Agent</h2><span className="sl-local-tag">全程陪伴</span></div>
    <div className="sl-context">
      <span><i />当前知识点 · 独立会话</span>
      <select aria-label="对话知识点" value={chapter.id} onChange={e => onSelect(room.chapters.find(c => c.id === e.target.value)!.resources[0].id)}>{room.chapters.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select>
      <small>{resource.kind === "video" ? `讲解位置 00:${String(Math.floor(evidence.position)).padStart(2, "0")}` : kindLabel[resource.kind]} · {evidence.completed ? "已标记完成" : "学习中"}{evidence.answer !== undefined ? ` · 检查${evidence.answer === 1 ? "正确" : "待回顾"}` : ""}</small>
      <small>切换知识点自动保存，同一知识点内继续聊。</small>
    </div>
    <div className="sl-learning-memory">
      <button className="sl-memory-toggle" aria-expanded={memoryOpen} onClick={() => setMemoryOpen(!memoryOpen)}><Icon name="book" size={15} /><span>全局学习记忆<small>{memory.filter(m => m.status !== "未开始").length} / {memory.length} 个知识点有记录</small></span><Icon name="chevron" size={14} /></button>
      {memoryOpen && <div className="sl-memory-body" aria-label="全局学习记忆">
        <p>本课堂各知识点的学习摘要会共同提供给 Agent。完成记录与理解程度分别记录。</p>
        {memory.map(m => <div className={`sl-memory-item ${m.chapterId === chapter.id ? "current" : ""}`} key={m.chapterId}><strong>{m.title}<span>{m.status}</span></strong><small>{m.facts}</small></div>)}
        <label>当前知识点的理解程度<select aria-label="当前知识点的理解程度" disabled={selfAssessmentPending} value={room.understanding?.[chapter.id] || ""} onChange={e => {
          const value = e.target.value;
          if (onSelfAssessment) { onSelfAssessment(value === "review" ? "needs_review" : value === "understood" ? "understood" : "unset"); return; }
          setState(s => updateRoom(s, room.id, r => {
            const understanding = { ...r.understanding };
            if (value === "review" || value === "understood") understanding[chapter.id] = value;
            else delete understanding[chapter.id];
            return { ...r, understanding };
          }));
        }}><option value="">尚未自评</option><option value="review">还需巩固</option><option value="understood">我已理解</option></select></label>
        <small>理解程度来自你的自评，练习反馈单独保留。</small>
      </div>}
    </div>
    <div className="sl-chat-history" ref={conversation} role="log" aria-label="当前知识点对话记录" data-session-id={session.sessionId}>
      {session.hasOlder && <button disabled={session.loading} onClick={() => { olderScrollHeight.current = conversation.current?.scrollHeight ?? null; void session.loadOlder(); }}>加载更早的对话</button>}
      {!room.sessionPersistence && <div className="sl-chat-bubble assistant"><span className="sl-chat-author"><Icon name="spark" size={14} />学习 Agent</span><p>我会一直在这里，陪你学完这堂课。</p><p>现在我们聊「{chapter.title}」。你可以随时提问；回来时，这里的对话会接着保留。</p></div>}
      {messages.map(m => <div key={m.id} data-message-kind={m.kind} className={`sl-chat-bubble ${m.role}`}><span className="sl-chat-author">{m.role === "user" ? "你" : "学习 Agent"}<small>{m.resourceTitle}</small></span><p>{m.text}</p>{m.answerResult?.citations?.map(c => <small key={c.citation_id}>来源：{c.resource_ref.material_id} · v{c.resource_ref.version}</small>)}</div>)}
      {turns.active && <div role="status">{turns.active.stage === "reading_resources" ? "正在读取资料…" : turns.active.status === "accepted" ? "问题已接收，等待处理…" : "正在组织回答…"}<button onClick={() => void turns.control(turns.active!.turn_id, "cancel")}>取消本次答疑</button></div>}
      {pending[chapter.id] && <div className="sl-chat-thinking" role="status">{room.live ? "正在思考…" : "正在整理示例回复"}<span>•••</span></div>}
    </div>
    <div className="sl-chat-bottom">
      {room.agentRuntime && turns.turns[0]?.status === 'failed' && <p role="alert">本次答疑失败（{turns.turns[0].error_code}），可以继续阅读。<button onClick={() => void turns.control(turns.turns[0].turn_id, 'retry')}>重试本次答疑</button></p>}
      {room.agentRuntime && turns.error && <p role="alert">{turns.error}</p>}
      {error && <p className="sl-error" role="alert">{error}</p>}
      {room.sessionPersistence && session.error && <p className="sl-error" role="alert">{session.error}<button onClick={() => void session.retry()}>重新读取会话</button></p>}
      <div className="sl-quick-questions">{["举个例子", "接下来学什么？"].map(q => <button key={q} disabled={pending[chapter.id] || !!turns.active} onClick={() => ask(q)}>{q}</button>)}</div>
      <form className="sl-chat-composer" onSubmit={e => { e.preventDefault(); ask(question); }}><textarea aria-label="向学习 Agent 提问" placeholder="随时提问，一起梳理这个知识点…" value={question} maxLength={1000} onChange={e => setDrafts(s => ({ ...s, [chapter.id]: e.target.value }))} onFocus={onEngage} onKeyDown={e => {
        if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); ask(question); }
      }} /><button className="sl-send" aria-label="发送问题" disabled={!question.trim() || pending[chapter.id] || !!turns.active}><Icon name="arrow" size={18} /></button></form>
      <small>{room.live ? "对话自动保存到账号" : "本地示例回复"} · Enter 发送 / Shift + Enter 换行</small>
    </div>
  </aside>;
}
