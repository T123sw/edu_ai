# rag_v2

`rag_v2` is the active backend RAG runtime module.

Current status:
- Backend runtime imports and routes are switched to `rag_v2.api`.
- `rag_v2/rag_main/` is the import-safe runtime package copied from the uploaded `rag-main` source.
- Public document identifiers should be RAG v2 index keys. Legacy physical paths are resolved only through `rag_v2.document_resolver`.
- Business code should not import or call the old RAG module.

Recommended next step:
- Add image retrieval on top of the active `rag_v2` runtime, reusing the same owner isolation and public identifier rules.
