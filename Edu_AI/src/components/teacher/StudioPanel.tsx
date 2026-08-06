import type { FC } from "react";

import type { WorkspaceScope } from "../../services/teacher/workspaceScope";
import { GenerationFactory } from "./generation/GenerationFactory";

type Props = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  courseId?: string;
  workspaceScope?: WorkspaceScope;
  onPreviewStateChange?: (open: boolean) => void;
};

const StudioPanel: FC<Props> = ({ collapsed, onToggleCollapsed, courseId }) => {
  if (collapsed) {
    return <button type="button" className="generation-factory-collapsed" onClick={onToggleCollapsed} aria-label="打开生成工厂">生成</button>;
  }
  return <GenerationFactory courseId={courseId} />;
};

export default StudioPanel;
