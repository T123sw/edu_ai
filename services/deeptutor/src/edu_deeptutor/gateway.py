from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
from pathlib import Path


class SDKGateway:
    """Use the upstream application service; do not replace its generation loop."""

    def __init__(self, source: Path, *, revision=None):
        from deeptutor.app import DeepTutorApp
        from deeptutor.agents.question import pipeline
        if not Path(pipeline.__file__).resolve().is_relative_to(source.resolve()):
            raise RuntimeError("DeepTutor was imported from an unverified installation")
        self.app = DeepTutorApp(workspace_id="")
        from .runtime import ExamTurnEngine, _migration_revision
        self.revision = deepcopy(revision if revision is not None else _migration_revision())
        if not isinstance(self.app.container.runtime_registry.turn_engine, ExamTurnEngine):
            self.app.container.runtime_registry.turn_engine = ExamTurnEngine(self.app.container.turn_engine)

    @contextmanager
    def owner_scope(self, owner: str):
        from deeptutor.multi_user.models import CurrentUser
        from deeptutor.multi_user.paths import ensure_scope_workspace, scope_for_user, user_context
        identifier = "edu_" + hashlib.sha256(owner.encode()).hexdigest()
        scope = scope_for_user(identifier, is_admin=False)
        ensure_scope_workspace(scope)
        with user_context(CurrentUser(id=identifier, username=owner, role="user", scope=scope)):
            yield

    async def start(self, owner: str, payload: dict) -> dict:
        from .runtime import model_scope, prepare_sources, reserve_request, QuestionCheckpoint
        import os
        from deeptutor.services.session import get_session_store
        import json
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        reserve_request(owner, payload['client_submission_id'], fingerprint)
        payload = deepcopy(payload)
        checkpoint_id = payload.get("_edu_checkpoint_id") or payload["client_submission_id"]
        checkpoint = QuestionCheckpoint(owner, checkpoint_id, payload, revision=self.revision)
        payload.pop("_edu_checkpoint_id", None)
        model = payload.pop("_edu_model", None)
        text_model = payload.pop("_edu_text_model", None)
        sources = payload.pop("_edu_sources", [])
        allowed = frozenset(filter(None, os.getenv("EDU_DEEPTUTOR_BUILTIN_TOOLS", "read_source").split(",")))
        with self.owner_scope(owner), model_scope(model, allowed, checkpoint, text_model):
            payload = prepare_sources(owner, checkpoint_id, sources, payload, revision=self.revision)
            # Upstream normally resubmits failed turns. The bridge treats every
            # submission as immutable; explicit retries use a new request ID.
            store = get_session_store()
            prior = await store.submission_turn(payload["client_submission_id"])
            if prior is not None:
                # reserve_submission validates the original payload digest.
                import json
                identity = {k: v for k, v in self._normalized_payload(payload).items()
                            if k not in {"session_id", "workspace_id"}}
                digest = hashlib.sha256(json.dumps(identity, sort_keys=True, default=str).encode()).hexdigest()
                await store.reserve_submission(payload["client_submission_id"], digest, None)
                return {"session_id": prior["session_id"], "turn_id": prior["id"], "status": prior["status"]}
            session, turn = await self.app.start_turn(payload)
            return {"session_id": session["id"], "turn_id": turn["id"], "status": turn["status"]}

    @staticmethod
    def _normalized_payload(payload):
        from deeptutor.app import TurnRequest
        return TurnRequest.model_validate(payload).to_payload()

    async def get(self, owner: str, turn_id: str) -> dict | None:
        from deeptutor.services.session import get_session_store
        with self.owner_scope(owner):
            turn = await get_session_store().get_turn(turn_id)
            if turn is None:
                return None
            if turn['status'] in {'queued', 'running', 'waiting_input'} and await self.app.container.coordinator.get_lease(turn_id) is None:
                await self.app.turns._reap_unowned_live_turn(turn_id)
                turn = await get_session_store().get_turn(turn_id)
            # Do not return the upstream error/log/body through the status route.
            return {"turn_id": turn["id"], "session_id": turn["session_id"],
                    "status": turn["status"], "last_seq": turn.get("last_seq", 0)}

    async def events(self, owner: str, turn_id: str, after_seq: int):
        with self.owner_scope(owner):
            async for event in self.app.stream_turn(turn_id, after_seq=after_seq):
                yield event

    async def cancel(self, owner: str, turn_id: str) -> bool:
        with self.owner_scope(owner):
            return await self.app.cancel_turn(turn_id)

    async def close(self):
        await self.app.container.close()
        from deeptutor.app.container import set_application_container
        set_application_container(None)
