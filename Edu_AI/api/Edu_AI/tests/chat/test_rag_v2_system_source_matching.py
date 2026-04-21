import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from rag_v2.rag_main.system import _match_allowed_source


def test_match_allowed_source_resolves_source_key_even_when_set_iteration_starts_with_source_key_variant():
    document_index = {
        "index-key": {
            "source_key": "source-key",
            "owner": None,
        }
    }
    allowed_sources = {"source-key", "index-key"}

    matched_key = _match_allowed_source(document_index, allowed_sources, "source-key")

    assert matched_key == "index-key"
