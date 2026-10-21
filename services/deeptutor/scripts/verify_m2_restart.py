"""Kill and restart the real bridge during a controlled model HTTP request."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4
import httpx


def main():
    entered, release = threading.Event(), threading.Event()
    calls = []
    class Model(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            calls.append(self.path)
            entered.set()
            release.wait(60)
            try:
                self.send_response(503)
                self.end_headers()
            except OSError:
                pass
    model = ThreadingHTTPServer(('127.0.0.1', 0), Model)
    model.daemon_threads = True
    threading.Thread(target=model.serve_forever, daemon=True).start()
    root = Path(__file__).resolve().parents[1]
    token = secrets.token_urlsafe(40)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='deeptutor-restart-') as temporary:
        env = {**os.environ, 'DEEPTUTOR_HOME': temporary, 'EDU_DEEPTUTOR_TOKEN': token}
        env.pop('PYTHONPATH', None)
        def start():
            process = subprocess.Popen([str(root / '.venv/bin/python'), '-m', 'uvicorn', 'edu_deeptutor.api:create_app', '--factory',
                '--host', '127.0.0.1', '--port', str(port)], cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError('Bridge startup failed')
                try:
                    if httpx.get(f'http://127.0.0.1:{port}/health', trust_env=False, timeout=1).status_code == 200:
                        return process
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
            process.kill()
            process.wait()
            raise RuntimeError('Bridge startup timeout')
        process = None
        try:
            process = start()
            headers = {'Authorization': 'Bearer ' + token, 'X-Edu-Owner': 'restart-alice'}
            payload = {'request_id': str(uuid4()), 'requirement': 'Generate one sorting question', 'num_questions': 1,
                'runtime_model': {'model': 'controlled-model', 'api_key': 'not-a-secret', 'base_url': f'http://127.0.0.1:{model.server_port}/v1'}}
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers=headers, timeout=30, trust_env=False) as client:
                response = client.post('/internal/generations', json=payload)
                response.raise_for_status()
                first = response.json()
                if not entered.wait(30): raise RuntimeError('Controlled model boundary was not reached')
                process.kill()
                process.wait(timeout=10)
                process = start()
                status = client.get('/internal/turns/' + first['turn_id'])
                status.raise_for_status()
                assert status.json()['status'] == 'failed'
                duplicate = client.post('/internal/generations', json=payload)
                duplicate.raise_for_status()
                assert duplicate.json()['turn_id'] == first['turn_id']
                assert duplicate.json()['status'] == 'failed'
                events = client.get('/internal/turns/' + first['turn_id'] + '/events', params={'view': 'internal'})
                events.raise_for_status()
                records = [json.loads(line) for line in events.text.splitlines() if line.strip()]
                assert any(e['type'] == 'done' and e['metadata'].get('status') == 'failed' for e in records)
                assert client.get('/internal/turns/' + first['turn_id'], headers={**headers, 'X-Edu-Owner': 'restart-bob'}).status_code == 404
                assert len(calls) == 1
                result = {'real_http': True, 'real_process_kill_and_restart': True, 'model_boundary': 'controlled HTTP test double',
                    'terminal_status': status.json()['status'], 'duplicate_keeps_turn': True, 'model_requests': len(calls),
                    'other_owner_status': 404, 'recovery_done_event': True, 'production_writes': False}
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            release.set()
            model.shutdown()
            model.server_close()
    result['services_stopped'] = True
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
