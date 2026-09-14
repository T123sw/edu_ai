import { useState } from "react";
import {
  createClassroom,
  uid,
  type Classroom,
  type LearningResource,
} from "./model";
import { Icon, Modal } from "./ui";

// UI-only import: file metadata is retained, not file bytes. No upload request occurs.
export function PublishDialog({
  publisher,
  onPublish,
  onClose,
}: {
  publisher: string;
  onPublish: (room: Classroom) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState("");
  return (
    <Modal title="上传共享课堂" onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!title.trim() || !goal.trim() || !files.length) {
            setError("请填写标题、学习目标，并选择至少一份学习文件。");
            return;
          }
          const room = createClassroom(goal, true);
          const resources: LearningResource[] = files.map((file) => ({
            id: uid(),
            title: file.name,
            topic: title.trim(),
            kind: /\.mp4$/i.test(file.name)
              ? "video"
              : /\.pptx$/i.test(file.name)
                ? "slides"
                : "report",
            ready: true,
            minutes: 5,
            createdAt: Date.now(),
          }));
          onPublish({
            ...room,
            title: title.trim(),
            publisher,
            chapters: [{ id: uid(), title: title.trim(), resources }],
            selectedId: resources[0].id,
          });
        }}
      >
        <p className="sl-publish-note">
          教师可以把课堂分享到首页。当前仅模拟发布到本浏览器，文件不会上传；预览仍使用示例内容。
        </p>
        <label className="sl-field">
          课堂名称
          <input
            required
            maxLength={60}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="给这段学习旅程起个名字"
          />
        </label>
        <label className="sl-field">
          学习目标
          <textarea
            required
            maxLength={500}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="学完后，学习者能够做什么？"
          />
        </label>
        <label className="sl-upload-area">
          <Icon name="upload" size={25} />
          <strong>选择课堂学习文件</strong>
          <span>PDF、Markdown、MP4、PPTX · 每份不超过 50 MB · 最多 10 份</span>
          <input
            type="file"
            aria-label="课堂学习文件"
            accept=".pdf,.md,.mp4,.pptx"
            multiple
            onChange={(e) => {
              const next = Array.from(e.target.files || []);
              if (
                next.length > 10 ||
                next.some(
                  (f) =>
                    f.size > 50 * 1024 * 1024 ||
                    !/\.(pdf|md|mp4|pptx)$/i.test(f.name),
                )
              ) {
                setError(
                  "请选择支持的文件类型，最多 10 份且每份不超过 50 MB。",
                );
                setFiles([]);
                e.target.value = "";
              } else {
                setError("");
                setFiles(next);
              }
            }}
          />
        </label>
        {files.length > 0 && (
          <ul className="sl-file-list">
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`}>
                <Icon name="report" size={16} />
                <span>{f.name}</span>
                <small>{Math.max(1, Math.round(f.size / 1024))} KB</small>
              </li>
            ))}
          </ul>
        )}
        {error && (
          <p className="sl-error" role="alert">
            {error}
          </p>
        )}
        <div className="sl-modal-actions">
          <button
            type="button"
            className="sl-secondary-button"
            onClick={onClose}
          >
            取消
          </button>
          <button
            className="sl-primary"
            disabled={!title.trim() || !goal.trim() || !files.length}
          >
            发布本地演示 <Icon name="arrow" size={17} />
          </button>
        </div>
      </form>
    </Modal>
  );
}
