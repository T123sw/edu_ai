"""Export isolated run evidence and a readable path without provider credentials."""
import argparse,json,os
from pathlib import Path
from collections import Counter
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from core.config import Config
from app.database.models import PreparationAction,PreparationExecution,CoursePreparationRecord,MaterialVersion
p=argparse.ArgumentParser();p.add_argument('--preparation-id',required=True);p.add_argument('--output',required=True);a=p.parse_args()
engine=create_engine(os.environ['DATABASE_URL'])
if engine.url.database!='edu_ai_agent_stage':raise ValueError('isolated stage database required')
out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str))
with Session(engine) as db:
 prep=db.get(CoursePreparationRecord,a.preparation_id)
 if not prep.owner_user_id.startswith('stage-'):raise ValueError('isolated owner required')
 run=db.get(PreparationExecution,(a.preparation_id,prep.current_attempt_no));cp=run.checkpoint
 actions=list(db.scalars(select(PreparationAction).where(PreparationAction.preparation_id==a.preparation_id)))
 research=cp.get('research_state',{})
 evidence=research.get('evidence',[]);candidates=research.get('candidates',[])
 summary={'preparation_id':a.preparation_id,'attempt_no':prep.current_attempt_no,'actions':dict(Counter(x.kind for x in actions)),
  'models':sorted({x.payload['model'] for x in actions if x.kind=='model_completion'}),'candidate_count':len(candidates),'evidence_count':len(evidence),
  'findings_count':len(cp.get('research_summary',{}).get('findings',[])),'research_trace':research.get('trace',[])}
 save('execution-summary.json',summary)
 save('actions.json',[{'kind':r.kind,'status':r.status,'payload':r.payload,'receipt':r.receipt,'reserved':r.reserved,'consumed':r.consumed} for r in actions])
 save('sources.json',{'candidates':candidates,'evidence':[{'source_id':e.get('source_id'),'candidate_id':e.get('candidate_id'),'title':e.get('title'),'url':e.get('url'),'content_chars':len(e.get('text','') or e.get('content','')),'locator':e.get('locator')} for e in evidence]})
 manifest=cp.get('candidate_manifest')
 if manifest and run.result_ref and run.result_ref.get('course_ready'):
  save('manifest.json',manifest)
  lines=['# '+manifest['goal'],'',f"预计 {manifest['estimated_minutes']} 分钟；课程版本 {manifest['version']}。",'']
  for node in manifest['nodes']:
   lines.extend([f"## {node['order']}. {node['title']}（{node['estimated_minutes']} 分钟）",''])
   lines.extend('- '+o['text'] for o in node['objectives']);lines.append('')
   for r in node['resources']:
    material=db.scalar(select(MaterialVersion).where(MaterialVersion.course_id==manifest['course_id'],MaterialVersion.material_id==r['resource_id'],MaterialVersion.material_type==r['resource_type'],MaterialVersion.version==r['version']))
    if material is None:raise ValueError('committed exact material missing')
    filename=r['resource_id']+'.json';save(filename,material.payload)
    lines.append(f"- [{r['resource_type']} v{r['version']}]({filename})：{r['purpose']}")
   lines.append('')
  (out/'learning-path.md').write_text('\n'.join(lines))
 print(json.dumps({k:v for k,v in summary.items() if k!='research_trace'},ensure_ascii=False))
