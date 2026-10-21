"""Private preview process: let the OS allocate a port without a reservation race."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import sys


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=sys.argv[1]))
    print(json.dumps({'preview_url': f'http://127.0.0.1:{server.server_port}/'}), flush=True)
    server.serve_forever()
