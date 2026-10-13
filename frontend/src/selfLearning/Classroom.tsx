import type { ReadingSnapshot } from '../liveLearning/agentTurns';
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  allResources,
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
import { useLearningProgress, readingProgress } from '../liveLearning/learningState';
import { resourceRef } from '../liveLearning/readingContext';
import { LearningAgent } from "./LearningAgent";
import "./classroomEditorial.css";

export function Classroom({
  room: inputRoom,
  resourceId,
  setState,
  onSelect,
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
  const readingScope = useMemo(() => ({ courseId: room.id, resourceId: resource.id, version: resource.remote?.version }), [room.id, resource.id, resource.remote?.version]);
  const [snapshotState, setSnapshotState] = useState<{ scope: object; snapshot: ReadingSnapshot }>();
  const [panel, setPanel] = useState("learn");
  const [noteOpen, setNoteOpen] = useState(false);
  const [chatActive, setChatActive] = useState(false);
  const [closedChapters, setClosedChapters] = useState<string[]>([]);
  const reading = useRef<HTMLDivElement>(null);
  const evidence = resourceEvidence(room, resource);
  const chapter = room.chapters.find(c => c.resources.some(r => r.id === resource.id))!;
  const currentRef = resourceRef(resource);
  const progress = readingProgress(room);
  const isPlayback = resource.kind === "video" || resource.remote?.materialType === "classroom";
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
    <main className={`sl-classroom panel-${panel} ${isPlayback ? "is-playback" : ""}`}>
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
        <div className="sl-rail-heading sl-course-heading">
          <a className="sl-icon-button" href="#/" aria-label="返回首页"><Icon name="back" size={18} /></a>
          <h2 title={room.title}>{room.title}</h2>
        </div>
        <div className="sl-route-progress">
          <div>
            <span>学习进度</span>
            <strong>
              {progress.finished} <small>/ {progress.total}</small>
            </strong>
          </div>
          <div className="sl-progress-track" role="progressbar" aria-label="学习进度" aria-valuemin={0} aria-valuemax={progress.total || 1} aria-valuenow={progress.finished} aria-valuetext={`已看完 ${progress.finished} / ${progress.total} 份资料`}>
            <i
              style={{
                width: `${progress.percent}%`,
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
                  {progress.finishedIds.includes(r.id) ? (
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
      </aside>
      <section className="sl-reader">
        {!isPlayback && <div className="sl-reader-toolbar">
          <div className="sl-reader-tools">
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
        </div>}
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
            onReadingSnapshot={room.agentRuntime ? snapshot => setSnapshotState({ scope: readingScope, snapshot }) : undefined}
            onReading={room.progressPersistence ? (type, payload) => facts.enqueue(chapter.id, type, resource, payload) : undefined}
            resource={resource}
            evidence={evidence}
            onEvidence={patch}
            paused={chatActive || panel === "agent" || panel === "directory"}
          />
          {noteOpen && !isPlayback && (
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
      </section>
      <LearningAgent readingSnapshot={currentRef ? (snapshotState?.scope === readingScope ? snapshotState.snapshot : { resource_ref: currentRef, selected_text: "", locator: currentRef.material_type === "classroom" ? undefined : evidence.locator }) : undefined} room={room} resource={resource} setState={setState} onSelect={onSelect} onEngage={() => setChatActive(true)} onAsk={onAsk} onSelfAssessment={room.progressPersistence ? (value) => facts.enqueue(chapter.id, 'self_assessment_set', undefined, { value }) : undefined} selfAssessmentPending={facts.pending.some(p => p.topic === chapter.id && p.event.type === 'self_assessment_set')} />
    </main>
  );
}
