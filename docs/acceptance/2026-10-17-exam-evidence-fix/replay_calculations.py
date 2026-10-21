"""Replay production calculation payloads against pre/post allocation guards; no model calls."""
import json,sqlite3,hashlib,collections,sys,types,importlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
modules=[]
for name,bundle in [('before_guard','bridge6'),('after_guard','bridge7')]:
 package=types.ModuleType(name);package.__path__=[str(ROOT/'.runtime/exam-quality-v7'/bundle/'.upstream/DeepTutor/deeptutor/agents/question')];sys.modules[name]=package
 modules.append(importlib.import_module(name+'.calculation_check'))
audit=json.loads((OUT/'online-audit.json').read_text());owner=json.loads((ROOT/'.runtime/exam-real-paper-e2e/auth.json').read_text())['username']
path=ROOT/'services/deeptutor/.runtime/data/users'/('edu_'+hashlib.sha256(owner.encode()).hexdigest())/'user/chat_history.db'
db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);report={'model_calls':0,'turns':[],'mismatches':[]};decoder=json.JSONDecoder()
for generation in audit['generations']:
 tid=generation['turn']['id'];groups=collections.defaultdict(str)
 for content,meta in db.execute("select content,metadata_json from turn_events where turn_id=? and type='thinking' order by seq",(tid,)):
  m=json.loads(meta or '{}')
  if m.get('trace_kind')=='llm_chunk' and m.get('call_id'):groups[m['call_id']]+=content
 count=0;expressions=0
 for call_id,content in groups.items():
  cursor=0
  while cursor<len(content):
   start=content.find('{',cursor)
   if start<0:break
   try:value,end=decoder.raw_decode(content[start:]);cursor=start+end
   except ValueError:cursor=start+1;continue
   if not isinstance(value,dict) or not isinstance(value.get('calculations'),list):continue
   old=modules[0].check_calculations(value['calculations'],allow_compute_only=True);new=modules[1].check_calculations(value['calculations'],allow_compute_only=True)
   count+=1;expressions+=len(value['calculations'])
   if old!=new:report['mismatches'].append({'turn_id':tid,'call_id':call_id})
 report['turns'].append({'turn_id':tid,'payloads':count,'expressions':expressions})
report['passed']=not report['mismatches'] and sum(x['payloads'] for x in report['turns'])>0
(OUT/'allocation-replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));assert report['passed']
