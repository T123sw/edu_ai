"""Recompute an asymptotic comparison claim made by the independent reviewer."""
from pathlib import Path
import json
O=Path(__file__).resolve().parent;R=O.parents[2]
r=json.loads((R/'.runtime/exam-multi-pdf-20261018/examgen_84063a92be99187d60738b6e120f254b-production.json').read_text())
q=r['result']['metadata']['summary']['results'][3]
assert '4n' in q['qa_pair']['question'] and '2n' in q['qa_pair']['question']
assert any('4n^2' in issue for issue in q['metadata']['issues'])
checks=[]
for n in [1,2,4,8,16,32,64]:
 a=['B']*n+['A']*(2*n)+['B']*n;comparisons=0
 for i in range(1,len(a)):
  x=a[i];j=i-1
  while j>=0:
   comparisons+=1
   if a[j]<=x:break
   a[j+1]=a[j];j-=1
  a[j+1]=x
 assert a==sorted(a) and comparisons==2*n*n+4*n-2
 checks.append({'n':n,'comparisons':comparisons,'comparisons_over_n_squared':comparisons/n**2})
report={'generation_id':r['id'],'ordinal':4,'child':'b','boundary':'Standard stable insertion sort; A sorts before B. Rechecks the reviewer arithmetic, not all reasons for rejecting the candidate.','reviewer_claim':'~4n^2','actual':'2n^2+4n-2; leading term ~2n^2','reviewer_arithmetic_correct':False,'candidate_answer_key':'C (~2n^2)','candidate_still_invalid_reasons':['Its step explanation mixes opposite A/B orderings.','The source task was copied without substantive changes.'],'checks':checks}
(O/'sorting-review-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print({'reviewer_arithmetic_correct':False,'actual':report['actual']})
