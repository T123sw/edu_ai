import os
import sys
import tempfile
from pathlib import Path
import dotenv
# Config normally loads the production .env with override=True. Tests must not.
dotenv.load_dotenv = lambda *args, **kwargs: False
root = Path(tempfile.mkdtemp(prefix='edu-narration-tests-'))
for name in ('JOB','TASK','COURSE','COURSE_MEMBERSHIP','MATERIAL','KNOWLEDGE','APP_STATE'):
    os.environ[name+'_PERSISTENCE_MODE']='json'
for name in ('STORAGE_ROOT','COURSE_STORAGE_ROOT','RUNTIME_CONFIG_ROOT'):
    os.environ[name]=str(root/name.lower())
os.environ['DATABASE_URL']='sqlite:///'+str(root/'test.db')
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
