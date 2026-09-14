import {
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  agentReply,
  allResources,
  completion,
  emptyEvidence,
  kindLabel,
  uid,
  updateEvidence,
  updateRoom,
  type Classroom as Room,
  type LearningState,
  type Message,
} from "./model";
import { LearningContent } from "./Content";
import { Icon } from "./ui";

export function Classroom({
  room,
  resourceId,
  setState,
  onSelect,
}: {
  room: Room;
  resourceId?: string;
  setState: Dispatch<SetStateAction<LearningState>>;
  onSelect: (id: string) => void;
}) {
  const resources = allResources(room);
  const resource =
    resources.find((r) => r.id === resourceId) ||
    resources.find((r) => r.id === room.selectedId) ||
    resources[0];
  const [panel, setPanel] = useState("learn");
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [chatActive, setChatActive] = useState(false);
  const conversation = useRef<HTMLDivElement>(null);
  const reading = useRef<HTMLDivElement>(null);
  const replyTimer = useRef<ReturnType<typeof setTimeout>>();
  const evidence = room.progress[resource.id] || emptyEvidence();
  const index = resources.findIndex((r) => r.id === resource.id);
  useEffect(() => {
    setState((s) =>
      updateRoom(s, room.id, (r) =>
        r.selectedId === resource.id
          ? r
          : { ...r, selectedId: resource.id, updatedAt: Date.now() },
      ),
    );
  }, [room.id, resource.id, setState]);
  useEffect(() => {
    const element = reading.current;
    if (element && resource.kind === "report")
      element.scrollTop =
        evidence.position; /* Restore only when opening a resource. */
  }, [resource.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const el = conversation.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [room.messages.length, pending]);
  useEffect(() => () => clearTimeout(replyTimer.current), []);
  function patch(value: Partial<typeof evidence>) {
    setState((s) => updateEvidence(s, room.id, resource.id, value));
  }
  function select(id: string) {
    setChatActive(false);
    onSelect(id);
    setPanel("learn");
  }
  function ask(text: string) {
    if (!text.trim() || pending) return;
    const captured = resource;
    const answer = agentReply(room, captured, text.trim());
    const message: Message = {
      id: uid(),
      role: "user",
      text: text.trim(),
      resourceId: captured.id,
      resourceTitle: captured.topic,
    };
    setState((s) =>
      updateRoom(s, room.id, (r) => ({
        ...r,
        messages: [...r.messages, message],
      })),
    );
    setQuestion("");
    setPending(true);
    setChatActive(true);
    replyTimer.current = setTimeout(() => {
      setState((s) =>
        updateRoom(s, room.id, (r) => ({
          ...r,
          messages: [
            ...r.messages,
            { ...message, id: uid(), role: "assistant", text: answer },
          ],
        })),
      );
      setPending(false);
    }, 750);
  }
  return (
    <main className={`sl-classroom panel-${panel}`}>
      <nav className="sl-mobile-panels" aria-label="课堂面板">
        {[
          ["directory", "menu", "目录"],
          ["learn", "book", "学习"],
          ["agent", "chat", "Agent"],
        ].map(([id, icon, label]) => (
          <button
            key={id}
            className={panel === id ? "active" : ""}
            onClick={() => setPanel(id)}
            aria-pressed={panel === id}
          >
            <Icon name={icon} size={17} />
            {label}
          </button>
        ))}
      </nav>
      <aside className="sl-directory">
        <div className="sl-rail-heading">
          <h2>课堂目录</h2>
          <span>{room.chapters.length} 个主题</span>
        </div>
        <div className="sl-route-progress">
          <div>
            <span>你的学习旅程</span>
            <strong>
              {completion(room)} <small>/ {resources.length}</small>
            </strong>
          </div>
          <div className="sl-progress-track">
            <i
              style={{
                width: `${(completion(room) / resources.length) * 100}%`,
              }}
            />
          </div>
        </div>
        <div className="sl-directory-scroll">
          {room.chapters.map((chapter, n) => (
            <section key={chapter.id}>
              <h3>
                <span>{String(n + 1).padStart(2, "0")}</span>
                {chapter.title}
              </h3>
              {chapter.resources.map((r) => (
                <button
                  key={r.id}
                  className={`sl-resource-row ${r.id === resource.id ? "active" : ""}`}
                  onClick={() => select(r.id)}
                  aria-current={r.id === resource.id ? "page" : undefined}
                  aria-label={r.title}
                >
                  <Icon name={r.kind} size={17} />
                  <span>
                    {kindLabel[r.kind]}
                    <small>{r.ready ? `${r.minutes} 分钟` : "正在准备"}</small>
                  </span>
                  {room.progress[r.id]?.completed ? (
                    <span className="sl-done">
                      <Icon name="check" size={15} />
                    </span>
                  ) : r.id === resource.id ? (
                    <span className="sl-current-dot" />
                  ) : null}
                </button>
              ))}
            </section>
          ))}
        </div>
        <a href={`#/studio?classroom=${room.id}`} className="sl-rail-studio">
          <Icon name="studio" size={17} />
          <span>
            需要更多学习资源？<small>前往工作台</small>
          </span>
          <Icon name="arrow" size={15} />
        </a>
      </aside>
      <section className="sl-reader">
        <div className="sl-reader-toolbar">
          <span>
            {String(
              room.chapters.findIndex((c) =>
                c.resources.some((r) => r.id === resource.id),
              ) + 1,
            ).padStart(2, "0")}
            <i>/</i>
            {kindLabel[resource.kind]}
          </span>
          <button
            className={`sl-text-button ${noteOpen ? "active" : ""}`}
            onClick={() => setNoteOpen(!noteOpen)}
          >
            <Icon name="report" size={16} />
            我的笔记
          </button>
        </div>
        <div
          className="sl-reader-scroll"
          ref={reading}
          onScroll={(e) => {
            if (resource.kind === "report")
              patch({ position: e.currentTarget.scrollTop });
          }}
        >
          <LearningContent
            key={resource.id}
            resource={resource}
            evidence={evidence}
            onEvidence={patch}
            paused={chatActive || panel === "agent" || panel === "directory"}
          />
          {noteOpen && (
            <section className="sl-notes">
              <label htmlFor="learning-note">记录你的理解</label>
              <textarea
                id="learning-note"
                value={evidence.note}
                placeholder="用自己的话记下这一节的收获…"
                onChange={(e) => patch({ note: e.target.value })}
              />
              <small>自动保存在此浏览器 · 仅自己可见</small>
            </section>
          )}
        </div>
        <footer className="sl-reader-footer">
          <button
            className="sl-text-button"
            disabled={index === 0}
            onClick={() => select(resources[index - 1].id)}
          >
            <Icon name="back" size={16} />
            上一份
          </button>
          <span className="sl-reading-fact">
            {evidence.completed ? "已标记完成学习" : "按自己的节奏，慢慢来"}
          </span>
          {resource.ready && !evidence.completed ? (
            <button
              className="sl-primary"
              onClick={() => patch({ completed: true })}
            >
              标记学完 <Icon name="check" size={17} />
            </button>
          ) : (
            <button
              className="sl-primary"
              disabled={index === resources.length - 1}
              onClick={() => select(resources[index + 1].id)}
            >
              {index === resources.length - 1 ? "已到最后一份" : "下一份资源"}
              <Icon name="arrow" size={17} />
            </button>
          )}
        </footer>
      </section>
      <aside className="sl-agent">
        <div className="sl-rail-heading">
          <h2>
            <span className="sl-agent-symbol">
              <Icon name="spark" size={18} />
            </span>
            学习 Agent
          </h2>
          <span className="sl-local-tag">演示</span>
        </div>
        <div className="sl-context">
          <span>
            <i />
            当前学习上下文
          </span>
          <strong>{resource.topic}</strong>
          <small>
            {resource.kind === "video"
              ? `讲解位置 00:${String(Math.floor(evidence.position)).padStart(2, "0")}`
              : kindLabel[resource.kind]}{" "}
            · {evidence.completed ? "已标记完成" : "学习中"}
            {evidence.answer !== undefined
              ? ` · 检查${evidence.answer === 1 ? "正确" : "待回顾"}`
              : ""}
          </small>
        </div>
        <div className="sl-chat-history" ref={conversation}>
          <div className="sl-chat-bubble assistant">
            <span className="sl-chat-author">
              <Icon name="spark" size={14} />
              学习 Agent
            </span>
            <p>
              我们从「{resource.topic}」开始。你的目标是：{room.goal}
            </p>
            <p>
              你可以边学边问。我会根据阅读位置、完成记录和检查结果，陪你梳理下一步。
            </p>
          </div>
          {room.messages.map((m) => (
            <div key={m.id} className={`sl-chat-bubble ${m.role}`}>
              <span className="sl-chat-author">
                {m.role === "user" ? "你" : "学习 Agent"}
                <small>{m.resourceTitle}</small>
              </span>
              <p>{m.text}</p>
            </div>
          ))}
          {pending && (
            <div className="sl-chat-thinking" role="status">
              正在整理示例回复<span>•••</span>
            </div>
          )}
        </div>
        <div className="sl-chat-bottom">
          <div className="sl-quick-questions">
            {["举个例子", "接下来学什么？"].map((q) => (
              <button key={q} disabled={pending} onClick={() => ask(q)}>
                {q}
              </button>
            ))}
          </div>
          <form
            className="sl-chat-composer"
            onSubmit={(e) => {
              e.preventDefault();
              ask(question);
            }}
          >
            <textarea
              aria-label="向学习 Agent 提问"
              placeholder="哪里不明白？我们一起看看…"
              value={question}
              maxLength={1000}
              onChange={(e) => setQuestion(e.target.value)}
              onFocus={() => setChatActive(true)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  ask(question);
                }
              }}
            />
            <button
              className="sl-send"
              aria-label="发送问题"
              disabled={!question.trim() || pending}
            >
              <Icon name="arrow" size={18} />
            </button>
          </form>
          <small>本地示例回复 · 学习记录不会被发布</small>
        </div>
      </aside>
    </main>
  );
}
