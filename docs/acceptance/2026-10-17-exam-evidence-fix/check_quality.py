"""Real blind-solver regression on previously generated answers; model supplied on stdin."""
import asyncio,json,sys,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
os.environ['DEEPTUTOR_HOME']=str(ROOT/'.runtime/exam-quality-v7/modelrun')
from edu_deeptutor.runtime import model_scope
from deeptutor.agents.question.pipeline import QuestionPipeline,QuizTemplate,build_openai_client
from deeptutor.runtime.stream_bus import StreamBus
model=json.load(sys.stdin)
old=json.loads((ROOT/'.runtime/exam-real-paper-e2e/isolated-fb46185c/result.json').read_text())['metadata']['summary']
latest=next(e['metadata']['summary'] for e in json.loads((ROOT/'.runtime/exam-real-paper-e2e/retest-upstream-final.json').read_text()) if e['type']=='result')
cases=[('old_binary',old,7,False),('old_partition',old,8,False),('old_tree',old,26,False),('new_arithmetic',latest,20,False),('new_tree',latest,26,False),('correct_binary',latest,7,True),('correct_partition',latest,8,True)]
# A fresh full-run counterexample: two options satisfy the heap condition.
partial=json.loads((ROOT/'docs/acceptance/2026-10-17-exam-quality-performance/review-only-full-canceled.json').read_text())
record=json.loads((Path(partial['run_directory'])/'record.json').read_text())
heap=next(e['metadata']['qa_pair'] for e in record['events'] if e.get('metadata',{}).get('question_index')==11 and e['metadata'].get('qa_pair'))
cases.append(('fresh_heap_multiple_answers',{'blueprint':{'questions':[record['blueprint']['questions'][11]]},'results':[{'qa_pair':heap}]},1,False))
record=json.loads((ROOT/'.runtime/exam-real-paper-e2e/examgen_cee3918f6e261eafdd101822d15e2df0-record.json').read_text())
bad_tree=json.loads((ROOT/'.runtime/exam-quality-v7/false-positive-tree.json').read_text())
cases.append(('fresh_tree_false_acceptance',{'blueprint':{'questions':[record['blueprint']['questions'][25]]},'results':[{'qa_pair':bad_tree}]},1,False))
node=record['blueprint']['questions'][25]
q={'question_id':node['question_id'],'question_type':'compound','question':'完全二叉树有27个结点，按层序从1编号至27。左、右孩子编号为2i、2i+1。S编号25。回答：(1) S在根的哪棵子树？(2) S所在的根的子树中，编号小于S的叶子有几个？(3) 该子树共有4层，写出根编号与最大编号。',
'correct_answer':'(1)右子树；(2)3个；(3)根3，最大27。','explanation':'25的祖先路径为1,3,6,12,25，故在右子树。右子树叶子为14,15,24,25,26,27，其中小于25的是14,15,24，共3个。右子树第1层3，第2层6,7，第3层12,13,14,15，第4层24,25,26,27。',
'children':[{'question_id':node['children'][i]['question_id'],'question_type':'short_answer','question':text,'correct_answer':answer,'explanation':proof} for i,(text,answer,proof) in enumerate([
('S在根的哪棵子树？','右子树','祖先路径1,3,6,12,25经过3。'),('所在子树编号更小的叶子有几个？','3','叶子14,15,24小于25。'),('该子树有4层，根与最大编号是多少？','根3，最大27','各层为3；6,7；12,13,14,15；24,25,26,27。')])]}
cases.append(('correct_tree_variant',{'blueprint':{'questions':[node]},'results':[{'qa_pair':q}]},1,True))
node=record['blueprint']['questions'][28]
q={'question_type':'written','question':'矩阵A[6][6]下标均为0..5，仅满足5-i<=j<=6-i且在下标范围内的位置有非零元素。按行优先将非零元素依次存到B[0..10]。写出位置(i,j)到k的分段关系，并给出A[2][3]的k及B[8]对应位置。','correct_answer':'i=0,j=5时k=0；i>=1,j=5-i时k=2i-1；i>=1,j=6-i时k=2i。A[2][3]的k=3；B[8]对应A[4][2]。','explanation':'第0行只有(0,5)，其后每行两个元素，因此共11个。行i>=1前共有1+2(i-1)个元素，两列依次为5-i和6-i。A[2][3]为第2行第一个位置，k=3；k=8为第4行第二个位置，即(4,2)。'}
cases.append(('correct_matrix_boundary',{'blueprint':{'questions':[node]},'results':[{'qa_pair':q}]},1,True))
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
