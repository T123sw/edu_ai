"""Private loopback bridge keeps authenticated Python services in the API process."""
from __future__ import annotations

import hmac
import json
import secrets
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@contextmanager
def tool_bridge(toolset):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 262144:
                self.send_error(413)
                return
            message = json.loads(self.rfile.read(length))
            method = message.get("method")
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                          "serverInfo": {"name": "edu-report", "version": "1"}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": toolset.schemas()}
            elif method == "tools/call":
                params = message.get("params") or {}
                outcome = toolset.call(params.get("name", ""), params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": json.dumps(outcome, ensure_ascii=False)}],
                          "isError": not outcome["ok"]}
            else:
                self._send({"jsonrpc": "2.0", "id": message.get("id"),
                            "error": {"code": -32601, "message": "Unsupported method"}})
                return
            self._send({"jsonrpc": "2.0", "id": message.get("id"), "result": result})

        def _send(self, message):
            body = json.dumps(message, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/", token
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        # A timed-out MCP client can disconnect while a Python capability is
        # still completing. Keep the conversation lock until that call settles.
        with toolset.lock:
            pass
