"""Request-local adapters around the original engine and source parser contracts."""
from contextvars import ContextVar
from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path

_builtin_tools = ContextVar('edu_exam_builtin_tools', default=None)
_question_checkpoint = ContextVar('edu_exam_checkpoint', default=None)


class ExamTurnEngine:
    def __init__(self, original):
        self.original = original

    async def execute(self, context):
        allowed = _builtin_tools.get()
        if allowed is not None:
            context.allowed_builtin_tools = list(allowed)
        checkpoint = _question_checkpoint.get()
        if checkpoint is not None:
            context.extension("question_pipeline")["checkpoint"] = checkpoint
        async for event in self.original.execute(context):
            yield event


@contextmanager
def model_scope(model, allowed_tools, checkpoint=None, text_model=None):
    from deeptutor.services.llm.config import LLMConfig, set_scoped_llm_config, reset_scoped_llm_config
    tools_token = _builtin_tools.set(allowed_tools)
    checkpoint_token = _question_checkpoint.set(checkpoint)
    token = None
    try:
        if model:
            config = LLMConfig(model=model['model'], api_key=model['api_key'],
                base_url=model['base_url'], binding=model.get('binding', 'openai'), provider_name=model.get('binding', 'openai'),
                api_format=model['api_format'], reasoning_effort=model.get('reasoning_effort'))
            config.edu_text_model = dict(text_model) if text_model else None
            config.edu_supports_vision = model.get("supports_vision", False)
            token = set_scoped_llm_config(config)
        yield
    finally:
        if token is not None:
            reset_scoped_llm_config(token)
        _builtin_tools.reset(tools_token)
        _question_checkpoint.reset(checkpoint_token)


def prepare_sources(owner, request_id, sources, payload, *, revision=None):
    """Materialize already-authorized parser output; accept no caller paths."""
    root = Path(os.environ['DEEPTUTOR_HOME']) / 'edu_sources' / hashlib.sha256(owner.encode()).hexdigest() / request_id
    # Content addressing keeps concurrent retries immutable; local directories
    # are server-owned and never returned through public progress.
    for source in sources:
        digest = hashlib.sha256(json.dumps({"source": source, "blueprint_version": revision if revision is not None else _migration_revision()}, sort_keys=True).encode()).hexdigest()
        directory = root / digest
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        files = {'source_metadata.json': json.dumps({key: source[key] for key in ('document_id', 'filename', 'source_hash', 'parser')}, ensure_ascii=False).encode(),
                 'source.md': source['content'].encode(),
                 'source_content_list.json': json.dumps(source['content_list'], ensure_ascii=False).encode()}
        for name, encoded in source['images'].items():
            files['images/' + name] = base64.b64decode(encoded, validate=True)
        for name, data in files.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if path.exists() and path.read_bytes() == data:
                continue
            # Atomic replace avoids partial reads when two identical submissions overlap.
            import tempfile
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                handle.write(data)
                temporary = Path(handle.name)
            temporary.replace(path)
        if source['role'] == 'template':
            payload['config']['paper_path'] = str(directory)
        else:
            payload['content'] += '\n\n[Supplied context: ' + source['document_id'] + ']\n' + source['content']
            import mimetypes
            for name, encoded in source['images'].items():
                payload.setdefault('attachments', []).append({'type': 'image', 'filename': name,
                    'base64': encoded, 'mime_type': mimetypes.guess_type(name)[0] or 'image/png'})
    return payload


def reserve_request(owner, request_id, fingerprint):
    """Bind an ID to all internal inputs, including the model, without secrets."""
    import sqlite3
    root = Path(os.environ['DEEPTUTOR_HOME'])
    with sqlite3.connect(root / 'edu_submissions.sqlite', timeout=30) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS submissions (owner TEXT, request TEXT, fingerprint TEXT NOT NULL, PRIMARY KEY(owner, request))')
        connection.execute('INSERT OR IGNORE INTO submissions VALUES (?, ?, ?)', (owner, request_id, fingerprint))
        stored = connection.execute('SELECT fingerprint FROM submissions WHERE owner=? AND request=?', (owner, request_id)).fetchone()[0]
        if stored != fingerprint:
            raise SubmissionConflict('Submission ID is already bound to different inputs')


class SubmissionConflict(ValueError):
    pass


class QuestionCheckpoint:
    """Private immutable-input cache, shared only by explicit retries of one request."""
    def __init__(self, owner, request_id, inputs, *, revision=None):
        identity = {key: value for key, value in inputs.items() if key not in {"client_submission_id", "_edu_checkpoint_id"}}
        identity['pipeline_revision'] = revision if revision is not None else _migration_revision()
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        self.root = Path(os.environ['DEEPTUTOR_HOME']) / 'edu_checkpoints' / hashlib.sha256(owner.encode()).hexdigest() / request_id / digest
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, template, previous):
        identity = {'version': 2, 'template': template.blueprint}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return self.root / (digest + '.json')

    def read(self, template, previous):
        path = self._path(template, previous)
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, ValueError):
            return None

    def save(self, template, previous, value):
        import tempfile
        path = self._path(template, previous)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.root, delete=False) as handle:
            json.dump(value, handle, ensure_ascii=False)
            temporary = Path(handle.name)
        temporary.replace(path)


def _migration_revision():
    # A prompt/validator upgrade must not reuse questions accepted by an older revision.
    return json.loads((Path(__file__).resolve().parents[2] / 'upstream.lock.json').read_text())['patches']
