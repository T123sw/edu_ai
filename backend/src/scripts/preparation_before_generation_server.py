"""Opt-in real app acceptance server with a hard stop before resource submission.

Only runs against an explicitly named, isolated PostgreSQL database and storage.
Provider calls, authentication, HTTP routes, queue and research handlers are real.
The sole workflow override cancels each validation task after producing specs.
"""
import json
import os
from pathlib import Path
import threading
import time
from uuid import uuid4


def create_app():
    import dotenv
    from sqlalchemy.engine import make_url
    settings_file = os.environ['PREPARATION_BEFORE_GENERATION_SETTINGS']
    settings = json.loads(Path(settings_file).read_text())
    root = Path(settings['PREPARATION_VALIDATION_ROOT']).resolve()
    url = make_url(settings['DATABASE_URL'])
    if (url.get_backend_name() != 'postgresql' or url.host != '127.0.0.1'
            or not url.database.startswith('edu_ai_preparation_test_')
            or not root.name.startswith('preparation-validation-')):
        raise RuntimeError('ISOLATED_VALIDATION_ENVIRONMENT_REQUIRED')
    for key in ('STORAGE_ROOT', 'COURSE_STORAGE_ROOT', 'RUNTIME_CONFIG_ROOT', 'TASKS_DB_PATH', 'OPENMAIC_DATA_ROOT'):
        if not Path(settings[key]).resolve().is_relative_to(root):
            raise RuntimeError('VALIDATION_PATH_OUTSIDE_ROOT:' + key)
    os.environ.update(settings)
    os.chdir(root)
    dotenv.load_dotenv = lambda *args, **kwargs: False
    from scripts.preparation_validation_common import redact
    evidence = root / 'evidence'
    evidence.mkdir(exist_ok=True)
    lock = threading.RLock()

    def save(path, value):
        path = evidence / path
        with lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(redact(value), ensure_ascii=False, indent=2, default=str))

    from app.course_preparation.lifecycle_repository import LifecycleRepository
    checkpoint = LifecycleRepository.checkpoint
    def recorded_checkpoint(self, context, value, **kwargs):
        result = checkpoint(self, context, value, **kwargs)
        stamp = f'{time.time_ns()}-{context.stage}'
        save(f'{context.preparation_id}/checkpoints/{stamp}.json', value)
        return result
    LifecycleRepository.checkpoint = recorded_checkpoint

    from app.course_preparation.harness_adapter import HarnessPreparationAdapter
    original_init = HarnessPreparationAdapter.__init__
    def recorded_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        client_factory = self.client_factory
        adapter = self
        class RecordedClient:
            def __init__(self, **options):
                self.client = client_factory(**options)
            def __enter__(self):
                self.client.__enter__()
                return self
            def __exit__(self, *exc):
                return self.client.__exit__(*exc)
            def stream(self, method, url, **request):
                task = adapter.meter.context.preparation_id
                save(f'{task}/requests/{time.time_ns()}-{uuid4().hex[:8]}.json', {
                    'time': time.time(), 'metadata': adapter.last_packet_metadata,
                    'payload': request.get('json'),
                })
                return self.client.stream(method, url, **request)
        self.client_factory = RecordedClient
    HarnessPreparationAdapter.__init__ = recorded_init

    from app.course_preparation import pipeline
    from app.course_preparation.runner import StepResult
    original_pipeline = pipeline.build_pipeline
    def no_generation(*args, **kwargs):
        raise AssertionError('VALIDATION_RESOURCE_GENERATION_FORBIDDEN')
    from app.course_preparation.adapters.generation import GenerationAdapter
    GenerationAdapter.submit = no_generation
    GenerationAdapter.reconcile = no_generation

    def validation_pipeline(task_store):
        built = original_pipeline(task_store)
        production = built.runner.handlers['produce'].__self__
        def stop_before_generation(context):
            prepared = production.prepare_specifications(context)
            built.repository.checkpoint(context, prepared)
            from sqlalchemy import text
            with built.repository.engine.connect() as conn:
                counts = {
                    'artifacts': conn.scalar(text('select count(*) from preparation_artifacts where preparation_id=:p'), {'p': context.preparation_id}),
                    'generation_actions': conn.scalar(text("select count(*) from preparation_actions where preparation_id=:p and kind='generate_resource'"), {'p': context.preparation_id}),
                    'resource_jobs': conn.scalar(text("select count(*) from durable_tasks where workflow_type='preparation_resource'")),
                }
            if any(counts.values()):
                raise AssertionError('GENERATION_BOUNDARY_VIOLATED')
            save(f'{context.preparation_id}/handoff.json', {
                'scope': 'pre-generation acceptance; no course or resource delivery',
                'stopped_at': 'resource_specs_ready_before_submit', 'time': time.time(),
                'counts': counts, 'checkpoint': prepared,
            })
            # Use the actual cancellation protocol so the queue cannot resume it.
            built.repository.cancel(context.owner_user_id, context.preparation_id)
            return StepResult(prepared)
        built.runner.handlers['produce'] = stop_before_generation
        for stage in ('review', 'repair', 'commit'):
            built.runner.handlers[stage] = no_generation
        for stage, handler in list(built.runner.handlers.items()):
            def measured(context, _handler=handler, _stage=stage):
                began = time.time()
                result = None
                error = None
                try:
                    result = _handler(context)
                    return result
                except Exception as exc:
                    error = {'code': getattr(exc, 'code', type(exc).__name__), 'message': str(exc)}
                    raise
                finally:
                    save(f'{context.preparation_id}/stages/{time.time_ns()}-{_stage}.json', {
                        'stage': _stage, 'started_at': began, 'seconds': time.time()-began,
                        'next_stage': getattr(result, 'next_stage', None), 'error': error,
                    })
            built.runner.handlers[stage] = measured
        return built
    pipeline.build_pipeline = validation_pipeline

    from app.bootstrap import create_app as actual_app
    from starlette.staticfiles import StaticFiles
    app = actual_app()
    @app.middleware('http')
    async def frontend_proxy(request, call_next):
        if request.scope['path'].startswith('/backend/'):
            request.scope['path'] = request.scope['path'][len('/backend'):]
            request.scope['raw_path'] = request.scope['path'].encode()
        return await call_next(request)
    app.mount('/', StaticFiles(directory=Path(__file__).resolve().parents[3] / 'frontend/dist', html=True))
    return app
