"""Recycle the API only between its jobs; freeze claims briefly for the check."""
import os,signal,time,json,subprocess
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy import create_engine,text
root=Path('docs/acceptance/2026-10-19-stable-voice')
pid=2503545
engine=create_engine(dotenv_values('.env')['DATABASE_URL'])
end=time.monotonic()+240;checks=0
while time.monotonic()<end:
 actual=int(subprocess.check_output(['systemctl','show','edu-ai-backend.service','-p','MainPID','--value']))
 if actual!=pid:raise RuntimeError(f'API PID changed externally to {actual}; recheck required')
 assert Path(f'/proc/{pid}').stat().st_uid==os.getuid()
 assert b'uvicorn\x00app.main:app' in Path(f'/proc/{pid}/cmdline').read_bytes()
 try:
  with engine.begin() as c:
   c.execute(text("SET LOCAL lock_timeout='500ms'"))
   c.execute(text('LOCK TABLE durable_tasks IN SHARE ROW EXCLUSIVE MODE'))
   rows=[dict(r) for r in c.execute(text("select task_id,lease_owner,status,started_at,attempt_count from durable_tasks where status='leased'")).mappings()]
   if not rows:
    (root/'api-reload.json').write_text(json.dumps({'old_pid':pid,'at':time.time(),'other_tasks_preserved':rows,'checks':checks},indent=2))
    os.kill(pid,signal.SIGKILL)
    print('IDLE_API_RELOADED',flush=True);break
 except Exception as exc:
  if 'lock timeout' not in str(exc):raise
 checks+=1
 if checks%20==0:print('Waiting for API-owned task to finish; no cancellation.',flush=True)
 time.sleep(.5)
else:raise TimeoutError('API still busy; no job was interrupted')
