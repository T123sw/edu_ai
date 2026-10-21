import json
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
from core.config import Config
from app.integrations.hyperframes.workflow import generate_native, creation_brief
from app.integrations.hyperframes.projects import ProjectStore
from app.self_learning.service import gateway

root=Path('/home/zxqs_ep/data/main-review/hyperframes-speed-20261019')
while True:
    p=root/'render-comparison.json'
    rows=json.loads(p.read_text()) if p.exists() else []
    if len(rows)==2:break
    time.sleep(5)
os.environ['HYPERFRAMES_RENDER_WORKERS']='2'
brief=json.loads(Path('/home/zxqs_ep/data/edu_ai/course_data/hyperframes/workflows/026f506184b04a256c6c9f60b27051c32effce941681fc0b7d6778e020d6b261/REQUEST.json').read_text())
teaching={k:brief[k] for k in ('language','requirements','exclusions','prior_knowledge','desired_outcomes','source_policy','depth','requirement_ids') if k in brief}
teaching.update(request_goal=brief['request'],resource_target_minutes=brief['requested_video_minutes'],objectives=brief.get('topic_objectives'))
payload=SimpleNamespace(title=brief['title'], audience=brief['audience'],research_context=brief['sources'],pdf_content=brief.get('uploaded_text'),
    original_content=brief.get('original_content'),revision_feedback=brief.get('requested_changes'),classroom_options=brief.get('media_requirements',{}),teaching_context=teaching)
assert {**creation_brief(payload),'assets':[]}==brief
statefile=root/'full-checkpoint.json'
class Checkpoint:
    def load_generation_state(self):return json.loads(statefile.read_text()) if statefile.exists() else None
    def save_generation_state(self,value):
        tmp=statefile.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False));tmp.replace(statefile)
store=ProjectStore(root/'full/projects')
started=time.time()
(root/'full-status.json').write_text(json.dumps({'status':'running','started_at':started,'scope':'fresh native generation from identical saved node brief; cloud TTS is a separate prior change; isolated outputs, not production replacement'}))
try:
    content=generate_native(payload,gateway=gateway('teacher'),artifact={'resource_id':'speed_validation_20261019','spec_digest':'speed_validation'},store=store,checkpoint=Checkpoint())
    elapsed=time.time()-started
    video=store.file(content['project'],'exports/lesson.mp4')
    subprocess.run(['/usr/bin/ffmpeg','-v','error','-i',str(video),'-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    result={'status':'succeeded','elapsed_seconds':round(elapsed,2),'duration_seconds':content['timeline']['duration'],'scenes':len(content['timeline']['segments']),
        'video':str(video),'project':content['project'],'decoded':True,'scope':'same brief, fresh model generation; cloud TTS and isolated load differ from historical run, not a controlled total-speed comparison'}
    (root/'full-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (root/'full-status.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False),flush=True)
except BaseException as exc:
    (root/'full-status.json').write_text(json.dumps({'status':'failed','error':str(exc),'elapsed_seconds':time.time()-started},ensure_ascii=False));raise
