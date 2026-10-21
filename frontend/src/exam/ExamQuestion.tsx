import { useEffect,useRef,useState } from 'react';
import { apiRequest, ApiError } from '../stitch/api/client';
import { QuizMarkdown } from '../liveLearning/QuizMarkdown';
import { ChoiceOptions } from '../liveLearning/ChoiceOptions';
import { type Answer,type Attempt,type Question,type Run,type Draft,emptyAnswer,filled,runPath,send,errorText } from './practiceApi';
const names:Record<string,string>={choice:'单选题',multiple_choice:'多选题',concept:'判断题',fill_in_blank:'填空题',short_answer:'简答题',written:'论述题',coding:'代码题'};
export type QuestionState={save:'saved'|'saving'|'pending';answer:'empty'|'draft'|'submitted'};
export type QuestionHandle={flush:()=>Promise<void>;pending:()=>Answer|undefined};
export type Reference={question_id:string;attempt_id?:string;draft?:Answer};
export function ExamQuestion({q,run,owner,selected,onFocus,onReference,onRefresh,register,onState}: {q:Question;run:Run;owner:string;selected:boolean;onFocus:()=>void;onReference:(ref:Reference,prompt:string)=>void;onRefresh:()=>Promise<void>;register:(id:string,handle:QuestionHandle|null)=>void;onState:(id:string,state:QuestionState)=>void}) {
  const path=runPath(run.paper_id,run.id),key=`exam-draft:${owner}:${run.version}:${run.id}:${q.question_id}`;
  const latest=run.answers[q.question_id]?.at(-1);
  const initial=run.drafts[q.question_id];
  const [value,setValue]=useState<Answer>(initial?.answer||latest?.answer||emptyAnswer(q));
  const [editing,setEditing]=useState(!latest||!!initial&&!initial.submitted);
  const [saved,setSaved]=useState('已保存'),[error,setError]=useState(''),[busy,setBusy]=useState(false),[conflict,setConflict]=useState<Draft>();
  const [selectedAttempt,setSelectedAttempt]=useState('');
  const attempt=(run.answers[q.question_id]||[]).find(a=>a.id===selectedAttempt)||latest;
  const current=useRef(value),revision=useRef(initial?.revision||0),dirty=useRef(false),edit=useRef(editing),alive=useRef(true),timer=useRef<ReturnType<typeof setTimeout>>(),saving=useRef<Promise<void>>();
  const pendingSubmit=useRef<{signature:string;id:string}>();
  const readOnly=run.status!=='active';
  const authorized=()=>{try{return JSON.parse(localStorage.getItem('edu-ai-auth')||'{}').user?.username===owner;}catch{return false;}};
  useEffect(()=>{
    if(readOnly){setEditing(false);edit.current=false;dirty.current=false;}
    if(!dirty.current&&latest){
      revision.current=run.drafts[q.question_id]?.revision||revision.current;
      if(!edit.current){current.current=latest.answer;setValue(latest.answer);}
    }
  },[readOnly,latest?.id,run.drafts,q.question_id]); // eslint-disable-line react-hooks/exhaustive-deps
  function local(answer:Answer){try{localStorage.setItem(key,JSON.stringify({answer,revision:revision.current}));}catch{/* Server persistence remains available. */}}
  async function flush(){
    clearTimeout(timer.current);
    if(saving.current){await saving.current;if(dirty.current)return flush();return;}
    if(!dirty.current||readOnly||!authorized())return;
    const snapshot=structuredClone(current.current);const expected=revision.current;
    const action=(async()=>{
      try{
        const response=await send<Draft>(`${path}/drafts/${encodeURIComponent(q.question_id)}`,{answer:snapshot,expected_revision:expected},'PUT');
        revision.current=response.revision;
        if(JSON.stringify(current.current)===JSON.stringify(snapshot)){dirty.current=false;localStorage.removeItem(key);if(alive.current)setSaved('已保存');}
        else local(current.current);
        if(alive.current){setError('');setConflict(undefined);}
      }catch(e){
        if(e instanceof ApiError&&e.status===409){const fresh=await apiRequest<Run>(path);if(alive.current)setConflict(fresh.drafts[q.question_id]);}
        if(alive.current){setSaved('待同步');setError(errorText(e));}throw e;
      }
    })();saving.current=action;
    try{await action;}finally{saving.current=undefined;}
    if(dirty.current)await flush();
  }
  const flushRef=useRef(flush);flushRef.current=flush;
  useEffect(()=>{
    alive.current=true;
    try{const cached=JSON.parse(localStorage.getItem(key)||'null');if(cached&&authorized()&&!readOnly){current.current=cached.answer;revision.current=cached.revision;dirty.current=true;edit.current=true;setValue(cached.answer);setEditing(true);setSaved('待同步');timer.current=setTimeout(()=>void flushRef.current().catch(()=>{}),600);}}catch{/* Invalid cache is not submitted. */}
    register(q.question_id,{flush:()=>flushRef.current(),pending:()=>edit.current&&filled(q,current.current)?current.current:undefined});
    const online=()=>void flushRef.current().catch(()=>{});
    const leaving=(e:BeforeUnloadEvent)=>{if(dirty.current){e.preventDefault();e.returnValue='';}};
    window.addEventListener('online',online);window.addEventListener('beforeunload',leaving);
    return()=>{alive.current=false;clearTimeout(timer.current);register(q.question_id,null);window.removeEventListener('online',online);window.removeEventListener('beforeunload',leaving);};
    // This component is keyed by run and question; polling must not overwrite an in-flight draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[key]);
  function change(answer:Answer){current.current=answer;dirty.current=true;setValue(answer);setSaved('保存中…');local(answer);clearTimeout(timer.current);timer.current=setTimeout(()=>void flushRef.current().catch(()=>{}),600);onFocus();}
  async function submit(){
    if(busy||!authorized())return;setBusy(true);setError('');
    try{await flush();const answer=current.current,signature=JSON.stringify(answer);
      if(!pendingSubmit.current){try{pendingSubmit.current=JSON.parse(localStorage.getItem(key+':submit')||'null')||undefined;}catch{/* A new request will be assigned. */}}
      if(pendingSubmit.current?.signature!==signature)pendingSubmit.current={signature,id:crypto.randomUUID()};
      localStorage.setItem(key+':submit',JSON.stringify(pendingSubmit.current));
      await send<Attempt>(`${path}/answers/${encodeURIComponent(q.question_id)}`,{request_id:pendingSubmit.current.id,answer});
      pendingSubmit.current=undefined;localStorage.removeItem(key+':submit');const fresh=await apiRequest<Run>(path);revision.current=fresh.drafts[q.question_id].revision;
      edit.current=false;setEditing(false);setSelectedAttempt('');dirty.current=false;localStorage.removeItem(key);await onRefresh();
    }catch(e){setError(errorText(e));}finally{setBusy(false);}
  }
  function reference(prompt:string){onReference({question_id:q.question_id,...(editing&&!readOnly?{draft:structuredClone(current.current)}:attempt?{attempt_id:attempt.id}:{})},prompt);}
  const shown=!editing&&attempt?attempt.answer:value;
  const hasAnswer=!!shown.text.trim()||shown.option_ids.length>0||shown.blank_values.some(v=>!!v.trim());
  const answerState=!editing&&attempt?'submitted':hasAnswer?'draft':'empty';
  const saveState=readOnly||saved==='已保存'?'saved':saved==='保存中…'?'saving':'pending';
  useEffect(()=>onState(q.question_id,{save:saveState,answer:answerState}),[onState,q.question_id,saveState,answerState]);
  const options=q.question_type==='concept'?[{id:'true',text:'正确'},{id:'false',text:'错误'}]:Object.entries(q.options||{}).map(([id,text])=>({id,text}));
  return <article id={`exam-question-${q.question_id}`} className={`exam-answer-card ${selected?'is-selected':''}`} onClickCapture={onFocus} onFocusCapture={onFocus}>
    <header><strong>第 {q.number} 题</strong><span>{names[q.question_type]||'简答题'}</span><button type="button" className="exam-link-question" aria-label={`关联第 ${q.number} 题`} aria-pressed={selected} onClick={onFocus}>{selected?'已关联':'关联此题'}</button>{!readOnly&&editing&&<small role="status">{saved}</small>}</header>
    <QuizMarkdown content={q.question}/>
    <fieldset disabled={busy||readOnly||!editing} aria-label={`第 ${q.number} 题作答`}>
      {options.length?<ChoiceOptions name={`${run.id}:${q.question_id}`} options={options} selected={shown.option_ids} multiple={q.question_type==='multiple_choice'} onChange={option_ids=>change({...value,option_ids})}/>:q.question_type==='fill_in_blank'?shown.blank_values.map((text,index)=><label className="exam-blank" key={index}>第 {index+1} 空<input aria-label={`第 ${q.number} 题第 ${index+1} 空`} value={text} onChange={e=>change({...value,blank_values:value.blank_values.map((v,i)=>i===index?e.target.value:v)})}/></label>):<textarea className={q.question_type==='coding'?'exam-code-answer':''} aria-label={`第 ${q.number} 题答案`} value={shown.text} maxLength={12000} onChange={e=>change({...value,text:e.target.value})} placeholder={q.question_type==='coding'?'在此输入代码…':'写下你的答案或解题过程…'}/>}
    </fieldset>
    {error&&<p role="alert" className="exam-error">{error}</p>}
    {conflict&&<div className="exam-actions"><button onClick={()=>{revision.current=conflict.revision;setConflict(undefined);void flush().catch(()=>{});}}>保留本地草稿</button><button onClick={()=>{revision.current=conflict.revision;current.current=conflict.answer;dirty.current=false;setValue(conflict.answer);localStorage.removeItem(key);setConflict(undefined);setError('');setSaved('已保存');}}>使用已保存版本</button></div>}
    {!editing&&attempt&&<div className="exam-answer-feedback" role="status"><strong>{attempt.status==='graded'?(attempt.evaluator==='model'?'AI 参考评价':attempt.correct?'回答正确':'回答有误'):attempt.status==='pending_evaluation'?'答案已保存，正在评价…':'答案已保存，评价暂不可用'}</strong>{attempt.feedback&&<QuizMarkdown content={attempt.feedback}/ >}{attempt.reference_answer&&<details><summary>参考答案</summary><QuizMarkdown content={attempt.reference_answer}/></details>}{attempt.status==='evaluation_failed'&&<button onClick={()=>void send(`${path}/answers/${q.question_id}/${attempt.id}/evaluate`).then(onRefresh).catch(e=>setError(errorText(e)))}>重新评价</button>}</div>}
    <div className="exam-actions">{!readOnly&&(editing?<button className="sl-primary" disabled={busy||!filled(q,value)||!!conflict} onClick={()=>void submit()}>{busy?'正在保存…':'提交答案'}</button>:<button onClick={()=>{edit.current=true;setEditing(true);current.current=emptyAnswer(q);change(current.current);}}>重新作答</button>)}<button onClick={()=>reference('先给我一个提示，不直接告诉我答案。')}>提示</button><button onClick={()=>reference('请完整讲解这道题的思路、步骤和易错点。')}>讲解</button></div>
    {(run.answers[q.question_id]?.length||0)>1&&<label className="exam-attempt-select">本题提交记录<select value={selectedAttempt||latest?.id} onChange={e=>{setSelectedAttempt(e.target.value);setEditing(false);edit.current=false;}}>{run.answers[q.question_id].map((a,i)=><option key={a.id} value={a.id}>第 {i+1} 次 · {new Date(a.created_at*1000).toLocaleString()}</option>)}</select></label>}
  </article>;
}
