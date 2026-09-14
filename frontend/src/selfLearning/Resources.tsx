import { useState } from "react";
import { kindLabel, type LearningResource } from "./model";
import { LearningContent, reportParagraphs } from "./Content";
import { Empty, Icon, Modal } from "./ui";

export function Resources({
  resources,
  resourceId,
  onRename,
  onRemove,
}: {
  resources: LearningResource[];
  resourceId?: string;
  onRename: (id: string, title: string) => void;
  onRemove: (id: string) => void;
}) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(resourceId);
  const current = resources.find((r) => r.id === selected);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [removing, setRemoving] = useState(false);
  const visible = resources.filter(
    (r) =>
      (filter === "all" || r.kind === filter) &&
      r.title.toLowerCase().includes(query.trim().toLowerCase()),
  );
  function download(resource: LearningResource) {
    const content = `# ${resource.title}\n\n本地示例内容，非模型生成。\n\n${reportParagraphs(resource).join("\n\n")}`;
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/markdown;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `${resource.title.replace(/[\\/:*?"<>|]/g, "-").slice(0, 60)}.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <main className="sl-secondary">
      <div className="sl-page-heading sl-heading-row">
        <div>
          <span className="sl-eyebrow">A LITTLE LIBRARY OF YOUR OWN</span>
          <h1>让每一次创作，有处安放。</h1>
          <p>工作台生成的报告、讲解和课件，都在这里。</p>
        </div>
        <a className="sl-primary" href="#/studio">
          <Icon name="spark" size={17} />
          创作资源
        </a>
      </div>
      <div className="sl-resource-filters">
        <nav className="sl-tabs" aria-label="资源类型">
          {[["all", "全部"], ...Object.entries(kindLabel)].map(
            ([id, label]) => (
              <button
                key={id}
                className={filter === id ? "active" : ""}
                aria-pressed={filter === id}
                onClick={() => setFilter(id)}
              >
                {label}
              </button>
            ),
          )}
        </nav>
        <label className="sl-search-field">
          <Icon name="search" size={17} />
          <input
            aria-label="搜索资源"
            placeholder="搜索资源…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      {visible.length ? (
        <div className="sl-output-grid">
          {visible.map((r) => (
            <button
              key={r.id}
              className="sl-output-card"
              onClick={() => {
                setSelected(r.id);
                setEditing(false);
                setRemoving(false);
              }}
            >
              <div className={`sl-output-art ${r.kind}`}>
                <Icon name={r.kind} size={45} />
                <span>{r.kind.toUpperCase()}</span>
              </div>
              <div>
                <span className="sl-eyebrow">{kindLabel[r.kind]}</span>
                <h3>{r.title}</h3>
                <p>
                  {new Date(r.createdAt).toLocaleDateString("zh-CN")}
                  <span>
                    本地示例 <Icon name="arrow" size={15} />
                  </span>
                </p>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <Empty
          title={
            resources.length ? "没有找到这份资源" : "你的资源库，等待第一个作品"
          }
          text={
            resources.length
              ? "试试其他关键词或资源类型。"
              : "在工作台创作，完成后会自动收进这里。课堂学习资料仍保留在对应课堂。"
          }
          action={
            <a className="sl-primary" href="#/studio">
              前往工作台 <Icon name="arrow" size={17} />
            </a>
          }
        />
      )}
      {current && (
        <Modal
          wide
          title={current.title}
          onClose={() => setSelected(undefined)}
        >
          <div className="sl-resource-organize">
            {editing ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (name.trim()) {
                    onRename(current.id, name.trim());
                    setEditing(false);
                  }
                }}
              >
                <input
                  aria-label="资源名称"
                  autoFocus
                  maxLength={100}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <button className="sl-text-button" disabled={!name.trim()}>
                  保存名称
                </button>
                <button
                  className="sl-text-button"
                  type="button"
                  onClick={() => setEditing(false)}
                >
                  取消
                </button>
              </form>
            ) : (
              <button
                className="sl-text-button"
                onClick={() => {
                  setName(current.title);
                  setEditing(true);
                  setRemoving(false);
                }}
              >
                重命名
              </button>
            )}
            {!removing && (
              <button
                className="sl-text-button"
                onClick={() => {
                  setRemoving(true);
                  setEditing(false);
                }}
              >
                删除资源
              </button>
            )}
            {removing && (
              <div className="sl-remove-confirm" role="alert">
                <span>仅删除这份本地作品，不影响课堂。确认删除？</span>
                <button
                  className="sl-text-button"
                  onClick={() => {
                    onRemove(current.id);
                    setSelected(undefined);
                    setRemoving(false);
                  }}
                >
                  确认删除
                </button>
                <button
                  className="sl-text-button"
                  onClick={() => setRemoving(false)}
                >
                  保留
                </button>
              </div>
            )}
          </div>
          <div className="sl-resource-preview">
            <LearningContent key={current.id} resource={current} />
          </div>
          <div className="sl-modal-actions">
            <span className="sl-muted">
              {current.kind === "report"
                ? "可导出当前示例报告"
                : "当前为交互预览，暂不提供真实媒体下载"}
            </span>
            {current.kind === "report" && (
              <button className="sl-primary" onClick={() => download(current)}>
                <Icon name="download" size={17} />
                下载 Markdown
              </button>
            )}
          </div>
        </Modal>
      )}
    </main>
  );
}
