"""Opt-in factory for the actual app and durable workers, with test-only attestation.

Run uvicorn scripts.preparation_validation_server:create_app --factory.
Set PREPARATION_VALIDATION_ENV_FILE to a private, explicit test configuration.
This factory never creates/migrates a database or provisions production users.
"""
import os
from pathlib import Path
from scripts.preparation_validation_common import database_identity, git_identity, digest


def create_app():
    import dotenv
    filename = os.environ.get('PREPARATION_VALIDATION_ENV_FILE')
    if not filename:
        raise RuntimeError('EXPLICIT_VALIDATION_ENV_REQUIRED')
    settings = {k: v for k, v in dotenv.dotenv_values(filename).items() if v is not None}
    url = settings.get('PREPARATION_TEST_DATABASE_URL', '')
    identity = database_identity(url)
    if settings.get('DATABASE_URL') != url or settings.get('LEARNING_TEST_DATABASE_URL') != url:
        raise RuntimeError('VALIDATION_DATABASE_MISMATCH')
    raw_root = settings.get('PREPARATION_VALIDATION_ROOT', '')
    if not raw_root or not Path(raw_root).is_absolute():
        raise RuntimeError('DEDICATED_VALIDATION_ROOT_REQUIRED')
    root = Path(raw_root).resolve()
    if not root.is_absolute() or not root.name.startswith('preparation-validation-') or root == Path.cwd():
        raise RuntimeError('DEDICATED_VALIDATION_ROOT_REQUIRED')
    required_paths = ('STORAGE_ROOT', 'COURSE_STORAGE_ROOT', 'RUNTIME_CONFIG_ROOT', 'TASKS_DB_PATH')
    for key in required_paths:
        raw = settings.get(key)
        if not raw or not Path(raw).is_absolute() or not Path(raw).resolve().is_relative_to(root):
            raise RuntimeError('VALIDATION_STORAGE_OUTSIDE_ROOT:' + key)
    # Prevent ambient storage overrides and implicit core.config dotenv loading.
    for key in ('VECTOR_DB_PATH', 'DOCUMENT_INDEX_PATH', 'DOCUMENTS_ROOT', 'VIDEOS_ROOT', 'VIDEO_CHUNKS_ROOT',
                'COURSE_MEMBERSHIPS_FILE', 'LEARNING_DB_PATH', 'TEMP_DIR', 'SEARCHED_IMAGE_STORAGE_ROOT',
                'CONVERSATIONS_FILE', 'USER_PROFILES_FILE', 'LESSON_PLANS_FILE'):
        if key in settings and not Path(settings[key]).resolve().is_relative_to(root):
            raise RuntimeError('VALIDATION_STORAGE_OUTSIDE_ROOT:' + key)
        os.environ.pop(key, None)
    # Legacy user storage has a cwd-relative default; isolate that path as well.
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    os.environ.update(settings)
    if settings.get('USER_PERSISTENCE_MODE') != 'postgres':
        raise RuntimeError('POSTGRES_TEST_IDENTITY_REQUIRED')
    dotenv.load_dotenv = lambda *a, **kw: False
    os.environ['COURSE_PREPARATION_ENABLED'] = 'true'
    os.environ['COURSE_RESEARCH_ENABLED'] = 'false'
    code = git_identity()
    if code['dirty']:
        raise RuntimeError('COMMITTED_VALIDATION_TREE_REQUIRED')
    from sqlalchemy import create_engine, text
    db = create_engine(url)
    try:
        with db.connect() as conn:
            if conn.scalar(text('select current_database()')) != identity['database']:
                raise RuntimeError('VALIDATION_DATABASE_MISMATCH')
    finally:
        db.dispose()
    from fastapi import Depends, Request
    from app.auth import get_current_user
    from app.bootstrap import create_app as actual_app
    app = actual_app()

    @app.get('/api/preparation-validation/identity')
    def attestation(request: Request, user=Depends(get_current_user)):
        runtime = request.app.state.durable_job_runtime
        return {**identity, **code, 'worker_started': runtime._started,
                'preparation_enabled': hasattr(request.app.state, 'preparation_service'),
                'test_identity': user['username'], 'config_version': digest(settings),
                'storage_root_digest': digest(str(root))}
    return app
