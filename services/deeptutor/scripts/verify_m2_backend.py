"""Run the migration backend regression with all persistence isolated.

The project's config loader overrides shell variables from .env. Load it first,
then replace persistence settings and prevent subsequent dotenv reloads.
"""
import os
from pathlib import Path
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'backend/src'))
    from core.config import Config
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False
    with tempfile.TemporaryDirectory(prefix='deeptutor-backend-regression-') as temporary:
        isolated = Path(temporary)
        for key in list(os.environ):
            if key.endswith('_PERSISTENCE_MODE'):
                os.environ[key] = 'json'
        os.environ.update(JOB_PERSISTENCE_MODE='json', APP_STATE_PERSISTENCE_MODE='json',
            MATERIAL_PERSISTENCE_MODE='json', DATABASE_URL='sqlite:///' + str(isolated / 'unused-default.db'),
            COURSE_STORAGE_ROOT=str(isolated / 'courses'), PYTHON_DOTENV_DISABLED='1')
        Config.STORAGE_ROOT = isolated / 'app'
        Config.RUNTIME_CONFIG_ROOT = isolated / 'runtime-config'
        # RAG's Config subclass also reads paths from os.environ at import time.
        for key, value in {
            'STORAGE_ROOT': isolated / 'app', 'RUNTIME_CONFIG_ROOT': isolated / 'runtime-config',
            'VECTOR_DB_PATH': isolated / 'vectors', 'DOCUMENT_INDEX_PATH': isolated / 'documents.json',
            'DOCUMENTS_ROOT': isolated / 'documents', 'VIDEOS_ROOT': isolated / 'videos',
            'VIDEO_CHUNKS_ROOT': isolated / 'video-chunks', 'TEMP_DIR': isolated / 'temp',
        }.items():
            os.environ[key] = str(value)
            setattr(Config, key, value)
        import pytest
        tests = sys.argv[1:] or ['tests/exam_generation', 'tests/integrations/test_deeptutor_client.py',
                 'tests/test_durable_task_executor.py', 'tests/test_durable_task_store.py',
                 'tests/test_job_completion_service.py', 'tests/test_job_reconciliation_service.py']
        return pytest.main([str(root / 'backend/src' / path) for path in tests] + ['-q', '--disable-warnings'])


if __name__ == '__main__':
    raise SystemExit(main())
