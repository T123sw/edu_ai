import { useRef, useState, type ReactNode, type CSSProperties } from 'react';
import { SandpackLayout } from '@codesandbox/sandpack-react';
export type WorkbenchPanel = 'preview'|'checks';
export interface WorkbenchViewProps {panel:WorkbenchPanel;onPanel(panel:WorkbenchPanel):void;mobilePane:'code'|'result';onMobilePane(pane:'code'|'result'):void;checks:ReactNode}
export function WorkbenchPanels({panel,onPanel,mobilePane,onMobilePane,checks,code,preview,previewLabel='页面预览',codeHint='编辑后自动更新预览'}:WorkbenchViewProps & {code:ReactNode;preview:ReactNode;previewLabel?:string;codeHint?:string}) {
  const [width,setWidth]=useState(50);
  const grid=useRef<HTMLDivElement>(null);
  const [dragging,setDragging]=useState(false);
  const clamp=(n:number)=>Math.max(30,Math.min(70,n));
  return <div className={`pbl-project-editor pbl-mobile-${mobilePane}${dragging?' pbl-resizing':''}`}>
    <nav className="pbl-mobile-workspace-tabs" aria-label="工作区视图"><button aria-pressed={mobilePane==='code'} onClick={()=>onMobilePane('code')}>代码</button><button aria-pressed={mobilePane==='result'} onClick={()=>onMobilePane('result')}>预览与验收</button></nav>
    <div ref={grid} className="pbl-workbench-surface" style={{'--pbl-code-width':`${width}%`} as CSSProperties}>
      <SandpackLayout className="pbl-workbench-grid">
        <section className="pbl-code-pane" aria-label="代码编辑区"><header><strong>代码</strong><span>{codeHint}</span></header>{code}</section>
        <div className="pbl-pane-resizer" role="separator" aria-label="调整代码区宽度" aria-orientation="vertical" aria-valuemin={30} aria-valuemax={70} aria-valuenow={Math.round(width)} tabIndex={0}
          onKeyDown={e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();setWidth(n=>e.key==='Home'?30:e.key==='End'?70:clamp(n+(e.key==='ArrowLeft'?-2:2)));}}}
          onPointerDown={e=>{e.preventDefault();e.currentTarget.setPointerCapture(e.pointerId);setDragging(true);}}
          onPointerMove={e=>{if(!dragging||!grid.current)return;const rect=grid.current.getBoundingClientRect();setWidth(clamp((e.clientX-rect.left)/rect.width*100));}}
          onPointerUp={()=>setDragging(false)} onPointerCancel={()=>setDragging(false)} onLostPointerCapture={()=>setDragging(false)}/>
        <section className="pbl-result-pane" aria-label="预览与验收">
          <nav className="pbl-result-tabs" aria-label="项目结果"><button aria-pressed={panel==='preview'} onClick={()=>onPanel('preview')}>{previewLabel}</button><button aria-pressed={panel==='checks'} onClick={()=>onPanel('checks')}>验收</button></nav>
          <div hidden={panel!=='preview'} className="pbl-preview-panel">{preview}</div>
          <div hidden={panel!=='checks'} className="pbl-result-scroll">{checks}</div>
        </section>
      </SandpackLayout>
    </div>
  </div>;
}
