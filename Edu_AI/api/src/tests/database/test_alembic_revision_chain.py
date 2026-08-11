from __future__ import annotations

import warnings
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


API_ROOT = Path(__file__).resolve().parents[2]


def test_alembic_revision_chain_has_unique_revisions_and_one_head() -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        script = ScriptDirectory.from_config(config)
        revisions = list(script.walk_revisions())
        heads = script.get_heads()

    revision_ids = [item.revision for item in revisions]
    assert len(revision_ids) == len(set(revision_ids))
    assert len(heads) == 1
