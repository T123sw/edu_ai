"""Bounded loopback MCP transport for long, private content submissions."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import secrets
import threading
import time


@contextmanager
def content_tool_bridge(toolset, *, timeout):
    # The workbench bridge's 256 KiB limit cannot carry a 65k-token review
    # escaped as JSON. Bound this transport independently of the legacy bridge.
    token = secrets.token_urlsafe(32)
    deadline = time.monotonic() + timeout

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(max(.1, deadline - time.monotonic()))

        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2_000_000:
                    self.send_error(413)
                    return
                message = json.loads(self.rfile.read(length))
                method = message.get('method')
                if method == 'initialize':
                    result = {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}},
                              'serverInfo': {'name': 'preparation-content', 'version': '1'}}
                elif method == 'ping':
                    result = {}
                elif method == 'tools/list':
                    result = {'tools': toolset.schemas()}
                elif method == 'tools/call':
                    params = message.get('params') or {}
                    outcome = toolset.call(params.get('name', ''), params.get('arguments'))
                    result = {'content': [{'type': 'text', 'text': json.dumps(outcome, ensure_ascii=False)}],
                              'isError': not outcome['ok']}
                else:
                    self.send_error(400)
                    return
                body = json.dumps({'jsonrpc': '2.0', 'id': message.get('id'), 'result': result}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (OSError, ValueError, TypeError, AttributeError):
                # Disconnected/invalid clients cannot create a candidate.
                self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = False
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05})
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/', token
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
