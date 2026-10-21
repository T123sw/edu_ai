import json,re
from pathlib import Path
root=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-19-transformer-generation-watch');s=json.loads((root/'latest.json').read_text());videos=[];light=[]
for r in s['artifacts']:
 if r['type']!='classroom':
  b=json.loads((root/r['id']/'content.json').read_text())['content'] if (root/r['id']/'content.json').exists() else None
  light.append({'node':r['node'],'kind':r['type'],'seconds':r.get('execution_seconds'),'status':r['status'],'characters':len(b) if isinstance(b,str) else None,'questions':len(b.get('questions',[])) if isinstance(b,dict) else None});continue
 ev=json.loads((root/r['id']/'host-events.json').read_text());w=r.get('scene_workers',[]);renders=[e for e in ev if e['tool']=='render_project' and e.get('command_id')]
 v={'node':r['node'],'title':r['title'],'artifact_id':r['id'],'status':r['status'],'started_at':r['started_at'],'finished_at':r.get('finished_at'),'production_seconds':r.get('execution_seconds'),'brief_conversion_seconds':r.get('brief_seconds'),'flow':'teaching-brief-v2' if r.get('brief_seconds') else 'legacy','tools':len(ev),'worker_groups':len(w),'tool_errors':r.get('tool_failures',[])}
 if w:
  dispatched=min(x['submitted_at'] for x in w);v['preparation_including_brief_seconds']=dispatched-r['started_at']
  if all(x.get('finished_at') for x in w):v['scene_execution_seconds']=max(x['finished_at'] for x in w)-dispatched
 if renders:
  render=renders[-1];log=(Path(r['workspace'])/'.host'/(render['command_id']+'.log')).read_text(errors='replace')
  count=re.findall(r'"workerCount":(\d+)',log);v['render_workers']=int(count[-1]) if count else None
  if w and all(x.get('finished_at') for x in w):v['assembly_check_seconds']=render['at']-max(x['finished_at'] for x in w)
  done=next((e['at'] for e in ev if e['tool']=='poll_command' and e.get('command_id')==render['command_id'] and e.get('exit_code')==0),None)
  if done:v['render_with_poll_seconds']=done-render['at'];v['post_render_seconds']=r['finished_at']-done if r.get('finished_at') else None
 if r['status']=='draft':
  b=json.loads((root/r['id']/'content.json').read_text())['content'];v.update(duration=b['timeline']['duration'],segments=len(b['timeline']['segments']),narration_characters=sum(len(x['narration']) for x in b['timeline']['segments']),narrated_segments=sum(bool(x['narration']) for x in b['timeline']['segments']),verification=b['verification'],project=b['project'])
 for k,val in list(v.items()):
  if isinstance(val,float):v[k]=round(val,3)
 videos.append(v)
result={'preparation_id':s['preparation_id'],'as_of':s['at'],'status':s['status'],'elapsed_seconds':s['elapsed_seconds'],'delivery':s['delivery'],'videos':videos,'reports_and_quizzes':light,'observations':{'nonintrusive':True,'database_read_only':True,'production_services_changed':False,'mixed_versions':{'main_backend_pid':2671910,'main_started':'2026-10-19T11:51:54Z','supplemental_worker_pid':2588978,'supplemental_started':'2026-10-19T08:34:28Z'},'numeric_spotcheck':'numeric-spotcheck.json','tts_429':'n4 first prepare_scene_assets audio subprocess returned HTTP 429; automatic retry produced complete audio','quality_scope':'Existing native snapshots and selected report/quiz calculations; not exhaustive frame-by-frame or spoken-word review'}}
if (root/'terminal.json').exists():
 terminal=json.loads((root/'terminal.json').read_text());result['observed_elapsed_seconds']=result['elapsed_seconds'];result['elapsed_seconds']=terminal['total_seconds'];result['started_at']=terminal['started_at'];result['finished_at']=terminal['finished_at'];result['delivery']={**terminal['final_delivery'],'available_resources':terminal['resource_count'],'planned_resources':terminal['resource_count']};result['status']=terminal['status']
(root/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({'status':s['status'],'minutes':round(s['elapsed_seconds']/60,1),'videos':[{k:v.get(k) for k in ['node','status','production_seconds','duration','scene_execution_seconds','render_with_poll_seconds']} for v in videos]},ensure_ascii=False))
