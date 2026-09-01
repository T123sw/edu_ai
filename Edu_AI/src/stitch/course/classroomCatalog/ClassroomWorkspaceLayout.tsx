import type { ReactNode } from "react";

type Props = {
  directory: ReactNode;
  viewer: ReactNode;
  qa: ReactNode;
  directoryOpen: boolean;
  qaOpen: boolean;
  onCloseDirectory: () => void;
  onCloseQa: () => void;
};

export function ClassroomWorkspaceLayout({
  directory,
  viewer,
  qa,
  directoryOpen,
  qaOpen,
  onCloseDirectory,
  onCloseQa,
}: Props) {
  const closeActiveRail = directoryOpen ? onCloseDirectory : onCloseQa;

  return (
    <div className="course-classroom-workspace">
      {directoryOpen || qaOpen ? (
        <button
          type="button"
          className="catalog-drawer-scrim"
          aria-label="关闭侧栏"
          onClick={closeActiveRail}
        />
      ) : null}
      <aside
        className={`course-classroom-workspace__directory${directoryOpen ? " is-open" : ""}`}
        aria-label="课程与个人课堂导航"
      >
        {directory}
      </aside>
      <section className="course-classroom-workspace__viewer" aria-label="当前学习内容">
        {viewer}
      </section>
      <aside
        className={`course-classroom-workspace__qa${qaOpen ? " is-open" : ""}`}
        aria-label="当前内容问答"
      >
        {qa}
      </aside>
    </div>
  );
}
