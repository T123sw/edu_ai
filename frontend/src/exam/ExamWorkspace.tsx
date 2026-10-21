import { useCallback,useEffect,useRef,useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { QuizMarkdown } from '../liveLearning/QuizMarkdown';
import { sharedQuestionStem } from './questionPresentation';
import { ExamQuestion,type QuestionHandle,type QuestionState,type Reference } from './ExamQuestion';
import { ExamAgent } from './ExamAgent';
import { type Paper,type Question,type Run,type RunSummary,examPath,runPath,leaves,send,errorText } from './practiceApi';
import './examPractice.css';
export function ExamWorkspace({id,owner}: {id:string;owner:string}) {
  const [paper,setPaper]=useState<Paper>(),[run,setRun]=useState<Run>(),[error,setError]=useState(''),[retry,setRetry]=useState(0);
  const [focused,setFocused]=useState<string>(),[tab,setTab]=useState('answers'),[showNav,setShowNav]=useState(false),[reference,setReference]=useState<{value:Reference;prompt:string;sequence:number}>();
  const handles=useRef(new Map<string,QuestionHandle>()),startId=useRef(crypto.randomUUID());
  const [questionStates,setQuestionStates]=useState<Record<string,QuestionState>>({});
  const trackState=useCallback((qid:string,state:QuestionState)=>setQuestionStates(previous=>({...previous,[qid]:state})),[]);
  const alive=useRef(true),runRef=useRef(run);runRef.current=run;
  const register=useCallback((qid:string,handle:QuestionHandle|null)=>{if(handle)handles.current.set(qid,handle);else handles.current.delete(qid);},[]);
  const refresh=useCallback(async()=>{const rid=runRef.current?.id;if(!rid)return;const data=await apiRequest<Run>(runPath(id,rid));if(alive.current&&runRef.current?.id===rid)setRun(data);},[id]);
  useEffect(()=>{
    alive.current=true;const abort=new AbortController();
    async function load(){try{
      const value=await apiRequest<Paper>(examPath(id)+'/practice',{signal:abort.signal});if(abort.signal.aborted)return;setPaper(value);
      const records=await apiRequest<{items:RunSummary[]}>(examPath(id)+'/practice-runs',{signal:abort.signal});
      const chosen=records.items.find(r=>r.status==='active')||records.items[0];
      const attempt=chosen?await apiRequest<Run>(runPath(id,chosen.id),{signal:abort.signal}):await send<Run>(examPath(id)+'/practice-runs',{request_id:startId.current,new:false});
      if(!abort.signal.aborted){setRun(attempt);setFocused(leaves(value.questions)[0]?.question_id);setError('');}
    }catch(e){if(!abort.signal.aborted)setError(errorText(e));}}
    void load();return()=>{alive.current=false;abort.abort();};
  },[id,retry]);
  useEffect(()=>{let stopped=false,timer:ReturnType<typeof setTimeout>;const poll=async()=>{try{await refresh();}catch(e){if(!stopped)setError(errorText(e));}if(!stopped)timer=setTimeout(()=>void poll(),2500);};timer=setTimeout(()=>void poll(),2500);return()=>{stopped=true;clearTimeout(timer);};},[refresh]);
  async function flush(){for(const handle of handles.current.values())await handle.flush();}
  async function switchRun(rid:string){try{await flush();const value=await apiRequest<Run>(runPath(id,rid));setQuestionStates({});setRun(value);setReference(undefined);setError('');return true;}catch(e){setError(errorText(e));return false;}}
  function locate(qid:string){setFocused(qid);setReference(undefined);setTab('answers');setShowNav(false);requestAnimationFrame(()=>document.getElementById(`exam-question-${qid}`)?.scrollIntoView({block:'center',behavior:'smooth'}));}
  async function back(){try{await flush();location.hash='/exam';}catch(e){setError(errorText(e));}}
  if(!paper||!run)return <main className="exam-workspace"><a href="#/exam">← 我的试卷</a>{error?<div role="alert"><p>{error}</p><button onClick={()=>setRetry(n=>n+1)}>重新加载</button></div>:<p role="status">正在打开试卷与作答记录…</p>}</main>;
  const qs=leaves(paper.questions),current=qs.find(q=>q.question_id===focused),submitted=Object.values(run.answers).filter(a=>a.length).length;
  function render(q:Question){return q.children.length?<section className="exam-question-group" key={q.question_id}><h2>第 {q.number} 大题</h2><QuizMarkdown content={sharedQuestionStem(q.question,q.children)}/>{q.children.map(render)}</section>:<ExamQuestion key={`${run!.id}:${q.question_id}`} q={q} run={run!} owner={owner} selected={focused===q.question_id} onFocus={()=>{if(focused!==q.question_id){setFocused(q.question_id);setReference(undefined);}}} onReference={(value,prompt)=>{setFocused(q.question_id);setReference({value,prompt,sequence:Date.now()});setTab('chat');}} onRefresh={refresh} register={register} onState={trackState}/>;}
  const answerState=(q:Question)=>questionStates[q.question_id]?.answer||(run.answers[q.question_id]?.length?'submitted':run.drafts[q.question_id]&&[...run.drafts[q.question_id].answer.option_ids,...run.drafts[q.question_id].answer.blank_values,run.drafts[q.question_id].answer.text].some(v=>v.trim())?'draft':'empty');
  const completed=qs.filter(q=>answerState(q)!=='empty').length;
  const saveState=Object.values(questionStates).some(s=>s.save==='pending')?'pending':Object.values(questionStates).some(s=>s.save==='saving')?'saving':'saved';
  return <main className={`exam-workspace exam-tab-${tab}`}>
    <header className="exam-workspace-header"><button onClick={()=>void back()}>← 我的试卷</button><div><h1>{paper.title}</h1><p>{paper.questions.length!==paper.answer_count?`${paper.questions.length} 道大题 · `:''}共 {paper.answer_count} 题 · 已提交 {submitted} 题</p></div><span className={`exam-save-status is-${saveState}`} role="status">{saveState==='pending'?'已存本地，待同步':saveState==='saving'?'正在保存…':'作答自动保存'}</span></header>
    {error&&<p className="exam-error" role="alert">{error}</p>}
    <div className="exam-mobile-tabs"><button aria-pressed={tab==='answers'} onClick={()=>setTab('answers')}>作答</button><button aria-pressed={tab==='chat'} onClick={()=>setTab('chat')}>问答</button><button aria-expanded={showNav} onClick={()=>setShowNav(v=>!v)}>答题卡</button></div>
    <div className="exam-workspace-grid"><nav className={`exam-answer-nav ${showNav?'is-open':''}`} aria-label="答题卡"><header><strong>答题卡</strong><span>{completed}<small> / {paper.answer_count}</small></span></header><div className="exam-nav-progress" role="progressbar" aria-label="已填写题数" aria-valuemin={0} aria-valuemax={paper.answer_count} aria-valuenow={completed}><span style={{width:`${paper.answer_count?completed/paper.answer_count*100:0}%`}}/></div><div className="exam-nav-questions">{qs.map(q=>{const state=answerState(q);return <button key={q.question_id} aria-label={`第 ${q.number} 题，${state==='submitted'?'已提交':state==='draft'?'已填写':'未答'}`} aria-current={focused===q.question_id?'true':undefined} className={`is-${state}`} onClick={()=>locate(q.question_id)}>{q.number}</button>;})}</div></nav>
      <section className="exam-answer-sheet" aria-label="试卷作答">{paper.questions.map(render)}</section>
      <ExamAgent paper={paper} run={run} owner={owner} current={current} reference={reference} onClear={()=>{setReference(undefined);setFocused(undefined);}} onLocate={(qid,rid)=>{if(rid&&rid!==run.id)void switchRun(rid).then(ok=>{if(ok)locate(qid);});else locate(qid);}}/>
    </div>
  </main>;
}
