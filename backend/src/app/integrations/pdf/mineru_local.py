"""MinerU 4.x local task API, preserving complete page and asset artifacts."""
from __future__ import annotations

import re
import time
from urllib.parse import quote

import httpx

from .base import PdfParseError, PdfParseProvider
from .mineru_cloud import ParseControl, ParseStopped, _sanitize_filename
from .mineru_local_artifacts import parse_bundle


class LocalMinerUProvider(PdfParseProvider):
    provider_id = 'mineru-local'
    adapter_revision = 'mineru-local-v2'

    def __init__(self, base_url='http://127.0.0.1:8190', *, timeout_s=1800,
                 api_key='', clock=time.monotonic, sleep=time.sleep, client_factory=None):
        self.base_url = base_url.rstrip('/')
        if self.base_url.endswith('/v1'):
            self.base_url = self.base_url[:-3]
        self.timeout_s = float(timeout_s)
        if self.timeout_s <= 0:
            raise ValueError('MinerU timeout must be positive')
        self.api_key = api_key
        self.clock, self.sleep = clock, sleep
        self.client_factory = client_factory or httpx.Client

    def is_configured(self):
        return bool(self.base_url)

    def parse(self, pdf, *, filename='document.pdf', deadline=None, canceled=None, on_remote_task=None):
        started = self.clock()
        deadline = min(deadline, started + self.timeout_s) if deadline is not None else started + self.timeout_s
        control = ParseControl(deadline=deadline, canceled=canceled, clock=self.clock, sleep=self.sleep)
        control.check()
        if not pdf:
            raise PdfParseError('empty document')
        name = _sanitize_filename(filename)
        headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
        task_id = None
        with self.client_factory(trust_env=False, headers=headers) as client:
            try:
                response = client.post(f'{self.base_url}/v1/tasks',
                    params={'output_formats': 'zip'}, files={'files': (name, pdf, 'application/octet-stream')},
                    timeout=control.timeout(60))
                task = self._json(response)
                task_id = task.get('task_id')
                if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', task_id):
                    raise PdfParseError('MinerU local missing or invalid task ID')
                control.remote_task = {'provider': self.provider_id, 'task_id': task_id}
                if on_remote_task:
                    on_remote_task(dict(control.remote_task))
                control.check()
                task_url = f'{self.base_url}/v1/tasks/{quote(task_id, safe="")}'
                while task.get('status') in ('queued', 'running', 'processing', 'pending'):
                    control.wait(1)
                    task = self._json(client.get(task_url, timeout=control.timeout(10)))
                    control.check()
                if task.get('status') != 'completed':
                    raise PdfParseError('MinerU local task did not complete successfully')
                files = task.get('files')
                if not isinstance(files, list) or len(files) != 1 or files[0].get('status') != 'completed':
                    raise PdfParseError('MinerU local file did not complete successfully')
                response = client.get(task_url + '/result', params={'response_format': 'zip'},
                                      timeout=control.timeout(60))
                self._check_response(response)
                control.check()
                parsed = parse_bundle(response.content)
                parsed.metadata.update(parser=self.provider_id, adapterRevision=self.adapter_revision,
                    taskId=task_id, fileName=name, processingTime=round(self.clock()-started, 3))
                control.check()
                return parsed
            except Exception as exc:
                # Cancel the known remote task on timeout, cancellation, receipt
                # persistence failure or invalid output; never mask the original error.
                if task_id:
                    try:
                        client.delete(f'{self.base_url}/v1/tasks/{quote(task_id, safe="")}', timeout=3)
                    except Exception:
                        pass
                if isinstance(exc, ParseStopped):
                    raise
                if isinstance(exc, httpx.HTTPError):
                    control.check()
                    failure = PdfParseError(f'MinerU local request failed ({type(exc).__name__})')
                    failure.remote_task = control.remote_task
                    raise failure from exc
                exc.remote_task = control.remote_task
                raise

    @staticmethod
    def _check_response(response):
        if response.status_code not in (200, 201, 202):
            raise PdfParseError(f'MinerU local HTTP {response.status_code}')

    @classmethod
    def _json(cls, response):
        cls._check_response(response)
        try:
            data = response.json()
        except ValueError as exc:
            raise PdfParseError('MinerU local invalid JSON') from exc
        if not isinstance(data, dict):
            raise PdfParseError('MinerU local invalid response')
        return data
