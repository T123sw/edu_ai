"""Shared, fail-closed provenance for opt-in real HTTP/worker acceptance."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def git_identity():
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True).strip())
    return {'code_sha': sha, 'dirty': dirty}


def database_identity(value):
    from sqlalchemy.engine import make_url
    try:
        url = make_url(value)
    except Exception:
        raise ValueError('TEST_DATABASE_URL_INVALID') from None
    if url.get_backend_name() != 'postgresql' or not re.fullmatch(r'edu_ai_preparation_test_[a-z0-9_]+', url.database or ''):
        raise ValueError('DEDICATED_POSTGRES_DATABASE_REQUIRED')
    if url.query:
        raise ValueError('TEST_DATABASE_URL_QUERY_NOT_ALLOWED')
    # No username, password or DSN is returned or persisted.
    return {'database': url.database, 'endpoint_digest': digest([url.host, url.port or 5432, url.database])}


def local_http(value):
    url = urlsplit(value)
    if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1') or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise ValueError('DEDICATED_LOOPBACK_HTTP_REQUIRED')
    return value.rstrip('/')


def redact(value):
    """Structured defense in depth; evidence callers still use field allowlists."""
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if re.search(r'password|secret|api.?key|authorization|credential|access_token|refresh_token|config_snapshot', k, re.I) else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'(?i)Bearer\s+\S+', 'Bearer [REDACTED]', value)
        value = re.sub(r'(?i)(?:postgresql(?:\+\w+)?|https?)://[^\s/]+:[^\s/@]+@', '[REDACTED-URL]@', value)
        value = re.sub(r'\bsk-[A-Za-z0-9_-]{12,}\b', '[REDACTED]', value)
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(value), ensure_ascii=False, indent=2, default=str) + '\n')
