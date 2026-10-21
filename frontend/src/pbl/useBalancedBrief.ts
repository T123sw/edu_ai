import {useEffect,useLayoutEffect,type RefObject} from 'react';

const useBrowserLayoutEffect=typeof window==='undefined'?useEffect:useLayoutEffect;

/** Balance complete sections using their rendered heights, without splitting text. */
export function useBalancedBrief(ref:RefObject<HTMLDivElement>,contentKey:string) {
  useBrowserLayoutEffect(()=>{
    const root=ref.current?.querySelector<HTMLElement>('.pbl-brief-columns');
    if(!root||root.children.length!==2)return;
    let width=-1,frame=0,alive=true;
    const balance=()=>{
      if(!alive)return;
      width=root.clientWidth;
      root.style.removeProperty('grid-template-columns');
      root.style.removeProperty('--pbl-brief-fraction');
      if(window.matchMedia('(max-width:1100px)').matches)return;
      const [left,right]=Array.from(root.children) as HTMLElement[];
      let best=.5,score=Infinity;
      // Keep both columns readable; prefer the central divider when heights tie.
      for(let n=0;n<=14;n++){
        const ratio=.36+n*.02;
        root.style.gridTemplateColumns=`minmax(0,${ratio}fr) minmax(0,${1-ratio}fr)`;
        const difference=Math.abs(left.getBoundingClientRect().height-right.getBoundingClientRect().height)+Math.abs(ratio-.5)*20;
        if(difference<score){score=difference;best=ratio;}
      }
      root.style.gridTemplateColumns=`minmax(0,${best}fr) minmax(0,${1-best}fr)`;
      root.style.setProperty('--pbl-brief-fraction',String(best));
    };
    const schedule=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(balance);};
    balance();
    const observer=new ResizeObserver(()=>{if(root.clientWidth!==width)schedule();});
    observer.observe(root);
    window.addEventListener('resize',schedule);
    root.addEventListener('load',schedule,true);
    void document.fonts.ready.then(()=>{if(alive)schedule();});
    return()=>{alive=false;observer.disconnect();root.removeEventListener('load',schedule,true);window.removeEventListener('resize',schedule);cancelAnimationFrame(frame);};
  },[ref,contentKey]);
}
