import os
from pathlib import Path
import dotenv
# Production Config normally reloads .env with override=True. Disable loading
# before importing the app so legacy test fixtures cannot reach business state.
dotenv.load_dotenv = lambda *args, **kwargs: False
os.environ['STORAGE_ROOT'] = '/tmp/edu-personal-studio/strict-isolated-storage'
for kind in ['JOB', 'TASK', 'COURSE', 'COURSE_MEMBERSHIP', 'MATERIAL', 'KNOWLEDGE', 'APP_STATE', 'USER', 'ASSESSMENT', 'CONVERSATION']:
    os.environ[kind + '_PERSISTENCE_MODE'] = 'json'
import pytest
raise SystemExit(pytest.main(['-q', 'backend/src/tests/personal_studio/test_studio.py', 'backend/src/tests/test_generation_task_handlers.py', 'backend/src/tests/test_job_completion_service.py', 'backend/src/tests/test_job_reconciliation_service.py']))
