"""Read-only checks against the deployed API for the dedicated acceptance account."""
import json,sys,urllib.request,urllib.error,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/sys.argv[1]
auth=json.loads((ROOT/'.runtime/exam-real-paper-e2e/auth.json').read_text());browser=json.loads((OUT/'online-browser.json').read_text())
def get(path,anonymous=False):
 req=urllib.request.Request('http://127.0.0.1/backend/api'+path,headers={} if anonymous else {'Authorization':'Bearer '+auth['token']})
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,None
report={'generation_checks':[]}
def forbidden(value,path=''):
 if isinstance(value,dict):
  return [path+'.'+k for k in value if k in {'correct_answer','correct_answers','blank_answers','explanation','reference_answer','encrypted_snapshot'}]+[x for k,v in value.items() for x in forbidden(v,path+'.'+k)]
 if isinstance(value,list):return [x for i,v in enumerate(value) for x in forbidden(v,path+f'[{i}]')]
 return []
def shape(node):return (node.get('question_id'),node.get('question_type'),tuple(shape(c) for c in node.get('children') or []))
for gid in browser['generations']:
 code,paper=get('/exam-generations/'+gid+'/paper');anonymous,_=get('/exam-generations/'+gid+'/paper',True)
 record=json.loads((ROOT/'.runtime/exam-multi-pdf-20261018'/(gid+'-production.json')).read_text())
 summary=(record.get('result') or {}).get('metadata',{}).get('summary',{});bp=(record.get('blueprint') or {}).get('questions',[])
 entry={'generation_id':gid,'paper_http':code,'anonymous_http':anonymous,'answer_fields':forbidden(paper),'blueprint_count':len(bp),'blueprint_types':dict(collections.Counter(n['question_type'] for n in bp)), 'blueprint_child_counts':[len(n.get('children') or []) for n in bp]}
 if code==200:
  entry['all_shapes_match_blueprint']=[shape(q['qa_pair']) for q in summary['results']]==[shape(q) for q in bp]
  entry['all_accepted']=all(q['metadata'].get('review_passed') for q in summary['results'])
  entry['result_count']=len(summary['results'])
  assert entry['all_shapes_match_blueprint'] and entry['all_accepted']
 assert anonymous==401 and not entry['answer_fields']
 assert code==200 if summary.get('success') else code==409
 report['generation_checks'].append(entry)
(OUT/'online-boundary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
