"""Independent deterministic recomputation of sampled 0010 accepted questions.

Input is a private frozen production result. No model is used for these checks.
"""
import json,re,itertools,heapq
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
r=json.loads((ROOT/'.runtime/exam-multi-pdf-20261018/examgen_ea63cd431d846f6740ee9f972e7761bf-production.json').read_text())
qs=[x['qa_pair'] for x in r['result']['metadata']['summary']['results']]
report={'generation_id':r['id'],'boundary':'Independent code recomputation of seven selected accepted questions; not all questions or all explanations.','checks':[]}
def record(number,passed,**facts):
 report['checks'].append({'ordinal':number,'question_id':qs[number-1]['question_id'],'passed':passed,**facts})
def edges(q):return {(u,v):int(w) for u,v,w in re.findall(r'w\(([A-Z]),([A-Z])\)=(\d+)',q['question'])}
def mst_weight(vertices,es):
 best=None
 for group in itertools.combinations(es,len(vertices)-1):
  seen={vertices[0]}
  for _ in vertices:
   for u,v in group:
    if u in seen or v in seen:seen.update([u,v])
  if len(seen)==len(vertices):
   total=sum(es[e] for e in group);best=total if best is None else min(best,total)
 return best
q=qs[7];es=edges(q);assert es=={('A','B'):1,('A','C'):2,('B','C'):1,('B','D'):3,('C','D'):3}
d={x:float('inf') for x in 'ABCD'};d['A']=0
for _ in range(4):
 for (u,v),w in es.items():d[v]=min(d[v],d[u]+w);d[u]=min(d[u],d[v]+w)
claimed=int(re.search(r'd\(A,D\)=(\d+)',q['explanation'])[1])
record(8,claimed==d['D'],distances=d,claimed_distance_to_D=claimed,actual_distance_to_D=d['D'],mst_weight=mst_weight('ABCD',es),issue='Explanation says distance A→D is 3; it is 1+3=4. Final true/false conclusion can still be correct.')
valid=set()
def stacks(next_value,stack,out):
 if len(out)==4:valid.add(tuple(out));return
 if next_value<=4:stacks(next_value+1,stack+[next_value],out)
 if stack:stacks(next_value,stack[:-1],out+[stack[-1]])
stacks(1,[],[]);q=qs[11];impossible=[k for k,v in q['options'].items() if tuple(map(int,re.findall(r'\d+',v))) not in valid]
record(12,impossible==[q['correct_answer']],impossible_options=impossible,valid_stack_permutations=len(valid))
q=qs[21];dag=re.findall(r'([A-Z])\\to ([A-Z])',q['question']);assert len(dag)==5
orders=[p for p in itertools.permutations('ABCDE') if all(p.index(u)<p.index(v) for u,v in dag)]
record(22,int(q['options'][q['correct_answer']])==len(orders),topological_orders=[''.join(p) for p in orders])
q=qs[22];es=edges(q);best=mst_weight('ABCDE',es);options={}
for key,value in q['options'].items():
 group=re.findall(r'\(([A-Z]),([A-Z])\)',value);ge={e:es[e] for e in group};options[key]=mst_weight('ABCDE',ge)
correct=[key for key,value in options.items() if value==best]
record(23,correct==[q['correct_answer']],minimum_weight=best,option_tree_weights=options,correct_options=correct)
q=qs[27];weights=[Fraction(s) for s in re.findall(r'(?<![\d.])0\.\d+',q['question'])[:5]];assert weights==list(map(Fraction,['0.05','0.10','0.15','0.30','0.40']))
heap=[(w,i,{chr(97+i):0}) for i,w in enumerate(weights)];heapq.heapify(heap);serial=5
while len(heap)>1:
 wa,_,a=heapq.heappop(heap);wb,_,b=heapq.heappop(heap)
 combined={k:v+1 for k,v in {**a,**b}.items()};heapq.heappush(heap,(wa+wb,serial,combined));serial+=1
lengths=heap[0][2];average=sum(weights[i]*lengths[chr(97+i)] for i in range(5))
expected=['A','B'];actual=q['correct_answers']
record(28,actual==expected,huffman_lengths=lengths,average_code_length=float(average),expected_options=expected,accepted_options=actual,issue='Accepted option C claims length(a)=3, but it is 4; the explanation also gives incorrect lengths and average 1.75 instead of 2.05.')
q=qs[31];a=list(map(int,re.findall(r'\d+',re.search(r'\{([^}]+)\}',q['question'])[1])));rows=[]
for i in range(1,len(a)):
 comparisons=swaps=0;j=i
 while j>0:
  comparisons+=1
  if a[j]>=a[j-1]:break
  a[j],a[j-1]=a[j-1],a[j];swaps+=1;j-=1
 if i>=2:rows.append([a.copy(),comparisons,swaps])
claims=[]
for line in q['correct_answer'].splitlines():
 if line.startswith('| 第 ') and '元素（' in line:
  cells=line.split('|');claims.append([list(map(int,re.findall(r'\d+',cells[2]))),int(cells[3]),int(cells[4])])
record(32,rows==claims,insertion_states=rows)
q=qs[32];a=[3,14,12,7,1,9];b=[9,3,14,12,7,1]
def inv(a):return [(x,y) for i,x in enumerate(a) for y in a[i+1:] if x>y]
actual=[int(x) for x in re.findall(r'共 (\d+) 对',q['correct_answer'])]
record(33,actual==[len(inv(a)),len(inv(b))],original_pairs=inv(a),rotated_pairs=inv(b),claimed_counts=actual)
report['passed']=sum(c['passed'] for c in report['checks']);report['failed']=sum(not c['passed'] for c in report['checks'])
(OUT/'independent-checks-0010.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':report['passed'],'failed':report['failed'],'failed_ordinals':[c['ordinal'] for c in report['checks'] if not c['passed']]}))
