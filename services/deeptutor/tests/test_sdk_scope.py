"""Exercise the real SDK/store boundary without a model call."""
import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from edu_deeptutor.api import Settings, create_app


def test_real_sdk_uses_distinct_owner_stores_and_keeps_auth_at_the_bridge():
    token = "sdk-scope-test-token-at-least-32-characters"
    with TestClient(create_app(settings=Settings(token=token))) as client:
        assert client.get("/health").json()["exam_ready"] is False
        gateway = client.app.state.gateway
        turn_id = "scope-test-" + uuid4().hex
        async def create_turn():
            from deeptutor.multi_user.context import get_current_user
            from deeptutor.services.session import get_session_store
            with gateway.owner_scope("scope-alice"):
                assert get_current_user().is_admin is False
                store = get_session_store()
                session = await store.create_session()
                await store.begin_turn(session["id"], turn_id=turn_id)
            alice, bob = await asyncio.gather(gateway.get("scope-alice", turn_id), gateway.get("scope-bob", turn_id))
            assert alice["turn_id"] == turn_id
            assert bob is None
        asyncio.run(create_turn())
        assert client.get(f"/internal/turns/{turn_id}").status_code == 401
        for owner, status in (("scope-alice", 200), ("scope-bob", 404)):
            assert client.get(f"/internal/turns/{turn_id}", headers={"Authorization": "Bearer " + token, "X-Edu-Owner": owner}).status_code == status
