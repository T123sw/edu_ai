import { useEffect, useState } from 'react';

export function useWorkbenchTutor() {
  const [tutorOpen,setTutorOpen]=useState(()=>window.matchMedia('(min-width:1200px)').matches);
  const [tutorVisited,setTutorVisited]=useState(tutorOpen);
  useEffect(()=>{
    const media=window.matchMedia('(min-width:1200px)');
    const resize=()=>{if(!media.matches)setTutorOpen(false);};
    media.addEventListener('change',resize);
    return()=>media.removeEventListener('change',resize);
  },[]);
  const openTutor=()=>{setTutorVisited(true);setTutorOpen(true);};
  const closeTutor=()=>{setTutorOpen(false);document.getElementById('pbl-tutor-toggle')?.focus();};
  const toggleTutor=()=>{if(tutorOpen)closeTutor();else openTutor();};
  return {tutorOpen,tutorVisited,openTutor,closeTutor,toggleTutor};
}
