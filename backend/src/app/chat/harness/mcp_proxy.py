"""Dependency-free stdio transport to the request-scoped MCP bridge.

Executed as a script by dsh. Never import application code or print diagnostics
on stdout; it belongs exclusively to MCP JSON-RPC.
"""
import json
import os
import sys
from urllib.request import Request, urlopen


def main():
    for line in sys.stdin:
        message = json.loads(line)
        if "id" not in message:
            continue
        request = Request(
            os.environ["EDU_MCP_URL"], data=line.encode(),
            headers={"Authorization": "Bearer " + os.environ["EDU_MCP_TOKEN"],
                     "Content-Type": "application/json"}, method="POST",
        )
        try:
            with urlopen(request, timeout=125) as response:
                result = response.read().decode()
        except Exception:
            result = json.dumps({"jsonrpc": "2.0", "id": message["id"],
                                 "error": {"code": -32603, "message": "Tool bridge unavailable"}})
        print(result, flush=True)


if __name__ == "__main__":
    main()
