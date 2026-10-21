import { useEffect, useRef, useState, type ReactNode } from 'react';
import './workbenchScroll.css';

export function WorkbenchStage({children,tutorOpen,onTutorToggle,controls}: {children:ReactNode;controls:ReactNode;tutorOpen:boolean;onTutorToggle():void}) {
  const stage=useRef<HTMLElement>(null);
  const content=useRef<HTMLDivElement>(null);
  const [focused,setFocused]=useState(false);
  useEffect(()=>{
    const node=stage.current,scroller=node?.closest<HTMLElement>('.sl-app');
    if(!node||!scroller)return;
    let atWorkspace=false;
    const heading=node.parentElement?.querySelector('.pbl-project-heading');
    let layout='';
    let lockedUntil=0,wheelTotal=0,lastWheel=0;
    const wheel=(event:WheelEvent)=>{
      if(event.ctrlKey||Math.abs(event.deltaX)>=Math.abs(event.deltaY))return;
      const now=performance.now();
      if(now<lockedUntil){event.preventDefault();return;}
      const target=event.target instanceof Element?event.target:null;
      // Once inside, scrolling code, results, steps or conversation belongs to that pane.
      if(atWorkspace&&target?.closest('.pbl-workbench-body,.pbl-project-tools'))return;
      if(target?.closest('dialog,textarea,pre'))return;
      const top=node.getBoundingClientRect().top-scroller.getBoundingClientRect().top;
      const entering=!atWorkspace&&event.deltaY>0&&top<scroller.clientHeight*.85;
      const exitZone=target?.closest('.pbl-stage-toolbar')?.getBoundingClientRect();
      const leaving=atWorkspace&&event.deltaY<0&&Boolean(exitZone&&event.clientY>=exitZone.top&&event.clientY<=exitZone.bottom);
      if(!entering&&!leaving)return;
      event.preventDefault();
      const delta=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?scroller.clientHeight:1);
      if(now-lastWheel>200||Math.sign(delta)!==Math.sign(wheelTotal))wheelTotal=0;
      lastWheel=now;wheelTotal+=delta;
      if(Math.abs(wheelTotal)<40)return;
      wheelTotal=0;
      const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      lockedUntil=now+(reduced?180:700);
      scroller.scrollTo({top:entering?scroller.scrollTop+top:0,behavior:reduced?'instant':'smooth'});
    };
    const update=()=>{
      const nextLayout=`${scroller.clientWidth}:${scroller.clientHeight}:${heading?.getBoundingClientRect().height}`;
      // Resize can dispatch scroll before ResizeObserver; anchor before evaluating the mode.
      if(atWorkspace&&layout!==nextLayout)scroller.scrollTo({top:scroller.scrollTop+node.getBoundingClientRect().top-scroller.getBoundingClientRect().top,behavior:'instant'});
      layout=nextLayout;
      atWorkspace=Math.abs(node.getBoundingClientRect().top-scroller.getBoundingClientRect().top)<3;
      if(content.current)content.current.inert=!atWorkspace;
      setFocused(atWorkspace);
    };
    scroller.scrollTo({top:0,behavior:'instant'});
    update();
    scroller.addEventListener('scroll',update,{passive:true});
    scroller.addEventListener('wheel',wheel,{passive:false,capture:true});
    const resize=new ResizeObserver(update);
    resize.observe(scroller);
    if(heading)resize.observe(heading);
    return()=>{scroller.removeEventListener('scroll',update);scroller.removeEventListener('wheel',wheel,true);resize.disconnect();};
  },[]);
  const enter=()=>{stage.current?.querySelector<HTMLButtonElement>('.pbl-stage-toolbar button')?.focus({preventScroll:true});stage.current?.scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});};
  const leave=()=>{stage.current?.parentElement?.querySelector<HTMLElement>('.pbl-project-heading')?.focus({preventScroll:true});stage.current?.closest('.sl-app')?.scrollTo({top:0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});};
  return <section ref={stage} className="pbl-workbench-stage" aria-label="编程工作区" data-focused={focused}>
    <header className="pbl-stage-toolbar">
      <button onClick={leave}>↑ 返回题目</button>
      <span>工作区</span>
      <div className="pbl-stage-controls">
      <button id="pbl-tutor-toggle" className="pbl-tutor-launch" aria-expanded={tutorOpen} aria-controls="pbl-tutor-sidebar" onClick={onTutorToggle}>AI 辅导</button>
      {controls}
      </div>
    </header>
    <div className="pbl-stage-main">
    <div ref={content} className="pbl-stage-content">{children}</div>
    {!focused&&<button className="pbl-stage-entry" onClick={enter} aria-label="展开工作区"><span>打开工作区</span></button>}
    </div>
  </section>;
}
