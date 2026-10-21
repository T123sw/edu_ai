"""Start the real bridge on loopback, verify its boundary, then stop it."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="deeptutor-smoke-") as directory:
        token = secrets.token_hex(32)
        env = {**os.environ, "DEEPTUTOR_HOME": directory, "EDU_DEEPTUTOR_TOKEN": token}
        with (Path(directory) / "server.log").open("w+") as log:
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "edu_deeptutor.api:create_app",
                "--factory", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=log)
            try:
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2, trust_env=False) as client:
                    health = None
                    for _ in range(80):
                        if process.poll() is not None:
                            raise RuntimeError("Bridge exited during startup")
                        try:
                            health = client.get("/health")
                            if health.status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(0.25)
                    assert health is not None and health.status_code == 200
                    assert client.get("/internal/turns/unknown").status_code == 401
                    # First access creates the real per-owner SQLite schema.
                    started = time.monotonic()
                    status = client.get("/internal/turns/unknown", timeout=30,
                                        headers={"Authorization": "Bearer " + token, "X-Edu-Owner": "isolated-smoke-owner"})
                    assert status.status_code == 404
                    result = {"health": health.json(), "unauthenticated_status": 401,
                              "owner_scoped_missing_turn_status": status.status_code,
                              "cold_owner_read_seconds": round(time.monotonic() - started, 3), "real_model_calls": 0}
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            result["service_stopped"] = process.poll() is not None
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
