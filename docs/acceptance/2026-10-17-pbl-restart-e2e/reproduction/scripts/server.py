import os,sys,json,time,hashlib
from pathlib import Path
root=Path('/tmp/pbl-restart-20261017')
sys.path.insert(0,'/home/zxqs_ep/Edu_AI/scripts/pbl')
from isolated import configure
os.environ['PBL_TEST_DATABASE_URL']='postgresql+psycopg://zxqs_ep@127.0.0.1:55441/pbl_acceptance_20261017_restart'
os.environ['PBL_ACCEPTANCE_STORAGE']=str(root/'storage')
configure(live_model=True)
for kind in ('JOB','TASK','COURSE','COURSE_MEMBERSHIP','MATERIAL','KNOWLEDGE','APP_STATE','USER','ASSESSMENT','CONVERSATION','LEARNING'):
    os.environ[kind+'_PERSISTENCE_MODE']='postgres'
os.environ.update(PERSISTENCE_PROFILE='database',DURABLE_JOB_WORKERS='2')
from sqlalchemy import create_engine
from app.database import Base
engine=create_engine(os.environ['DATABASE_URL']);Base.metadata.create_all(engine)
from app.bootstrap import create_app
from core.user_storage import user_storage
for name in ('shop_a','shop_b','form','layout','score','recovery','outsider'):
    name='matrix_'+name
    if not user_storage.get_user(name):user_storage.create_user(username=name,password='matrix-isolated-only',role='student')
from app.pbl import project_service
original=project_service.generate_project_phase
async def traced(owner,snapshot,phase,data):
    out=root/owner;out.mkdir(exist_ok=True)
    n=len(list(out.glob('input-*.json')))+1
    record={'phase':phase,'data':data,'startedAt':time.time()}
    (out/f'input-{n:03}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
    try:
        result=await original(owner,snapshot,phase,data)
        (out/f'output-{n:03}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        return result
    except Exception as exc:
        (out/f'error-{n:03}.json').write_text(json.dumps({'type':type(exc).__name__,'message':str(exc)},ensure_ascii=False))
        raise
project_service.generate_project_phase=traced
import uvicorn
uvicorn.run(create_app(),host='127.0.0.1',port=8027,log_level='warning')
