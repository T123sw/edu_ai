"""Expose existing speech as the upstream audio engine's host provider."""
from contextlib import contextmanager
from contextvars import copy_context
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn, UnixStreamServer
from pathlib import Path
import hashlib
import json
import os
import shutil
import threading

from .runtime import NativeRuntime


@contextmanager
def audio_provider(workspace, *, guard, options, narrate=None):
    workspace = Path(workspace).resolve()
    socket = workspace / '.host/audio.sock'
    socket.parent.mkdir(exist_ok=True)
    socket.unlink(missing_ok=True)
    if narrate is None:
        from .generation import _narrate
        narrate = _narrate

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
                if 'tts' in only:
                    cache = workspace / '.host/audio-cache'
                    cache.mkdir(exist_ok=True)
                    for line in request.get('lines', []):
                        guard()
                        text = line['text']
                        effective_options = {**options, 'speed':request.get('speed', options.get('speed'))}
                        name = hashlib.sha256((text + json.dumps(effective_options, sort_keys=True)).encode()).hexdigest()
                        target = project / 'assets/audio' / (name + '.mp3')
                        target.resolve().relative_to(workspace)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            source = Path(narrate(text, cache, effective_options))
                            shutil.copyfile(source, target)
                        duration = NativeRuntime().audio_duration(target)
                        voices.append({'id': str(line['id']), 'path': target.relative_to(project).as_posix(),
                                       'duration_s': duration, 'words': []})
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

    runtime_context = copy_context()

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
