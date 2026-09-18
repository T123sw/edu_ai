"""Full application with real workers, limited to the isolated acceptance database."""
import os
from pathlib import Path
from core.config import Config

if 'edu_ai_agent_merge' not in os.getenv('DATABASE_URL',''):
    raise RuntimeError('This launcher only supports the isolated merged-agent database (migrated through 20260918_0036)')
root=Path(__file__).resolve().parents[3]/'artifacts'/'full-application'
root.mkdir(parents=True,exist_ok=True)
os.environ.update({name:'true' for name in ('COURSE_PREPARATION_ENABLED','LEARNING_SESSION_V1_ENABLED',
    'LEARNING_PROGRESS_V1_ENABLED','LEARNING_AGENT_V1_ENABLED','LEARNING_ENRICHMENT_V1_ENABLED','LEARNING_PREPARATION_V1_ENABLED')})
os.environ['TASKS_DB_PATH']=str(root/'tasks.db')
for domain in ('USER','COURSE','COURSE_MEMBERSHIP','MATERIAL','KNOWLEDGE','APP_STATE','JOB','CONVERSATION'):
    os.environ[domain+'_PERSISTENCE_MODE']='postgres'

if __name__=='__main__':
    import uvicorn
    from app.bootstrap import app
    uvicorn.run(app,host='127.0.0.1',port=8027,log_level='info')
