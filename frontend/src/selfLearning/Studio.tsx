import { useState, type Dispatch, type SetStateAction } from "react";
import {
  createStudioJob,
  jobAction,
  kindLabel,
  type LearningState,
  type ResourceKind,
} from "./model";
import { Empty, Icon } from "./ui";

export function Studio({
  state,
  setState,
  classroomId,
}: {
  state: LearningState;
  setState: Dispatch<SetStateAction<LearningState>>;
  classroomId?: string;
}) {
  const [tab, setTab] = useState("create");
  const [kind, setKind] = useState<ResourceKind>("report");
  const [prompt, setPrompt] = useState("");
  const [created, setCreated] = useState(false);
  const room = state.rooms.find((r) => r.id === classroomId);
  const [sourceId, setSourceId] = useState(
    classroomId || state.rooms[0]?.id || "",
  );
  const source = state.rooms.find((r) => r.id === sourceId);
  const running = state.jobs.filter((j) => j.status === "running").length;
  return (
    <main className="sl-secondary">
      <div className="sl-page-heading">
        <span className="sl-eyebrow">YOUR CREATIVE SPACE</span>
        <h1>学习之外，多一点创造。</h1>
        <p>为一个问题整理报告，为一个想法生成课件。这里是你的工作台。</p>
        {room && (
          <a className="sl-back-context" href={`#/classroom/${room.id}`}>
            <Icon name="back" size={15} />
            返回「{room.title}」
          </a>
        )}
      </div>
      <nav className="sl-tabs" aria-label="工作台功能">
        {[
          ["create", "spark", "资源创作"],
          ["knowledge", "book", "课程知识库"],
          ["jobs", "clock", "后台任务"],
        ].map(([id, icon, title]) => (
          <button
            key={id}
            aria-pressed={tab === id}
            className={tab === id ? "active" : ""}
            onClick={() => setTab(id)}
          >
            <Icon name={icon} size={18} />
            {title}
            {id === "jobs" && running > 0 && (
              <span className="sl-count">{running}</span>
            )}
          </button>
        ))}
      </nav>
      {tab === "create" && (
        <section className="sl-studio-create">
          <div className="sl-studio-intro">
            <span className="sl-big-icon">
              <Icon name="spark" size={30} />
            </span>
            <h2>把想深入的知识，变成一份资源</h2>
            <p>生成后的作品会自动收进资源中心，不会打乱你的课堂目录。</p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!prompt.trim()) return;
              const job = createStudioJob(prompt, kind);
              setState((s) => ({ ...s, jobs: [job, ...s.jobs] }));
              setCreated(true);
              setPrompt("");
            }}
          >
            <div className="sl-kind-grid">
              {(["report", "video", "slides", "quiz"] as ResourceKind[]).map(
                (k) => (
                  <button
                    key={k}
                    type="button"
                    className={kind === k ? "selected" : ""}
                    aria-pressed={kind === k}
                    onClick={() => setKind(k)}
                  >
                    <Icon name={k} size={23} />
                    <strong>{kindLabel[k]}</strong>
                    <small>
                      {
                        {
                          report: "把复杂知识讲清楚",
                          video: "可视化理解一个主题",
                          slides: "组织重点与思路",
                          quiz: "用问题检查理解",
                        }[k]
                      }
                    </small>
                  </button>
                ),
              )}
            </div>
            <label className="sl-field">
              想创作什么？
              <textarea
                aria-label="资源创作需求"
                placeholder="例如：整理一份 ReAct 与 MCP 的区别对比报告，附上应用场景。"
                value={prompt}
                onChange={(e) => {
                  setPrompt(e.target.value);
                  setCreated(false);
                }}
                maxLength={1000}
              />
            </label>
            <div className="sl-form-bottom">
              <span className="sl-muted">本地生成演示 · 暂未调用生成服务</span>
              <button className="sl-primary" disabled={!prompt.trim()}>
                开始创作 <Icon name="arrow" size={17} />
              </button>
            </div>
            {created && (
              <div className="sl-feedback correct" role="status">
                已加入后台任务，完成后可在资源中心查看。
                <button
                  type="button"
                  className="sl-text-button"
                  onClick={() => setTab("jobs")}
                >
                  查看任务 <Icon name="arrow" size={15} />
                </button>
              </div>
            )}
          </form>
        </section>
      )}
      {tab === "knowledge" && (
        <section className="sl-knowledge">
          <div className="sl-section-heading">
            <div>
              <h2>课程背后的资料</h2>
              <p className="sl-muted">
                爬取资料用于构建知识库，生成内容在课堂中学习。
              </p>
            </div>
            <select
              aria-label="选择课程知识库"
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
            >
              {state.rooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title}
                </option>
              ))}
            </select>
          </div>
          {source ? (
            <>
              <div className="sl-knowledge-banner">
                <Icon name="book" size={27} />
                <div>
                  <h3>{source.title}</h3>
                  <p>
                    以下是检索范围预览。尚未连接爬虫，也未导入真实来源文档。
                  </p>
                </div>
                <span className="sl-local-tag">示例</span>
              </div>
              <div className="sl-source-list">
                {source.chapters.map((c, i) => (
                  <div key={c.id}>
                    <span className="sl-source-number">0{i + 1}</span>
                    <div>
                      <h3>{c.title}</h3>
                      <p>计划检索：官方文档、概念说明与实践案例</p>
                    </div>
                    <span>待联调</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <Empty
              title="还没有课程知识库"
              text="从首页开始一门课堂，Agent 将围绕学习路径整理来源。"
              action={
                <a className="sl-primary" href="#/">
                  开始学习
                </a>
              }
            />
          )}
        </section>
      )}
      {tab === "jobs" && (
        <section>
          <div className="sl-section-heading">
            <h2>
              后台任务 <span>{state.jobs.length}</span>
            </h2>
            <span className="sl-muted">离开此页面也会继续 · 本地计时演示</span>
          </div>
          {state.jobs.length ? (
            <div className="sl-job-list">
              {state.jobs.map((job) => (
                <div className="sl-job" key={job.id}>
                  <span className={`sl-job-icon ${job.status}`}>
                    <Icon
                      name={
                        job.status === "done"
                          ? "check"
                          : job.status === "cancelled"
                            ? "pause"
                            : "spark"
                      }
                      size={21}
                    />
                  </span>
                  <div className="sl-job-body">
                    <h3>{job.title}</h3>
                    <p>
                      {job.roomId
                        ? "课堂资源准备"
                        : `${kindLabel[job.resource?.kind || "report"]}创作`}
                      <span>·</span>
                      {job.status === "done"
                        ? "已完成"
                        : job.status === "cancelled"
                          ? "已取消"
                          : "正在生成"}{" "}
                      · {Math.round((job.elapsed / job.duration) * 100)}%
                    </p>
                    <div className="sl-progress-track">
                      <i
                        style={{
                          width: `${(job.elapsed / job.duration) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                  {job.status === "done" ? (
                    <a
                      className="sl-text-button"
                      href={
                        job.roomId
                          ? `#/classroom/${job.roomId}`
                          : `#/resources?resource=${job.resource?.id}${room ? `&classroom=${room.id}` : ""}`
                      }
                    >
                      查看 <Icon name="arrow" size={16} />
                    </a>
                  ) : (
                    <button
                      className="sl-text-button"
                      onClick={() =>
                        setState((s) =>
                          jobAction(
                            s,
                            job.id,
                            job.status === "running" ? "cancel" : "retry",
                          ),
                        )
                      }
                    >
                      {job.status === "running" ? "取消" : "继续生成"}
                    </button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <Empty
              title="这里还很安静"
              text="开始课堂或创作一份资源后，可以在这里查看生成过程。"
              action={
                <button className="sl-primary" onClick={() => setTab("create")}>
                  创作第一份资源 <Icon name="arrow" size={17} />
                </button>
              }
            />
          )}
        </section>
      )}
    </main>
  );
}
