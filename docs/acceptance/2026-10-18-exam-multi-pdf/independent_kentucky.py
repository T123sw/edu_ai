"""Independent recomputation of six numerical subquestions from a frozen successful run."""
from pathlib import Path
import json,re,ast
R=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parent
r=json.loads((R/'.runtime/exam-multi-pdf-20261018/examgen_999feff63616eb873d1cf26a5f446513-production.json').read_text());qs=[x['qa_pair'] for x in r['result']['metadata']['summary']['results']];checks=[]
def record(parent,child,actual,claimed):checks.append(dict(parent=parent,child=child,actual=actual,claimed=claimed,passed=actual==claimed))
def array(text):return ast.literal_eval(re.search(r'\[[0-9, ]+\]',text)[0])
q=qs[1]['children'][0];operations=re.search(r'`(I3[^`]+)`',q['question'])[1].split();a=[None]*5;front=rear=0
for op in operations:
 if op=='D':a[front]=None;front=(front+1)%5
 else:a[rear]=int(op[1:]);rear=(rear+1)%5
claimed=re.search(r'\[([^]]+)\]',q['correct_answer'])[1];claimed=[None if x.strip()=='-' else int(x) for x in claimed.split(',')];claimed_positions=[int(re.search(key+r'\s*=\s*(\d+)',q['correct_answer'])[1]) for key in ['front','rear']];record(2,1,[a,front,rear],[claimed,*claimed_positions])
q=qs[1]['children'][1];a=array(q['question'])
for i in range(3):
 j=min(range(i,len(a)),key=a.__getitem__);a[i],a[j]=a[j],a[i]
record(2,2,a,array(q['correct_answer']))
q=qs[1]['children'][2];a=array(q['question']);pivot=a[-1];i=0
for j in range(len(a)-1):
 if a[j]<=pivot:a[i],a[j]=a[j],a[i];i+=1
a[i],a[-1]=a[-1],a[i];record(2,3,[a,i],[array(q['correct_answer']),int(re.search(r'下标为 (\d+)',q['correct_answer'])[1])])
q=qs[1]['children'][3];values=list(map(int,re.search(r'`([^`]+)`',q['question'])[1].split(',')));a=[]
for x in values:
 a.append(x);i=len(a)-1
 while i>0 and a[i]>a[(i-1)//2]:j=(i-1)//2;a[i],a[j]=a[j],a[i];i=j
record(2,4,a,array(q['correct_answer']))
q=qs[2]['children'][4];a=array(q['question'])
for root in range(len(a)//2-1,-1,-1):
 i=root
 while 2*i+1<len(a):
  j=2*i+1
  if j+1<len(a) and a[j+1]<a[j]:j+=1
  if a[i]<=a[j]:break
  a[i],a[j]=a[j],a[i];i=j
record(3,5,a,array(q['correct_answer']))
q=qs[3]['children'][2];a=[(x,[]) for x in array(q['question'])];comparisons=0
while len(a)>1:
 next_round=[]
 for left,right in zip(a[::2],a[1::2]):
  comparisons+=1;winner,loser=(left,right) if left[0]>right[0] else (right,left);next_round.append((winner[0],winner[1]+[loser[0]]))
 a=next_round
comparisons+=len(a[0][1])-1;record(4,3,comparisons,int(re.search(r'最少 (\d+) 次',q['correct_answer'])[1]))
report=dict(generation_id=r['id'],boundary='Six selected numerical subquestions only; not a full semantic or novelty review.',passed=sum(x['passed'] for x in checks),failed=sum(not x['passed'] for x in checks),checks=checks,manual_note='Question 3a correctly states expected logarithmic BST cost, but its categorical wording that a random insertion tree will not degenerate into a chain is too strong; this is an expectation, not an absolute guarantee.')
(O/'independent-kentucky-0013.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print({'passed':report['passed'],'failed':report['failed']});assert report['failed']==0
