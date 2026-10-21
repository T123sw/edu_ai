from pathlib import Path
# Load only the isolated server's persistence setup, never start another worker.
exec(Path('/tmp/pbl-fixes-final-20261017/server.py').read_text().split('from app.pbl import project_service')[0])
import uuid,json,time
from app.pbl.repository import PblRepository
from app.pbl.project_workflow import load_project_skill
from app.services.job_store import create_job,update_job,JobKind,JobStatus
from app.chat.tasks.task_store import get_task_store
old=Path('/tmp/pbl-matrix-20261017/matrix_shop_b')
checkpoint=json.loads((old/'private.json').read_text())['checkpoint']
topic=json.loads((old/'input-001.json').read_text())['data']['topic']
owner='matrix_retry'
if not user_storage.get_user(owner):user_storage.create_user(username=owner,password='matrix-isolated-only',role='student')
repo=PblRepository();row=repo.create_or_get(owner,str(uuid.uuid4()),topic)
job=create_job(kind=JobKind.GENERATE_PBL,edu_job_id=row.current_job_id,owner_user_id=owner,scope_type='pbl',scope_id=row.id,input_summary={'topic':topic,'title':topic,'exercise_id':row.id})
checkpoint['skillVersions']={phase:load_project_skill(phase)['version'] for phase in ('plan','review_plan','build_step','repair_step','build_checks','repair_checks','validate','publish')}
checkpoint['generationJobId']=job.edu_job_id
checkpoint['repairTotals']=dict(checkpoint['repairs'])
repo.save_checkpoint(owner,row.id,job.edu_job_id,checkpoint)
store=get_task_store();store.enqueue(task_id=job.edu_job_id,workflow_type='pbl_generate',handler_version=1,owner_user_id=owner,course_id=None,scope_type='pbl',scope_id=row.id,command={'exercise_id':row.id,'topic':topic},config_snapshot_id=None,idempotency_key=job.edu_job_id,max_attempts=3,available_at=time.time()+3600)
store.mark_failed(job.edu_job_id,error='Injected exhausted budget from original failed checkpoint',error_code='PBL_VALIDATION_FAILED')
update_job(job.edu_job_id,status=JobStatus.FAILED,error_code='PBL_VALIDATION_FAILED',error_message='隔离回归：修复预算已耗尽',step='failed')
out=Path('/tmp/pbl-fixes-final-20261017/matrix_retry');out.mkdir(exist_ok=True)
(out/'seed.json').write_text(json.dumps({'exerciseId':row.id,'jobId':job.edu_job_id,'completedSteps':len(checkpoint['completed']),'repairs':checkpoint['repairs'],'injectedFailure':True}))
print('SEEDED',row.id,flush=True)
