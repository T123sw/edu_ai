import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from rag_v2.rag_main.system import RAGSystem


def test_list_documents_includes_public_documents_for_named_owner():
    rag_system = RAGSystem.__new__(RAGSystem)
    rag_system.document_index = {
        "shared-course-doc": {
            "file_name": "shared.md",
            "owner": None,
            "include_in_search": True,
        },
        "user_alice:/tmp/private.md": {
            "file_name": "private.md",
            "owner": "alice",
            "include_in_search": True,
        },
        "user_bob:/tmp/secret.md": {
            "file_name": "secret.md",
            "owner": "bob",
            "include_in_search": True,
        },
    }

    listed = rag_system.list_documents(owner="alice")

    assert [doc["file_path"] for doc in listed] == [
        "shared-course-doc",
        "user_alice:/tmp/private.md",
    ]
