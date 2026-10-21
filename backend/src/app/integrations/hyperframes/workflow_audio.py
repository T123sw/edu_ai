"""Expose existing speech as the upstream audio engine's host provider."""
from contextlib import contextmanager
from contextvars import copy_context
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn, UnixStreamServer
from pathlib import Path
import hashlib
import json
import os
import shutil
import threading
import tempfile

from .runtime import NativeRuntime
from app.services.classroom_narration import NARRATION_CACHE_VERSION


@contextmanager
def audio_provider(workspace, *, guard, options, narrate=None):
    workspace = Path(workspace).resolve()
    socket = workspace / '.host/audio.sock'
    socket.parent.mkdir(exist_ok=True)
    socket.unlink(missing_ok=True)
    if narrate is None:
        from .generation import _narrate
        narrate = _narrate
    cache_locks = {}
    cache_locks_guard = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            try:
                guard()
                if self.path != '/audio': raise ValueError('Unknown audio operation')
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length < 2_000_000: raise ValueError('Invalid audio request')
                value = json.loads(self.rfile.read(length))
                project = Path(value['project']).resolve()
                project.relative_to(workspace)
                request = value['request']
                voices = []
                only = value.get('only', 'tts,bgm,sfx').split(',')
                if 'tts' in only and request.get('lines') and options.get('enable_tts') is False:
                    raise ValueError('Narration was explicitly disabled in BRIEF.md; preserve silent delivery, do not synthesize speech')
                if 'tts' in only:
                    cache = workspace / '.host/audio-cache'
                    cache.mkdir(exist_ok=True)
                    def render_line(line):
                        guard()
                        text = line['text']
                        effective_options = {**options, 'speed':request.get('speed', options.get('speed'))}
                        name = hashlib.sha256((NARRATION_CACHE_VERSION + text + json.dumps(effective_options, sort_keys=True)).encode()).hexdigest()
                        target = project / 'assets/audio' / (name + '.mp3')
                        target.resolve().relative_to(workspace)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with cache_locks_guard:
                            line_lock = cache_locks.setdefault(str(target), threading.Lock())
                        # Repeated native calls or duplicate lines share a single synthesis.
                        while not line_lock.acquire(timeout=.5):
                            guard()
                        try:
                            guard()
                            if not target.exists():
                                source = Path(narrate(text, cache, effective_options))
                                guard()
                                with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.mp3', delete=False) as temp:
                                    temporary = Path(temp.name)
                                try:
                                    shutil.copyfile(source, temporary)
                                    os.replace(temporary, target)
                                finally:
                                    temporary.unlink(missing_ok=True)
                        finally:
                            line_lock.release()
                        duration = NativeRuntime().audio_duration(target)
                        return {'id': str(line['id']), 'path': target.relative_to(project).as_posix(),
                                'duration_s': duration, 'words': []}
                    concurrency = max(1, min(12, int(os.getenv('HYPERFRAMES_AUDIO_CONCURRENCY', '8'))))
                    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix='hf-audio') as pool:
                        futures = [pool.submit(copy_context().run, render_line, line)
                                   for line in request.get('lines', [])]
                        try:
                            voices = [future.result() for future in futures]
                        except BaseException:
                            for future in futures:
                                future.cancel()
                            raise
                result = {'tts_provider': 'host', 'voice_id': options.get('voice')}
                if 'tts' in only:
                    result.update(voices=voices, total_duration_s=sum(v['duration_s'] for v in voices))
                body = json.dumps(result).encode()
                self.send_response(200)
            except Exception as exc:
                body = json.dumps({'error': str(exc)}).encode()
                self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    from .stage_limits import ADMISSION_GUARD
    runtime_context = copy_context()
    runtime_context.run(ADMISSION_GUARD.set, guard)

    class Server(ThreadingMixIn, UnixStreamServer):
        daemon_threads = True

        def process_request_thread(self, request, client_address):
            return runtime_context.copy().run(super().process_request_thread, request, client_address)

    directory_fd = os.open(socket.parent, os.O_RDONLY | os.O_DIRECTORY)
    # Unix socket names are limited to ~108 bytes; persistent project paths are longer.
    try:
        server = Server(f'/proc/self/fd/{directory_fd}/audio.sock', Handler)
    except Exception:
        os.close(directory_fd)
        raise
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield socket
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        socket.unlink(missing_ok=True)
        os.close(directory_fd)
