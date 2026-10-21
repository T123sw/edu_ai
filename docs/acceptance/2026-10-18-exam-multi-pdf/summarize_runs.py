"""Summarize observed attempts without treating API success as paper-quality acceptance."""
import json,collections
from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parents[2];W=R/'.runtime/exam-multi-pdf-20261018'
rows=[];fidelity=[];cases=[]
for f in sorted(O.glob('*/online-audit.json')):
 label=f.parent.name;sample=label.split('-')[0];a=json.loads(f.read_text());b=json.loads(f.with_name('online-browser.json').read_text())
 cases.append({'label':label,'ui_acceptance_passed':bool(b.get('completed') and not b.get('failure') and b.get('questions')==b.get('expected_questions') and len(b.get('viewports',[]))==3),'browser_failure':b.get('failure'),'controlled_stop':b.get('stop_reason') or b.get('interruption_reason')})
 for g in a['generations']:
  t=g['turn'];s=g['summary'];rows.append(dict(label=label,generation_id=g['generation_id'],turn_status=t['status'],blueprint_count=g['blueprint_count'],accepted=s.get('completed'),requested=s.get('requested'),pipeline_success=s.get('success'),seconds=round(t['updated_at']-t['created_at'],2) if t['status']!='running' else None,recorded_model_calls=g['usage']['recorded_calls'],terminal_events_match=g['local_events']==g['upstream_events'] and g['done_received']))
  raw=W/(g['generation_id']+'-production.json')
  if raw.exists():
   r=json.loads(raw.read_text());q=(r.get('blueprint') or {}).get('questions',[]);expected={'kentucky':4,'princeton':9,'shanghai':45}[sample];passed=len(q)==expected
   if sample=='kentucky':passed=passed and [len(x.get('children') or []) for x in q]==[4,4,5,4]
   if sample=='princeton' and passed:
    for number,n in {'2':2,'3':2,'4':5,'5':3,'6':4,'7':4,'8':8,'9':5,'10':5}.items():
     x=next((x for x in q if str(x.get('original_number','')).strip('.() ')==number),{});passed=passed and max(len(x.get('children') or []),x.get('blank_count') or 0)>=n
   fidelity.append(dict(label=label,generation_id=g['generation_id'],expected_top=expected,actual_top=len(q),child_counts=[len(x.get('children') or []) for x in q],passed=passed,boundary='Top-level count and selected source subitem counts; not complete semantic equivalence.'))
result=dict(unique_pdfs=3,fresh_upload_cases=len(cases),generation_attempts=len(rows),upstream_states=dict(collections.Counter(r['turn_status'] for r in rows)),full_pipeline_summaries=sum(r['accepted'] is not None for r in rows),pipeline_successes=sum(r['pipeline_success'] is True for r in rows),ui_acceptance_passes=sum(c['ui_acceptance_passed'] for c in cases),recorded_model_calls=sum(r['recorded_model_calls'] for r in rows),cases=cases,attempts=rows,source_fidelity=fidelity)
(O/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ['cases','attempts','source_fidelity']})
