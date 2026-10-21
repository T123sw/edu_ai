"""Run PBL checks without letting core.config reload production persistence.

Usage (repo root): python scripts/pbl/isolated.py pytest ...
PBL_TEST_DATABASE_URL must explicitly name a test database for PostgreSQL tests.
Only model provider values may be inherited for --server real-model acceptance.
"""
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend/src'))
import dotenv

def configure(*, live_model=False):
    if live_model:
        for key, value in dotenv.dotenv_values(ROOT / '.env').items():
            if value is not None and any(part in key for part in ('LLM_', 'DEEPSEEK_', 'QWEN_', 'OPENROUTER_', 'ANSWER_', 'VISION_MODEL', 'LOGIC_MODEL')):
                os.environ.setdefault(key, value)
    dotenv.load_dotenv = lambda *args, **kwargs: False
    storage = Path(os.environ.get('PBL_ACCEPTANCE_STORAGE') or tempfile.mkdtemp(prefix='edu-pbl-'))
    storage.mkdir(parents=True, exist_ok=True)
    os.environ.update(STORAGE_ROOT=str(storage), COURSE_STORAGE_ROOT=str(storage/'courses'),
        RUNTIME_CONFIG_ROOT=str(storage/'runtime_config'), TASKS_DB_PATH=str(storage/'tasks.db'),
        JWT_SECRET_KEY='isolated-pbl-acceptance-secret-not-production', PERSISTENCE_PROFILE='compatibility')
    for kind in ('JOB','TASK','COURSE','COURSE_MEMBERSHIP','MATERIAL','KNOWLEDGE','APP_STATE','USER','ASSESSMENT','CONVERSATION','LEARNING'):
        os.environ[kind+'_PERSISTENCE_MODE']='json'
    os.environ['DATABASE_URL']=os.environ.get('PBL_TEST_DATABASE_URL',f'sqlite:///{storage}/pbl.db')
    return storage

if __name__=='__main__':
    configure()
    if sys.argv[1:2]==['pytest']:
        import pytest
        raise SystemExit(pytest.main(sys.argv[2:]))
    raise SystemExit('Usage: python scripts/pbl/isolated.py pytest <test paths>')
