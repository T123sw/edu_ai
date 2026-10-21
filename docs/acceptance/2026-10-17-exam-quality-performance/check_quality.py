"""Real blind-solver regression on previously generated answers; model supplied on stdin."""
import asyncio,json,sys,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
os.environ['DEEPTUTOR_HOME']=str(ROOT/'.runtime/exam-quality-performance')
from edu_deeptutor.runtime import model_scope
from deeptutor.agents.question.pipeline import QuestionPipeline,QuizTemplate,build_openai_client
from deeptutor.runtime.stream_bus import StreamBus
model=json.load(sys.stdin)
old=json.loads((ROOT/'.runtime/exam-real-paper-e2e/isolated-fb46185c/result.json').read_text())['metadata']['summary']
latest=next(e['metadata']['summary'] for e in json.loads((ROOT/'.runtime/exam-real-paper-e2e/retest-upstream-final.json').read_text()) if e['type']=='result')
cases=[('old_binary',old,7,False),('old_partition',old,8,False),('old_tree',old,26,False),('new_arithmetic',latest,20,False),('new_tree',latest,26,False),('correct_binary',latest,7,True),('correct_partition',latest,8,True)]
# A fresh full-run counterexample: two options satisfy the heap condition.
partial=json.loads((OUT/'review-only-full-canceled.json').read_text())
record=json.loads((Path(partial['run_directory'])/'record.json').read_text())
heap=next(e['metadata']['qa_pair'] for e in record['events'] if e.get('metadata',{}).get('question_index')==11 and e['metadata'].get('qa_pair'))
cases.append(('fresh_heap_multiple_answers',{'blueprint':{'questions':[record['blueprint']['questions'][11]]},'results':[{'qa_pair':heap}]},1,False))
rows=[];gate=asyncio.Semaphore(2)
async def one(name,s,ordinal,expected):
 async with gate:
  with model_scope(model,[]):
   p=QuestionPipeline(language='zh');client=build_openai_client(p.client_config)
   n=s['blueprint']['questions'][ordinal-1];q=s['results'][ordinal-1]['qa_pair'];t=QuizTemplate(n['question_id'],n['concept'],n['question_type'],'medium',source='mimic',reference_question=n['reference_question'],blueprint=n)
   started=time.monotonic()
   steps=[];original_step=p._run_labeled_step
   async def trace(**kwargs):
    kwargs['reasoning_effort']=os.environ.get('EXAM_REVIEW_EFFORT',kwargs.get('reasoning_effort'));result=await original_step(**kwargs);steps.append(result.text);(ROOT/'.runtime'/('quality-'+name+'.json')).write_text(json.dumps(steps,ensure_ascii=False));return result
   p._run_labeled_step=trace
   try:
    issues=await p._review_mimic(t,q,'保持原题型和考点，生成使用不同有效数据的新题。',StreamBus(),client,[])
    entry={'case':name,'expected_accept':expected,'accepted':not issues,'issues':issues,'seconds':round(time.monotonic()-started,2)}
    rows.append(entry);(OUT/'quality-cases.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(json.dumps(entry,ensure_ascii=False),flush=True)
   finally:
    pass  # Upstream client factory pools clients across concurrent calls.
async def main():await asyncio.gather(*(one(*args) for args in cases))
asyncio.run(main())
