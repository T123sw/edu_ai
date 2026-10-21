import json,time,traceback
from pathlib import Path
from types import SimpleNamespace
from core.config import Config
from app.self_learning.service import gateway
from app.integrations.hyperframes.generation import generate_content
from app.integrations.hyperframes.projects import ProjectStore
from app.services.hyperframes_classroom import JobCheckpoint
rows=json.loads(Path('/tmp/hf-latest-analysis.json').read_text())
r=next(r for r in rows if r['spec']['node_id'].startswith('n4'))
request=json.loads((Path(r['workspace'])/'REQUEST.json').read_text())
root=Path('/home/zxqs_ep/data/main-review/hyperframes-teaching-brief-20261019');root.mkdir(parents=True,exist_ok=True)
payload=SimpleNamespace(title=r['spec']['title'],teaching_context=r['spec']['teaching_context'],research_context=request['sources'])
started=time.time()
(root/'input.json').write_text(json.dumps(vars(payload),ensure_ascii=False,indent=2))
try:
 result=generate_content(payload,gateway=gateway('teacher'),artifact={'resource_id':'teaching_brief_validation_20261019','spec_digest':'teaching-brief-v2-code-example'},store=ProjectStore(root/'projects'))
 out={'started_at':started,'finished_at':time.time(),'seconds':time.time()-started,'result':result}
 (root/'result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'seconds':out['seconds'],'duration':result['timeline']['duration'],'project':result['project']},ensure_ascii=False),flush=True)
except BaseException as e:
 (root/'failure.json').write_text(json.dumps({'started_at':started,'finished_at':time.time(),'error':str(e)},ensure_ascii=False));traceback.print_exc();raise
