import os, sys, tempfile
import dotenv
# Local .env forces database modes with override=True. Block dotenv only in
# this isolated test process, before application imports.
dotenv.load_dotenv = lambda *args, **kwargs: False
for key in ('USER', 'COURSE', 'COURSE_MEMBERSHIP', 'CONVERSATION', 'JOB', 'MATERIAL', 'KNOWLEDGE', 'APP_STATE', 'LEARNING', 'TASK'):
    os.environ[key + '_PERSISTENCE_MODE'] = 'json'
os.environ['PERSISTENCE_PROFILE'] = 'compatibility'
root = tempfile.mkdtemp(prefix='edu-b-test-')
os.environ['STORAGE_ROOT'] = root
os.environ['COURSE_STORAGE_ROOT'] = root + '/courses'
os.environ['AGENT_RUNS_DB_PATH'] = root + '/agent-runs.db'
os.environ['AGENT_MEMORY_DB_PATH'] = root + '/agent-memory.db'
os.environ['USE_REACT_AGENT'] = 'false'
sys.path.insert(0, os.getcwd())
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
