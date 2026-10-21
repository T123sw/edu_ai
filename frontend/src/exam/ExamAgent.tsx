import { useEffect,useRef,useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { AgentComposer } from '../selfLearning/AgentComposer';
import { QuizMarkdown } from '../liveLearning/QuizMarkdown';
import { type Paper,type Run,type Turn,type Question,examPath,send,errorText,leaves } from './practiceApi';
import type { Reference } from './ExamQuestion';
export function ExamAgent({paper,run,owner,current,reference,onClear,onLocate}: {paper:Paper;run:Run;owner:string;current?:Question;reference?:{value:Reference;prompt:string;sequence:number};onClear:()=>void;onLocate:(id:string,runId?:string)=>void}) {
  const [turns,setTurns]=useState<Turn[]>([]),[question,setQuestion]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[more,setMore]=useState(false);
  const path=examPath(paper.generation_id)+'/agent-turns',key=`exam-chat-draft:${owner}:${paper.version}`;
  const composer=useRef<HTMLTextAreaElement>(null),history=useRef<HTMLDivElement>(null),stick=useRef(true),alive=useRef(true);
  const panel=useRef<HTMLElement>(null),[panelHeight,setPanelHeight]=useState(650),oldestLoaded=useRef(false);
  const pending=useRef<{signature:string;id:string}>();
  const authorized=()=>{try{return JSON.parse(localStorage.getItem('edu-ai-auth')||'{}').user?.username===owner;}catch{return false;}};
  function updateDraft(value:string){setQuestion(value);try{localStorage.setItem(key,value);}catch{/* Server conversation is still preserved. */}}
  useEffect(()=>{try{setQuestion(localStorage.getItem(key)||'');}catch{/* Optional local input. */}},[key]);
  useEffect(()=>{
    const resize=()=>{if(panel.current?.getClientRects().length)setPanelHeight(Math.max(320,(window.visualViewport?.height||innerHeight)-Math.max(16,panel.current.getBoundingClientRect().top)-16));};
    const observer=new ResizeObserver(resize);if(panel.current)observer.observe(panel.current);
    window.addEventListener('scroll',resize,{passive:true});window.addEventListener('resize',resize);window.visualViewport?.addEventListener('resize',resize);resize();
    return()=>{observer.disconnect();window.removeEventListener('scroll',resize);window.removeEventListener('resize',resize);window.visualViewport?.removeEventListener('resize',resize);};
  },[]);
  useEffect(()=>{if(reference){updateDraft(reference.prompt);composer.current?.focus();}},[reference?.sequence]); // eslint-disable-line react-hooks/exhaustive-deps
  async function refresh(){
    const response=await apiRequest<{items:Turn[]}>(path);
    if(!alive.current||!authorized())return;
    setTurns(previous=>{const merged=new Map(previous.map(t=>[t.id,t]));response.items.forEach(t=>merged.set(t.id,t));return [...merged.values()].sort((a,b)=>a.created_at-b.created_at);});
    if(!oldestLoaded.current)setMore(response.items.length===30);setError('');
  }
  useEffect(()=>{
    alive.current=true;let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{await refresh();}catch(e){if(alive.current)setError(errorText(e));}if(alive.current)timer=setTimeout(()=>void poll(),2000);};void poll();
    return()=>{alive.current=false;clearTimeout(timer);};
    // One session spans every run and question of this version.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[path,owner]);
  useEffect(()=>{if(stick.current&&history.current)history.current.scrollTop=history.current.scrollHeight;},[turns]);
  const active=turns.some(t=>t.status==='pending');
  async function ask(){
    if(!question.trim()||busy||active||!authorized())return;setBusy(true);setError('');
    const qid=reference?.value.question_id||current?.question_id;
    const attempt=qid?run.answers[qid]?.at(-1):undefined;
    const ref=reference?.value||{question_id:qid,...(attempt?{attempt_id:attempt.id}:{})};
    const body={question:question.trim(),run_id:run.id,...ref},signature=JSON.stringify(body);
    if(pending.current?.signature!==signature)pending.current={signature,id:crypto.randomUUID()};
    try{await send(path,{...body,request_id:pending.current.id});pending.current=undefined;updateDraft('');onClear();stick.current=true;await refresh();}catch(e){setError(errorText(e));}finally{setBusy(false);}
  }
  async function older(){
    if(!turns.length)return;setBusy(true);
    try{const previousHeight=history.current?.scrollHeight||0;const data=await apiRequest<{items:Turn[]}>(`${path}?before=${turns[0].created_at}`);stick.current=false;setTurns(previous=>[...data.items,...previous]);oldestLoaded.current=data.items.length<30;setMore(!oldestLoaded.current);requestAnimationFrame(()=>{if(history.current)history.current.scrollTop=history.current.scrollHeight-previousHeight;});}catch(e){setError(errorText(e));}finally{setBusy(false);}
  }
  const focused=reference?.value.question_id||current?.question_id;
  return <aside ref={panel} style={{height:panelHeight}} className="exam-agent" aria-label="试卷学习 Agent"><header><strong>学习 Agent</strong><small>对话自动保存</small></header>
    <div className="exam-agent-history" ref={history} role="log" aria-label="当前试卷对话记录" onScroll={()=>{const e=history.current;if(e)stick.current=e.scrollHeight-e.clientHeight-e.scrollTop<60;}}>
      {more&&<button disabled={busy} onClick={()=>void older()}>加载更早对话</button>}
      {!turns.length&&<p className="exam-agent-empty">遇到不明白的地方，随时问我。你可以要一个提示，也可以一起梳理解题过程。</p>}
      {turns.map(t=><div key={t.id} className="exam-conversation"><div className="exam-message user"><small>你 · {new Date(t.created_at*1000).toLocaleTimeString()}{t.run_id!==run.id?' · 其他轮次':''}</small>{t.question_id&&<button onClick={()=>onLocate(t.question_id!,t.run_id)}>第 {t.question_number} 题</button>}<p>{t.question}</p></div><div className="exam-message assistant"><small>学习 Agent</small>{t.status==='succeeded'?<><QuizMarkdown content={t.answer}/>{t.citations.map(c=><button key={c.question_id} onClick={()=>onLocate(c.question_id,t.run_id)}>{c.label}</button>)}</>:t.status==='pending'?<><p role="status">正在思考…</p><button onClick={()=>void send(`${path}/${t.id}/cancel`).then(refresh).catch(e=>setError(errorText(e)))}>停止回答</button></>:<><p>{t.error||'本次回答未完成'}</p><button onClick={()=>void send(`${path}/${t.id}/retry`).then(refresh).catch(e=>setError(errorText(e)))}>重试回答</button></>}</div></div>)}
    </div>
    <div className="exam-agent-bottom">{error&&<p role="alert" className="exam-error">{error}</p>}<div className="exam-agent-reference">{focused?<><span>关联第 {reference?.value.question_id===current?.question_id||!reference?current?.number:leaves(paper.questions).find(q=>q.question_id===focused)?.number||''} 题{reference?.value.draft?' · 未提交草稿':reference?.value.attempt_id?' · 已提交答案':''}</span><button aria-label="取消题目引用" onClick={onClear}>×</button></>:<span>当前试卷</span>}</div>
      <div className="exam-actions"><button disabled={!focused} onClick={()=>updateDraft('先给我一个提示，不直接告诉我答案。')}>给我提示</button><button disabled={!focused} onClick={()=>updateDraft('请讲解当前题目的思路、步骤和易错点。')}>讲解本题</button></div>
      <AgentComposer value={question} onChange={updateDraft} onSend={()=>void ask()} disabled={busy||active} placeholder="问思路，或让我看看你的作答…" inputRef={composer}/>
    </div>
  </aside>;
}
