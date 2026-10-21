"""Full application on an explicitly dedicated acceptance database, with real models."""
import os
from isolated import configure
url=os.environ.get('PBL_TEST_DATABASE_URL','')
if not url or 'pbl_acceptance' not in url:
    raise SystemExit('PBL_TEST_DATABASE_URL must name the dedicated pbl_acceptance database')
storage=configure(live_model=True)
for kind in ('JOB','TASK','COURSE','COURSE_MEMBERSHIP','MATERIAL','KNOWLEDGE','APP_STATE','USER','ASSESSMENT','CONVERSATION','LEARNING'):
    os.environ[kind+'_PERSISTENCE_MODE']='postgres'
os.environ.update(PERSISTENCE_PROFILE='database',DURABLE_JOB_WORKERS='2')
from sqlalchemy import create_engine
from app.database import Base
engine=create_engine(url)
Base.metadata.create_all(engine)
engine.dispose()
from core.user_storage import user_storage
if not user_storage.get_user('pbl_learner'):
    user_storage.create_user(username='pbl_learner',password='pbl-isolated-acceptance-only',role='student')
from app.bootstrap import create_app
import uvicorn
uvicorn.run(create_app(),host='127.0.0.1',port=int(os.environ.get('PBL_API_PORT','8017')),log_level='warning')
