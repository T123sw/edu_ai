import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base, Conversation, ConversationMessage


def test_conversation_import_cli_previews_and_applies_idempotently(
    tmp_path: Path, capsys
):
    from app.database.migrate_conversations_cli import main

    source = tmp_path / "conversations.json"
    source.write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "conversation_id": "conv-1",
                        "title": "Imported",
                        "created_at": "2026-08-10T10:00:00+00:00",
                        "updated_at": "2026-08-10T10:00:00+00:00",
                        "state": {},
                        "messages": [
                            {
                                "message_id": "msg-1",
                                "role": "user",
                                "content": "Hello",
                                "timestamp": "2026-08-10T10:00:00+00:00",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'target.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    assert main(["--source", str(source)]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "mode": "preview",
        "conversations": 1,
        "messages": 1,
    }
    for _ in range(2):
        assert (
            main(
                [
                    "--source",
                    str(source),
                    "--database-url",
                    database_url,
                    "--apply",
                ]
            )
            == 0
        )
        capsys.readouterr()

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 1
        assert (
            session.scalar(select(func.count()).select_from(ConversationMessage))
            == 1
        )
