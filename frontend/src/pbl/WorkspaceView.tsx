import type { WorkspaceView } from './useWorkspaceView';

export function WorkspaceViewControls({view, onChange, compact, project = false}: {
  view: WorkspaceView; onChange(view: WorkspaceView): void; compact: boolean; project?: boolean;
}) {
  return <nav className="pbl-view-switch" aria-label="编程工作区视图">
    {!compact && <button aria-pressed={view === 'split'} onClick={() => onChange('split')}>并排显示</button>}
    <button aria-pressed={view === 'code'} onClick={() => onChange('code')}>代码</button>
    <button aria-pressed={view === 'result'} onClick={() => onChange('result')}>{project ? '页面预览' : '运行结果'}</button>
  </nav>;
}
