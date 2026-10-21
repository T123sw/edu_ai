from __future__ import annotations

import asyncio
from contextlib import aclosing, asynccontextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import subprocess
from urllib.parse import unquote

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from .contracts import GenerateRequest, public_progress
from .runtime import SubmissionConflict

ROOT = Path(__file__).resolve().parents[2]
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    source: Path = ROOT / ".upstream" / "DeepTutor"
    allowed_tools: frozenset[str] = frozenset()

    @classmethod
    def from_env(cls):
        token = os.getenv("EDU_DEEPTUTOR_TOKEN", "")
        if len(token) < 32:
            raise RuntimeError("EDU_DEEPTUTOR_TOKEN must contain at least 32 characters")
        return cls(token=token, allowed_tools=frozenset(filter(None, os.getenv("EDU_DEEPTUTOR_TOOLS", "").split(","))))


def verify_source(source: Path) -> dict:
    lock = json.loads((ROOT / "upstream.lock.json").read_text())
    def git(*args):
        return subprocess.check_output(["git", "-C", str(source), *args], text=True)
    if git("rev-parse", "HEAD").strip() != lock["commit"]:
        raise RuntimeError("Unexpected DeepTutor source version")
    expected = ""
    for entry in lock["patches"]:
        patch = ROOT / "patches" / entry["file"]
        if hashlib.sha256(patch.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("DeepTutor patch checksum mismatch")
        expected += patch.read_text()
    if git("diff", "--cached", "--name-only").strip() or git("diff", "--binary", "--no-ext-diff", "--no-color") != expected:
        raise RuntimeError("DeepTutor source differs from the reviewed patch set")
    return lock


async def event_lines(events, *, view="internal", heartbeat_seconds=15.0):
    """Read a context-scoped iterator in ONE task; keep idle NDJSON alive."""
    queue = asyncio.Queue(maxsize=64)
    async def produce():
        try:
            # Upstream owner/workspace scopes span yields. Both advancement
            # and finalization must run in this same task/context.
            async with aclosing(events):
                async for event in events:
                    await queue.put((event, None))
        except Exception as exc:
            await queue.put((None, exc))
        else:
            await queue.put((None, None))
    producer = asyncio.create_task(produce())
    try:
        while True:
            try:
                event, error = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                yield "\n"  # The existing client ignores blank lines.
                continue
            if error is not None:
                raise error
            if event is None:
                break
            record = event if view == "internal" else public_progress(event)
            yield json.dumps(record, ensure_ascii=False) + "\n"
    finally:
        if not producer.done():
            producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)


def create_app(*, settings: Settings | None = None, gateway=None) -> FastAPI:
    config = settings or Settings.from_env()
    if len(config.token) < 32:
        raise RuntimeError("Internal service token is too short")

    @asynccontextmanager
    async def lifespan(app):
        if gateway is None:
            app.state.upstream = verify_source(config.source)
            # Configure the process once, before importing upstream path singletons.
            runtime = Path(os.getenv("DEEPTUTOR_HOME", "").strip() or str(ROOT / ".runtime")).resolve()
            os.environ["DEEPTUTOR_HOME"] = str(runtime)
            settings_dir = runtime / "data" / "user" / "settings"
            settings_dir.mkdir(parents=True, exist_ok=True)
            from deeptutor.services.setup.init import DEFAULT_MAIN_SETTINGS, DEFAULT_AGENTS_SETTINGS
            import yaml
            for name, defaults in (("main.yaml", DEFAULT_MAIN_SETTINGS), ("agents.yaml", DEFAULT_AGENTS_SETTINGS)):
                try:
                    with (settings_dir / name).open("x") as handle:
                        yaml.safe_dump(defaults, handle, allow_unicode=True)
                except FileExistsError:
                    pass
            from deeptutor.services.config.runtime_settings import ensure_runtime_settings_files
            ensure_runtime_settings_files()
            from .gateway import SDKGateway
            app.state.gateway = SDKGateway(config.source, revision=app.state.upstream["patches"])
        else:
            app.state.gateway = gateway
            app.state.upstream = {"version": "test", "commit": "test"}
        try:
            yield
        finally:
            await app.state.gateway.close()

    app = FastAPI(title="Edu_AI DeepTutor internal bridge", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    async def owner(authorization: str = Header(default=""), x_edu_owner: str = Header(default="")):
        expected = "Bearer " + config.token
        if not hmac.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(401, "Internal authentication required")
        try:
            actor = unquote(x_edu_owner, encoding="utf-8", errors="strict")
        except UnicodeError:
            raise HTTPException(400, "Invalid owner identity") from None
        if not actor.strip() or len(actor) > 255 or "\r" in actor or "\n" in actor:
            raise HTTPException(400, "Owner identity required")
        return actor

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # Default FastAPI errors echo input, including uploaded documents.
        return JSONResponse(status_code=422, content={"detail": "Invalid generation request"})

    @app.get("/health")
    async def health(request: Request):
        return {"status": "ok", "version": request.app.state.upstream["version"],
                "commit": request.app.state.upstream["commit"], "scope": "internal_bridge", "exam_ready": False}

    @app.post("/internal/generations", status_code=202)
    async def start(body: GenerateRequest, request: Request, actor: str = Depends(owner)):
        try:
            payload = body.upstream_payload(config.allowed_tools)
        except ValueError as exc:
            raise HTTPException(422, "Requested configuration is not supported") from exc
        try:
            return await request.app.state.gateway.start(actor, payload)
        except SubmissionConflict:
            raise HTTPException(409, "Submission ID already used for different inputs") from None
        except PermissionError:
            raise HTTPException(403, "Model or resource access is not configured") from None
        except Exception as exc:
            # Keep provider errors and any prompt/credential text off the wire.
            log.warning("DeepTutor submission failed (%s)", type(exc).__name__)
            raise HTTPException(503, "Generation runtime unavailable; check service configuration") from None

    async def owned(request, actor, turn_id):
        turn = await request.app.state.gateway.get(actor, turn_id)
        if turn is None:
            raise HTTPException(404, "Generation not found")
        return turn

    @app.get("/internal/turns/{turn_id}")
    async def status(turn_id: str, request: Request, actor: str = Depends(owner)):
        return await owned(request, actor, turn_id)

    @app.get("/internal/turns/{turn_id}/events")
    async def events(turn_id: str, request: Request, after_seq: int = Query(default=0, ge=0),
                     view: str = Query(default="progress", pattern="^(progress|internal)$"), actor: str = Depends(owner)):
        await owned(request, actor, turn_id)
        stream = event_lines(request.app.state.gateway.events(actor, turn_id, after_seq), view=view)
        return StreamingResponse(stream, media_type="application/x-ndjson", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @app.post("/internal/turns/{turn_id}/cancel")
    async def cancel(turn_id: str, request: Request, actor: str = Depends(owner)):
        await owned(request, actor, turn_id)
        return {"cancel_requested": await request.app.state.gateway.cancel(actor, turn_id)}

    return app
