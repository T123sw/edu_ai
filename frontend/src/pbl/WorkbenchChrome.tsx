import { useEffect, useRef, type ReactNode } from 'react';
import './projectWorkbench.css';
import './workbenchBrief.css';
export function WorkbenchHeading({title,taskTitle,stepNumber,totalSteps,children}: {
  title:string;taskTitle:string;
  stepNumber:number;totalSteps:number;children:ReactNode;
}) {
  return <header tabIndex={-1} className="pbl-project-heading pbl-task-brief">
    <div className="pbl-project-title"><a href="#/practice" aria-label="返回互动实验">←</a><h1>{title}</h1><span className="pbl-brief-step">第 {stepNumber} / {totalSteps} 步</span>
    </div>
    <div className="pbl-brief-intro">
      <h2>{taskTitle}</h2>
    </div>
    {children}
  </header>;
}
export function WorkbenchControls({saveStatus,status,operations,actions}:{saveStatus:string;status:string;operations:ReactNode;actions:ReactNode}) {
  return <>
    <span className="pbl-save-feedback" role="status" data-testid="save-status" hidden={['已保存','正在保存','本地草稿'].includes(saveStatus)}>{saveStatus}</span>
    <span className="pbl-workspace-status" role="status" data-testid="task-status">{status}</span>
    {actions}
    <details className="pbl-project-tools"><summary>工程操作</summary><div>{operations}</div></details>
  </>;
}

export function WorkbenchBody({steps,activeStep,onStep,disabled,children,tutor,tutorOpen,onTutorClose}: {
  steps:{id:string;title:string;passed?:boolean}[];activeStep:string;onStep(id:string):void;disabled:boolean;children:ReactNode;tutor:ReactNode;tutorOpen:boolean;onTutorClose():void;
}) {
  const stepList=useRef<HTMLOListElement>(null);
  useEffect(()=>{
    const list=stepList.current,active=list?.querySelector('[aria-current="step"]');
    if(!list||!active)return;
    const box=list.getBoundingClientRect(),item=active.getBoundingClientRect();
    if(item.top<box.top)list.scrollTop+=item.top-box.top;
    else if(item.bottom>box.bottom)list.scrollTop+=item.bottom-box.bottom;
    if(item.left<box.left)list.scrollLeft+=item.left-box.left;
    else if(item.right>box.right)list.scrollLeft+=item.right-box.right;
  },[activeStep]);
  return <div className="pbl-workbench-body">
    <nav className="pbl-workbench-steps" aria-label="练习步骤">
      <header><h2>练习步骤</h2><span>{steps.filter(step=>step.passed).length} / {steps.length} 已通过</span></header>
      <ol ref={stepList}>{steps.map((step,index)=><li key={step.id}>
        <button type="button" aria-current={activeStep===step.id?'step':undefined} disabled={disabled} onClick={()=>onStep(step.id)}>
          <span className={`pbl-step-number${step.passed?' passed':''}`} aria-hidden="true">{step.passed?'✓':index+1}</span>
          <span className="pbl-step-detail"><strong>{step.title}</strong><span>{step.passed?'检查通过':activeStep===step.id?'当前步骤 · 待检查':'待检查'}</span></span>
        </button>
      </li>)}</ol>
    </nav>
    <div className="pbl-workbench-content">{children}</div>
    <aside id="pbl-tutor-sidebar" className="pbl-tutor-sidebar" aria-label="AI 辅导" hidden={!tutorOpen} onKeyDown={event=>{if(event.key==='Escape'){event.stopPropagation();onTutorClose();}}}>
      <header><h2>AI 辅导</h2></header>
      <div className="pbl-tutor-sidebar-content">{tutor}</div>
    </aside>
  </div>;
}
