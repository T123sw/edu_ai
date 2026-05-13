import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def test_rag_v2_top_level_compat_surface_matches_runtime_package():
    from modules.rag_v2 import __all__ as rag_v2_all
    from modules.rag_v2 import api as compat_api
    from modules.rag_v2 import system as compat_system
    from modules.rag_v2.rag_main import api as runtime_api
    from modules.rag_v2.rag_main import system as runtime_system

    expected_symbols = [
        "router",
        "get_rag_system",
        "RAGSystem",
        "QueryRequest",
        "QueryResponse",
        "ImportResponse",
        "StatsResponse",
        "DocumentInfo",
        "DocumentParticipationRequest",
        "DocumentDetailResponse",
        "DocumentSummaryRequest",
        "DocumentSummaryResponse",
        "ImportFromPathRequest",
        "UploadTempResponse",
        "ImportProgressResponse",
        "RenameDocumentRequest",
        "DocumentContentResponse",
    ]

    for symbol_name in expected_symbols:
        assert hasattr(compat_api, symbol_name)
        assert symbol_name in rag_v2_all

    assert compat_api.router is runtime_api.router
    assert compat_api.get_rag_system is runtime_api.get_rag_system
    assert compat_api.RAGSystem is runtime_system.RAGSystem
    assert compat_system.RAGSystem is runtime_system.RAGSystem

    model_symbols = [name for name in expected_symbols if name not in {"router", "get_rag_system", "RAGSystem"}]
    for symbol_name in model_symbols:
        assert getattr(compat_api, symbol_name) is getattr(runtime_api, symbol_name)


def test_rag_v2_top_level_surface_exposes_required_backend_entrypoints():
    from modules.rag_v2 import api as compat_api

    expected_symbols = [
        "router",
        "get_rag_system",
        "RAGSystem",
        "QueryRequest",
        "QueryResponse",
        "ImportResponse",
        "StatsResponse",
        "DocumentInfo",
        "DocumentParticipationRequest",
        "DocumentDetailResponse",
        "DocumentSummaryRequest",
        "DocumentSummaryResponse",
        "ImportFromPathRequest",
        "UploadTempResponse",
        "ImportProgressResponse",
        "RenameDocumentRequest",
        "DocumentContentResponse",
    ]

    for symbol_name in expected_symbols:
        assert hasattr(compat_api, symbol_name)
