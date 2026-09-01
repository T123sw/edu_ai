import { useEffect, useRef, type ReactNode, type RefObject } from "react";

type Props = {
  directory: ReactNode;
  viewer: ReactNode;
  qa: ReactNode;
  directoryOpen: boolean;
  qaOpen: boolean;
  onCloseDirectory: () => void;
  onCloseQa: () => void;
  directoryTriggerRef: RefObject<HTMLButtonElement | null>;
  qaTriggerRef: RefObject<HTMLButtonElement | null>;
};

export function ClassroomWorkspaceLayout({
  directory,
  viewer,
  qa,
  directoryOpen,
  qaOpen,
  onCloseDirectory,
  onCloseQa,
  directoryTriggerRef,
  qaTriggerRef,
}: Props) {
  const closeActiveRail = directoryOpen ? onCloseDirectory : onCloseQa;
  const directoryRef = useRef<HTMLElement | null>(null);
  const qaRef = useRef<HTMLElement | null>(null);
  const previousDirectoryOpen = useRef(directoryOpen);
  const previousQaOpen = useRef(qaOpen);

  useEffect(() => {
    if (previousDirectoryOpen.current && !directoryOpen) {
      requestAnimationFrame(() => directoryTriggerRef.current?.focus());
    }
    previousDirectoryOpen.current = directoryOpen;
  }, [directoryOpen, directoryTriggerRef]);

  useEffect(() => {
    if (previousQaOpen.current && !qaOpen) {
      requestAnimationFrame(() => qaTriggerRef.current?.focus());
    }
    previousQaOpen.current = qaOpen;
  }, [qaOpen, qaTriggerRef]);

  useEffect(() => {
    const activeRail = directoryOpen ? directoryRef.current : qaOpen ? qaRef.current : null;
    if (!activeRail) return;
    requestAnimationFrame(() => {
      const firstControl = activeRail.querySelector<HTMLElement>(
        '[data-drawer-initial-focus], button:not(:disabled), textarea:not(:disabled), input:not(:disabled)',
      );
      (firstControl ?? activeRail).focus();
    });
  }, [directoryOpen, qaOpen]);

  useEffect(() => {
    if (!directoryOpen && !qaOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeActiveRail();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [closeActiveRail, directoryOpen, qaOpen]);

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
        ref={directoryRef}
        id="classroom-workspace-directory"
        tabIndex={-1}
        className={`course-classroom-workspace__directory${directoryOpen ? " is-open" : ""}`}
        aria-label="课程与个人课堂导航"
      >
        {directory}
      </aside>
      <section className="course-classroom-workspace__viewer" aria-label="当前学习内容">
        {viewer}
      </section>
      <aside
        ref={qaRef}
        id="classroom-workspace-qa"
        tabIndex={-1}
        className={`course-classroom-workspace__qa${qaOpen ? " is-open" : ""}`}
        aria-label="当前内容问答"
      >
        {qa}
      </aside>
    </div>
  );
}
