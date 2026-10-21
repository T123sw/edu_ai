"""Retry a rejected completion with the backup key, never replay an agent turn.

The local authenticated transport also works for the Harness subprocess. It is
created only when a distinct backup is configured; secrets stay in this process.
"""
from __future__ import annotations

import json
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import secrets
import threading

import httpx

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_endpoints = {}


def upstream_base_url(base_url: str):
    """Resolve only this process's registered proxy; never return credentials."""
    with _lock:
        for identity, endpoint in _endpoints.items():
            if endpoint[0].rstrip('/') == base_url.rstrip('/'):
                return identity[0]
    return base_url


def _start_endpoint(base: str, primary: str, backup: str):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_args):
            pass

        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.send_error(403)
                return
            if self.path != '/v1/chat/completions':
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                self.send_error(400)
                return
            if length <= 0 or length > 32 * 1024 * 1024:
                self.send_error(413)
                return
            body = self.rfile.read(length)
            sent = False
            try:
                from core.config import Config
                with httpx.Client(timeout=httpx.Timeout(180, connect=15),
                                  trust_env=Config.DEEPSEEK_TRUST_ENV_PROXY,
                                  transport=None if Config.DEEPSEEK_TRUST_ENV_PROXY else httpx.HTTPTransport(retries=1)) as client:
                    for index, key in enumerate((primary, backup)):
                        with client.stream('POST', base + '/chat/completions', content=body,
                                           headers={'Authorization': 'Bearer ' + key,
                                                    'Content-Type': 'application/json', 'Accept-Encoding': 'identity'}) as response:
                            if response.status_code == 402 and index == 0:
                                logger.warning('DeepSeek primary key returned HTTP 402; retrying completion with backup key')
                                continue
                            self.send_response(response.status_code)
                            self.send_header('Content-Type', response.headers.get('content-type', 'application/json'))
                            self.send_header('Connection', 'close')
                            self.end_headers()
                            self.close_connection = True
                            sent = True
                            for chunk in response.iter_bytes():
                                self.wfile.write(chunk)
                                self.wfile.flush()
                            return
            except (httpx.HTTPError, OSError) as exc:
                logger.warning('DeepSeek completion transport failed: %s; response_started=%s', type(exc).__name__, sent)
                if not sent:
                    payload = json.dumps({'error': {'code': 'model_transport_unavailable',
                        'message': '模型连接暂时不可用，请稍后重试。'}}, ensure_ascii=False).encode()
                    self.send_response(502)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(payload)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(payload)
                self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.1}, daemon=True,
                     name='deepseek-key-failover').start()
    return f'http://127.0.0.1:{server.server_port}/v1', token, server


def completion_endpoint(base_url: str, api_key: str | None):
    from core.config import Config
    base = str(base_url or '').rstrip('/')
    configured = str(Config.DEEPSEEK_BASE_URL or '').rstrip('/')
    # This backup is scoped to the configured DeepSeek endpoint, never sent to
    # a different provider or an arbitrary user-selected host.
    if base.removesuffix('/v1') != configured.removesuffix('/v1'):
        return base_url, api_key
    backup = str(Config.DEEPSEEK_API_KEY_BACKUP or '').strip()
    requested = str(api_key or '').strip()
    # The endpoint identity determines the credential order. A role alias or
    # runtime override may select a model, but it cannot put another DeepSeek
    # credential ahead of the project-wide primary key.
    primary = Config.resolve_llm_api_key(base_url, requested)
    if not backup or backup == primary:
        return base_url, primary
    if not primary:
        return base_url, backup
    if not base.endswith('/v1'):
        base += '/v1'
    identity = (base, primary, backup)
    with _lock:
        if identity not in _endpoints:
            _endpoints[identity] = _start_endpoint(*identity)
        local, token, _server = _endpoints[identity]
    return local, token
