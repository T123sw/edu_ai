# RAG v2 Full Cutover Status

Date: 2026-04-15

## Current Runtime Contract

The backend runtime now uses `rag_v2` as the active RAG module.

- Backend callers import `rag_v2.api`.
- `rag_v2/rag_main/` is the import-safe runtime package.
- `rag_v2.document_resolver` is the only shared business-layer resolver for selected document identifiers.
- Business code should pass public RAG v2 `index_key` values wherever possible.
- Legacy physical paths are accepted only as an internal compatibility input to `document_resolver`; business code should not manually inspect `document_index` or rebuild document keys.

## Completed Cutover Work

- Teacher lesson-plan, report, and quiz generation now load selected documents through one shared RAG v2 resolver helper.
- Course knowledge-base import resolves RAG document identifiers through RAG v2 before reading files.
- Knowledge-base summary and document-content providers resolve selected documents through RAG v2.
- Chat RAG tools and web/deepsearch follow-up retrieval now pass resolved public `index_key` values to RAG queries instead of mixing absolute paths, index keys, and source keys.
- Runtime code has a regression test that prevents `new_rag` references from reappearing in active backend modules.
- `rag_v2` media routes keep local file paths behind guarded storage-relative URLs.

## Image Retrieval Boundary

Image retrieval should be added inside the active `rag_v2` runtime rather than through a separate legacy adapter.

The expected boundary is:

- Store imported image metadata under owner-isolated RAG v2 storage.
- Return storage-relative media identifiers or guarded URLs, not local absolute paths.
- Reuse `index_key` for document selection and owner isolation.
- Keep multimodal/image-specific ranking inside `rag_v2.rag_main`, while business callers continue using `rag_v2.api` and `rag_v2.document_resolver`.

## Guardrails

- Do not add new imports from the old RAG package in `app/**` or `rag_v2/rag_main/**`.
- Do not add ad-hoc selected-document matching in business endpoints.
- Do not expose absolute local paths to frontend-facing responses when a public key or guarded media URL is available.
