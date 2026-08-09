import { useEffect, useState } from "react";

import StudentSourcePanel from "../../../components/student/SourcePanel";
import StudentChatPanel from "../../../components/student/ChatPanel";
import StudentStudioPanel from "../../../components/student/StudentStudioPanel";
import { useCourseRoute } from "../../course/CourseRouteProvider";
import { MaterialIcon, cx } from "../../shared";
import { saveRecentLearningVisit } from "./studentRecentLearning";
import "../styles/studentAIWorkspace.css";

export function StudentAIWorkspacePage() {
  const { courseId } = useCourseRoute();
  const compact = typeof window !== "undefined" && window.innerWidth <= 1180;
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [leftCollapsed, setLeftCollapsed] = useState(compact);
  const [rightCollapsed, setRightCollapsed] = useState(compact);

  useEffect(() => {
    if (courseId) saveRecentLearningVisit(courseId, "student-ai");
    setSelectedDocumentIds([]);
  }, [courseId]);

  if (!courseId) return null;
  return (
    <div className="student-ai-workspace">
      <div className="student-ai-workspace__mobile-tools" aria-label="工作区面板切换">
        <button aria-pressed={!leftCollapsed} onClick={() => { setLeftCollapsed((value) => !value); setRightCollapsed(true); }}><MaterialIcon name="database" />知识库</button>
        <button aria-pressed={!rightCollapsed} onClick={() => { setRightCollapsed((value) => !value); setLeftCollapsed(true); }}><MaterialIcon name="auto_awesome" />生成工具</button>
      </div>
      <div className="student-ai-workspace__grid">
        <div className={cx("student-ai-workspace__region is-source", leftCollapsed && "is-collapsed")} data-testid="student-ai-source-region">
          <StudentSourcePanel courseId={courseId} selectedDocumentIds={selectedDocumentIds} onSelectedDocumentIdsChange={setSelectedDocumentIds} collapsed={leftCollapsed} onToggleCollapsed={() => setLeftCollapsed((value) => !value)} />
        </div>
        <div className="student-ai-workspace__region is-chat" data-testid="student-ai-chat-region">
          <StudentChatPanel courseId={courseId} selectedDocumentIds={selectedDocumentIds} />
        </div>
        <div className={cx("student-ai-workspace__region is-studio", rightCollapsed && "is-collapsed")} data-testid="student-ai-tools-region">
          <StudentStudioPanel courseId={courseId} selectedDocumentIds={selectedDocumentIds} collapsed={rightCollapsed} onToggleCollapsed={() => setRightCollapsed((value) => !value)} />
        </div>
      </div>
    </div>
  );
}
