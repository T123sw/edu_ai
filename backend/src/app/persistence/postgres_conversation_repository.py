from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from app.database import Conversation, ConversationMessage, database_session

from .postgres_repositories import _iso_timestamp, _required_text, _timestamp


def _scope_fields(state: Mapping[str, Any]) -> tuple[str | None, str, str | None]:
    active_context = dict(state.get("active_context") or {})
    course_id = str(
        state.get("course_id")
        or active_context.get("current_course_id")
        or active_context.get("course_id")
        or ""
    ).strip() or None
    scope_type = str(
        state.get("scope_type") or active_context.get("scope_type") or "course"
    ).strip() or "course"
    scope_id = str(
        state.get("scope_id") or active_context.get("scope_id") or ""
    ).strip() or None
    if scope_type == "course":
        scope_id = None
    return course_id, scope_type, scope_id


class PostgresConversationRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def upsert(self, conversation: Mapping[str, Any]) -> None:
        payload = dict(conversation)
        conversation_id = _required_text(
            payload.get("conversation_id"), "conversation_id"
        )
        state = dict(payload.get("state") or {})
        course_id, scope_type, scope_id = _scope_fields(state)
        with database_session(engine=self._engine) as session:
            record = session.get(Conversation, conversation_id)
            if record is None:
                record = Conversation(conversation_id=conversation_id)
                session.add(record)
            record.owner = str(payload.get("owner") or "").strip() or None
            record.title = str(payload.get("title") or "")
            record.course_id = course_id
            record.scope_type = scope_type
            record.scope_id = scope_id
            record.state = state
            record.created_at = _timestamp(
                payload.get("created_at"), default=record.created_at
            )
            record.updated_at = _timestamp(payload.get("updated_at"))
            record.raw_payload = {
                key: value for key, value in payload.items() if key != "messages"
            }

            session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.conversation_id == conversation_id
                )
            )
            messages = payload.get("messages") or []
            if not isinstance(messages, list):
                raise ValueError("messages must be a list")
            for position, source in enumerate(messages):
                message = dict(source or {})
                role = _required_text(message.get("role"), "role")
                message_id = _required_text(
                    message.get("message_id")
                    or f"{conversation_id}:msg:{position + 1}",
                    "message_id",
                )
                session.add(
                    ConversationMessage(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        position=position,
                        role=role,
                        content=str(message.get("content") or ""),
                        message_kind=str(
                            message.get("message_kind")
                            or (
                                "user_content"
                                if role == "user"
                                else "assistant_content"
                            )
                        ),
                        occurred_at=_timestamp(message.get("timestamp")),
                        raw_payload=message,
                    )
                )

    def get(self, conversation_id: str) -> dict[str, Any] | None:
        normalized_id = _required_text(conversation_id, "conversation_id")
        with database_session(engine=self._engine) as session:
            record = session.get(Conversation, normalized_id)
            return self._payload(record) if record is not None else None

    def list(self) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(Conversation).order_by(Conversation.created_at)
            ).all()
            return [self._payload(record) for record in records]

    def delete(self, conversation_id: str) -> bool:
        normalized_id = _required_text(conversation_id, "conversation_id")
        with database_session(engine=self._engine) as session:
            record = session.get(Conversation, normalized_id)
            if record is None:
                return False
            session.delete(record)
            return True

    @staticmethod
    def _payload(record: Conversation) -> dict[str, Any]:
        payload = dict(record.raw_payload or {})
        messages: list[dict[str, Any]] = []
        for message in record.messages:
            item = dict(message.raw_payload or {})
            item.update(
                {
                    "message_id": message.message_id,
                    "role": message.role,
                    "content": message.content,
                    "message_kind": message.message_kind,
                    "timestamp": _iso_timestamp(message.occurred_at),
                }
            )
            messages.append(item)
        payload.update(
            {
                "conversation_id": record.conversation_id,
                "owner": record.owner,
                "title": record.title,
                "state": dict(record.state or {}),
                "created_at": _iso_timestamp(record.created_at),
                "updated_at": _iso_timestamp(record.updated_at),
                "messages": messages,
            }
        )
        return payload
