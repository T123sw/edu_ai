import type { ClassroomQaController } from '../../classroomQa/classroomQaController';
import { ClassroomQaPanel } from '../../classroomQa/ClassroomQaPanel';
import { MaterialIcon } from '../../shared';

export const RESOURCE_QA_SCOPE_LABELS = {
  document: '已读取完整文档',
  practice: '已读取完整习题',
  classroom: '已读取完整课堂',
} as const;

export type WorkspaceQaBinding =
  | { status: 'empty' }
  | { status: 'loading'; title: string; kindLabel: string }
  | { status: 'error'; title: string; message: string; onRetry: () => void }
  | {
      status: 'ready';
      title: string;
      kindLabel: string;
      scopeLabel: string;
      controller: ClassroomQaController;
      canAsk: boolean;
    };

export function ContextualClassroomQaPanel({
  binding,
}: {
  binding: WorkspaceQaBinding;
}) {
  if (binding.status === "empty") {
    return (
      <aside className="contextual-classroom-qa is-state" aria-label="AI 学习问答">
        <MaterialIcon name="forum" />
        <h2>AI 学习问答</h2>
        <p>从左侧选择课堂、文档或习题后，可以围绕完整学习内容提问。</p>
      </aside>
    );
  }

  if (binding.status === "loading") {
    return (
      <aside className="contextual-classroom-qa is-state" aria-label="问答加载中">
        <MaterialIcon name="progress_activity" />
        <h2>正在准备《{binding.title}》的问答</h2>
        <p>{binding.kindLabel}内容加载完成后即可提问。</p>
      </aside>
    );
  }

  if (binding.status === "error") {
    return (
      <aside className="contextual-classroom-qa is-state is-error" aria-label="问答加载失败">
        <MaterialIcon name="error" />
        <h2>《{binding.title}》问答暂不可用</h2>
        <p>{binding.message}</p>
        <button type="button" onClick={binding.onRetry}>重新加载</button>
      </aside>
    );
  }

  return (
    <aside className="contextual-classroom-qa" aria-label="AI 学习问答">
      <div className="contextual-classroom-qa__context">
        <MaterialIcon name="auto_awesome" />
        <div>
          <strong>正在围绕《{binding.title}》问答</strong>
          <span>{binding.kindLabel} · {binding.scopeLabel}</span>
        </div>
      </div>
      <ClassroomQaPanel
        controller={binding.controller}
        canAsk={binding.canAsk}
        title="AI 学习问答"
        eyebrow={`${binding.kindLabel} · ${binding.scopeLabel}`}
      />
    </aside>
  );
}
