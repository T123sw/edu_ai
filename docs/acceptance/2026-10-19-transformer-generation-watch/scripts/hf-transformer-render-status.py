from pathlib import Path
import json,re,shutil
root=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-19-transformer-generation-watch');s=json.loads((root/'latest.json').read_text());res=[]
(root/'previews').mkdir(exist_ok=True)
for r in s['artifacts']:
 if r['type']!='classroom':continue
 ws=Path(r['workspace']);ev=json.loads((root/r['id']/'host-events.json').read_text())
 for p in ws.glob('videos/*/.hyperframes/artifacts/snapshots/*/contact-sheet*.jpg'):
  dest=root/'previews'/f'{r["node"]}-{p.name}'
  if not dest.exists():shutil.copy2(p,dest)
 renders=[e for e in ev if e['tool']=='render_project' and e.get('command_id')]
 row={'node':r['node'],'status':r['status'],'render_started':False}
 if renders:
  e=renders[-1];file=ws/'.host'/(e['command_id']+'.log');log=file.read_text(errors='replace') if file.exists() else ''
  progress=re.findall(r'@hf-progress (\{[^\n]+\})',log)
  counts=re.findall(r'"workerCount":(\d+)',log)
  row.update(render_started=True,start=e['at'],workers=int(counts[-1]) if counts else None,progress=json.loads(progress[-1]) if progress else None,tail=log[-300:] if 'Render complete' in log else None)
 res.append(row)
(root/'render-progress.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(res,ensure_ascii=False))
