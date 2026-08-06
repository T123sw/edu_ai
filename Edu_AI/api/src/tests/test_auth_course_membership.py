from __future__ import annotations

import asyncio

from app import auth
from app.schemas.auth import RegisterRequest


def test_registration_auto_enrolls_the_created_user(monkeypatch):
    created = {"username": "new-teacher", "role": "teacher"}
    enrolled: list[dict] = []

    monkeypatch.setattr(auth.user_storage, "create_user", lambda **kwargs: created)
    monkeypatch.setattr(auth.auth_manager, "create_token", lambda **kwargs: "token")
    monkeypatch.setattr(
        auth,
        "get_course_membership_bootstrap",
        lambda: type(
            "BootstrapSpy",
            (),
            {"on_user_created": lambda self, user: enrolled.append(dict(user))},
        )(),
    )

    response = asyncio.run(
        auth.register(
            RegisterRequest(
                username="new-teacher",
                password="safe-password",
                role="teacher",
            )
        )
    )

    assert response.token == "token"
    assert enrolled == [created]
