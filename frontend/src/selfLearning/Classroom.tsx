import type { ReadingSnapshot } from '../liveLearning/agentTurns';
import {
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  allResources,
  completion,
  resourceEvidence,
  kindLabel,
  resourceDurationLabel,
  updateEvidence,
  updateRoom,
  type Classroom as Room,
  type LearningState,
} from "./model";
import { LearningContent } from "./Content";
import { Icon } from "./ui";
import { useLearningProgress } from '../liveLearning/learningState';
import { resourceRef, refKey } from '../liveLearning/readingContext';
import { LearningAgent } from "./LearningAgent";
import "./classroomEditorial.css";

export function Classroom({
  room: inputRoom,
  resourceId,
  setState,
  onSelect,
  workbenchHref,
  onAsk,
}: {
  room: Room;
  resourceId?: string;
  setState: Dispatch<SetStateAction<LearningState>>;
  onSelect: (id: string) => void;
  workbenchHref?: string;
  onAsk?: (chapterId: string, resourceId: string, text: string) => Promise<void>;
}) {
  const facts = useLearningProgress(inputRoom);
  const room = facts.room;
  const resources = allResources(room);
  const resource =
    resources.find((r) => r.id === resourceId) ||
    resources.find((r) => r.id === room.selectedId) ||
    resources[0];
  const [snapshots, setSnapshots] = useState<Record<string, ReadingSnapshot>>({});
  const [panel, setPanel] = useState("learn");
  const [noteOpen, setNoteOpen] = useState(false);
  const [chatActive, setChatActive] = useState(false);
  const [directoryCollapsed, setDirectoryCollapsed] = useState(false);
  const [closedChapters, setClosedChapters] = useState<string[]>([]);
  const reading = useRef<HTMLDivElement>(null);
  const evidence = resourceEvidence(room, resource);
  const chapter = room.chapters.find(c => c.resources.some(r => r.id === resource.id))!;
  const syncing = facts.pending.some(p => p.event.type === 'resource_completion_set' && p.event.resource_ref && resourceRef(resource) && refKey(p.event.resource_ref) === refKey(resourceRef(resource)!));
  const currentRef = resourceRef(resource);
  const nextRef = room.learningProjection?.next_actions[chapter.id]?.find(a => a.kind === 'continue' && a.resource_ref && (!currentRef || refKey(a.resource_ref) !== refKey(currentRef)))?.resource_ref;
  const nextResource = (nextRef && resources.find(r => r.remote && refKey(resourceRef(r)!) === refKey(nextRef))) || resources[resources.findIndex(r => r.id === resource.id) + 1];
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
  function patch(value: Partial<typeof evidence>) {
    setState((s) => updateEvidence(s, room.id, resource.id, value));
  }
  function select(id: string) {
    setChatActive(false);
    onSelect(id);
    setPanel("learn");
  }
  return (
    <main className={`sl-classroom panel-${panel} ${directoryCollapsed ? "directory-collapsed" : ""}`}>
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
          <button className="sl-icon-button sl-desktop-control" aria-label="收起课堂目录" onClick={() => setDirectoryCollapsed(true)}><Icon name="back" size={16} /></button>
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
              <button className="sl-chapter-heading" aria-expanded={!closedChapters.includes(chapter.id)} onClick={() => setClosedChapters(s => s.includes(chapter.id) ? s.filter(id => id !== chapter.id) : [...s, chapter.id])}>
                <span>{String(n + 1).padStart(2, "0")}</span>
                {chapter.title}
                <Icon name="chevron" size={13} />
              </button>
              {!closedChapters.includes(chapter.id) && chapter.resources.map((r) => (
                <button
                  key={r.id}
                  className={`sl-resource-row ${r.id === resource.id ? "active" : ""}`}
                  onClick={() => select(r.id)}
                  aria-current={r.id === resource.id ? "page" : undefined}
                  aria-label={r.title}
                >
                  <Icon name={r.kind} size={17} />
                  <span>
                    {r.sourceResourceId ? r.title : kindLabel[r.kind]}
                    <small>{r.ready ? resourceDurationLabel(r) : "正在准备"}</small>
                  </span>
                  {resourceEvidence(room, r).completed ? (
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
        <a href={workbenchHref || `#/studio?classroom=${room.id}`} className="sl-rail-studio">
          <Icon name="studio" size={17} />
          <span>
            需要更多学习资源？<small>前往工作台</small>
          </span>
          <Icon name="arrow" size={15} />
        </a>
      </aside>
      <section className="sl-reader">
        <div className="sl-reader-toolbar">
          <div className="sl-reader-tools">
          {directoryCollapsed && <button className="sl-icon-button sl-desktop-control" aria-label="展开课堂目录" onClick={() => setDirectoryCollapsed(false)}><Icon name="menu" size={17} /></button>}
          <span>
            {String(
              room.chapters.findIndex((c) =>
                c.resources.some((r) => r.id === resource.id),
              ) + 1,
            ).padStart(2, "0")}
            <i>/</i>
            {kindLabel[resource.kind]}
          </span>
          </div>
          <div className="sl-reader-tools">
          <button
            className={`sl-text-button ${noteOpen ? "active" : ""}`}
            onClick={() => setNoteOpen(!noteOpen)}
          >
            <Icon name="report" size={16} />
            我的笔记
          </button>
          </div>
        </div>
        <div
          className="sl-reader-scroll"
          ref={reading}
          onScroll={(e) => {
            if (!room.progressPersistence && resource.kind === "report")
              patch({ position: e.currentTarget.scrollTop });
          }}
        >
          <LearningContent
            key={`${resource.id}:${resource.remote?.version}`}
            onReadingSnapshot={room.agentRuntime ? snapshot => setSnapshots(s => ({ ...s, [refKey(snapshot.resource_ref)]: snapshot })) : undefined}
            onReading={room.progressPersistence ? (type, payload) => facts.enqueue(chapter.id, type, resource, payload) : undefined}
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
              <small>{room.live ? "自动保存到账号 · 仅自己可见" : "自动保存在此浏览器 · 仅自己可见"}</small>
            </section>
          )}
        </div>
        {room.progressPersistence && facts.error && <div role="alert">学习记录未同步：{facts.error}<button onClick={facts.retry}>重试保存</button>{facts.pending.some(p => p.blocked) && <button onClick={facts.discardConflicts}>放弃冲突操作并刷新</button>}<small>可以继续阅读其他资料。</small></div>}
        <footer className={`sl-reader-footer ${room.progressPersistence ? "sl-versioned-progress" : ""}`}>
          <button
            className="sl-text-button"
            disabled={index === 0}
            onClick={() => select(resources[index - 1].id)}
          >
            <Icon name="back" size={16} />
            上一份
          </button>
          {room.progressPersistence ? <>
            <span className="sl-reading-fact" role="status">{evidence.completed ? '资料已学完，理解尚未验证' : '按自己的节奏，慢慢来'}{facts.pending.length > 0 && (facts.error ? ' · 未同步' : ' · 保存中…')}</span>
            {resource.ready && <button className="sl-primary" disabled={syncing} onClick={() => facts.enqueue(chapter.id, 'resource_completion_set', resource, { completed: !evidence.completed })}>{evidence.completed ? '撤销学完' : '本资料已学完'}</button>}
            <button className="sl-primary" disabled={!nextResource} onClick={() => nextResource && select(nextResource.id)}>{nextResource ? '继续学习' : '已到最后一份'}</button>
          </> : <>          <span className="sl-reading-fact">
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
          )}</>}

        </footer>
      </section>
      <LearningAgent readingSnapshot={currentRef ? snapshots[refKey(currentRef)] || { resource_ref: currentRef, selected_text: "", locator: evidence.locator } : undefined} room={room} resource={resource} setState={setState} onSelect={onSelect} onEngage={() => setChatActive(true)} onAsk={onAsk} onSelfAssessment={room.progressPersistence ? (value) => facts.enqueue(chapter.id, 'self_assessment_set', undefined, { value }) : undefined} selfAssessmentPending={facts.pending.some(p => p.topic === chapter.id && p.event.type === 'self_assessment_set')} />
    </main>
  );
}
