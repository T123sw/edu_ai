# Professional Multimodal Course Knowledge Base Implementation Plan

> **Execution rule:** Complete tasks in order. Use test-driven changes, keep each migration reversible, and do not rebuild the active course library until the staging evaluation gate passes.

**Goal:** Deliver a complete, professional, Chinese-first computational-thinking course knowledge base with a curriculum-oriented graph, at least three substantive documents per leaf knowledge point, preserved formulas/tables/images/video, Gemini Embedding 2 multimodal indexing, structure-aware parent-child chunks, measurable hybrid retrieval, correct personal/course ownership, usable previews, and atomic rollback.

**Design:** `docs/superpowers/specs/2026-08-08-professional-multimodal-course-knowledge-base-design.md`

**Runtime constraint:** Do not deploy full Docling. Keep MinerU Cloud for PDF parsing and implement a bounded-memory internal `ContentBlock` layer.

---

## Phase 0 Completion Gate

Before changing ingestion behavior:

- preserve a read-only snapshot of the current graph, course KB index and active RAG document index;
- create a deterministic baseline report for the current 244 documents / 827 chunks;
- add representative fixtures for Markdown, HTML, DOCX, PDF/MinerU output, image, table, formula, code and video metadata;
- establish a small gold-query set that reproduces current retrieval failures;
- do not copy or delete user-owned `api/data/` content.

---

## Task 1: Freeze baseline and add reproducible audit tooling

**Files:**

- Create: `api/src/app/services/knowledge_quality/audit_models.py`
- Create: `api/src/app/services/knowledge_quality/index_audit.py`
- Create: `api/src/scripts/audit_course_knowledge_base.py`
- Create: `api/src/tests/knowledge_quality/test_index_audit.py`
- Create: `docs/qa/course-knowledge-baseline-2026-08-08.md`

- [ ] Write tests that construct an index containing tiny chunks, silently truncated embedding inputs, broken code fences, missing media, duplicate chunks and wrong access scopes.
- [ ] Implement a read-only audit that reports document count, modalities, token/character distribution, malformed structures, duplicate hashes, missing files and scope violations.
- [ ] Ensure the tool never initializes or mutates Chroma when run in audit mode.
- [ ] Run it against `computational-thinking` and record baseline evidence without copying private content into the report.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/knowledge_quality/test_index_audit.py -q
D:\anaconda\envs\edu-ai\python.exe -m app.scripts.audit_course_knowledge_base --course-id computational-thinking --read-only
```

**Expected:** deterministic report; active indexes remain byte-for-byte unchanged.

---

## Task 2: Make personal and course access scopes first-class

**Files:**

- Modify: `api/src/modules/rag_v2/rag_main/system.py`
- Modify: `api/src/modules/rag_v2/document_resolver.py`
- Modify: `api/src/app/services/knowledge_document_service.py`
- Modify: `api/src/app/deepsearch_importer.py`
- Modify: `api/src/app/services/deepsearch_service.py`
- Modify: `api/src/app/services/course_knowledge_builder.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `api/src/app/schemas/course.py`
- Create: `api/src/tests/test_rag_access_scopes.py`
- Modify: `api/src/tests/chat/test_deepsearch_importer.py`
- Modify: `api/src/tests/chat/test_course_scope_routes.py`

- [ ] Write cross-account tests for `personal:<user_id>` and membership-based tests for `course:<course_id>`.
- [ ] Extend import/index metadata with `access_scope`, `library_type`, `course_id` and nullable `owner_user_id`.
- [ ] Keep user uploads and deep research in the personal scope.
- [ ] Make system course building write directly to the course scope, independent of the triggering teacher.
- [ ] Make explicit personal-to-course promotion create a new course-scope index instead of sharing a personal source key.
- [ ] Retain compatibility lookup for historical `user_<owner>:<path>` entries, but stop creating that shape for new course documents.
- [ ] Remove frontend path-based classification once backend fields are available; retain a temporary migration fallback only.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_rag_access_scopes.py tests/chat/test_deepsearch_importer.py tests/chat/test_course_scope_routes.py -q
```

**Gate:** zero personal/course leakage in list, retrieval, content and media APIs.

---

## Task 3: Introduce the lightweight ContentBlock intermediate model

**Files:**

- Create: `api/src/app/services/knowledge_ingestion/__init__.py`
- Create: `api/src/app/services/knowledge_ingestion/models.py`
- Create: `api/src/app/services/knowledge_ingestion/manifest_store.py`
- Create: `api/src/app/services/knowledge_ingestion/markdown_parser.py`
- Create: `api/src/app/services/knowledge_ingestion/html_parser.py`
- Create: `api/src/app/services/knowledge_ingestion/docx_parser.py`
- Create: `api/src/app/services/knowledge_ingestion/mineru_adapter.py`
- Create: `api/src/app/services/knowledge_ingestion/text_parser.py`
- Create: `api/src/tests/knowledge_ingestion/fixtures/`
- Create: `api/src/tests/knowledge_ingestion/test_content_block_parsers.py`

- [ ] Define immutable block, asset, provenance and source-span models.
- [ ] Parse Markdown through an AST and preserve headings, lists, fenced code, math, tables, images and callouts.
- [ ] Parse cleaned HTML DOM while removing navigation, scripts and decorative elements.
- [ ] Parse DOCX headings, paragraphs, tables and embedded images without flattening them into one string.
- [ ] Convert MinerU Markdown/image mapping/page metadata into the same block model.
- [ ] Reject legacy `.doc` with a stable conversion-required error; do not read binary bytes as text.
- [ ] Persist a versioned JSON manifest beside the source file, with asset paths rather than base64 payloads.
- [ ] Add round-trip tests showing that display Markdown preserves formulas, tables, code and asset references.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/knowledge_ingestion/test_content_block_parsers.py -q
```

**Gate:** every supported format produces ordered blocks, stable IDs, headings, source spans and valid asset references.

---

## Task 4: Implement structure-protected parent-child chunking

**Files:**

- Create: `api/src/app/services/knowledge_ingestion/token_counter.py`
- Create: `api/src/app/services/knowledge_ingestion/structural_chunker.py`
- Create: `api/src/app/services/knowledge_ingestion/chunk_models.py`
- Create: `api/src/tests/knowledge_ingestion/test_structural_chunker.py`
- Modify: `api/src/modules/rag_v2/rag_main/system.py`

- [ ] Write tests for target/hard token caps, tiny sibling merging, heading boundaries and adjacency links.
- [ ] Write invariant tests proving short code blocks, formulas, tables, images with captions and callouts are not split internally.
- [ ] Implement long-code splitting by function/class boundaries and long-table splitting with repeated headers.
- [ ] Produce parent chunks and child chunks with `parent_id`, `previous_id`, `next_id`, `heading_path` and source spans.
- [ ] Generate separate `embedding_text` and `display_content`.
- [ ] Remove all silent `[:1500]` embedding truncation. Oversized input must fail before network I/O or be structurally re-split.
- [ ] Store token count and embedding input hash.
- [ ] Keep the old splitter behind a temporary version flag only for rollback; new staging builds use the structural chunker.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/knowledge_ingestion/test_structural_chunker.py tests/chat/test_rag_v2_runtime_import.py -q
```

**Gate:** zero broken fenced blocks/formulas/tables across fixtures and zero embedding truncation.

---

## Task 5: Add bounded-memory multimodal ingestion

**Files:**

- Create: `api/src/app/services/knowledge_ingestion/asset_pipeline.py`
- Create: `api/src/app/services/knowledge_ingestion/video_segmenter.py`
- Modify: `api/src/modules/rag_v2/rag_main/system.py`
- Modify: `api/src/modules/rag_v2/rag_main/api.py`
- Modify: `api/src/core/config.py`
- Create: `api/src/tests/knowledge_ingestion/test_asset_pipeline.py`
- Create: `api/src/tests/knowledge_ingestion/test_video_segmenter.py`
- Create: `api/src/tests/knowledge_ingestion/test_ingestion_memory_bounds.py`

- [ ] Localize approved source images into document-owned asset directories and rewrite references to stable asset IDs.
- [ ] Reject path traversal, unsupported MIME, oversized downloads and executable SVG; convert approved SVG to a safe bitmap if conversion support exists.
- [ ] Filter decorative images and icons before embedding.
- [ ] Generate an image vector plus caption/nearby-text representation for each instructional image.
- [ ] Segment video by captions/scenes when available; use bounded 30–80 second fallback windows with keyframes and timecodes.
- [ ] Use direct Gemini video embedding only when the configured gateway confirms support; otherwise index transcript and keyframes and record the fallback.
- [ ] Stream embedding batches and immediately upsert results; do not retain all images or vectors in memory.
- [ ] Add a synthetic large-document memory test and an operational benchmark that records peak RSS on the target machine.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/knowledge_ingestion/test_asset_pipeline.py tests/knowledge_ingestion/test_video_segmenter.py tests/knowledge_ingestion/test_ingestion_memory_bounds.py -q
```

**Gate:** real image vectors are present; failures are explicit; no OOM under the agreed fixture/target-machine benchmark.

---

## Task 6: Replace early source dedup and score mixing with a staged retriever

**Files:**

- Create: `api/src/modules/rag_v2/retrieval/candidates.py`
- Create: `api/src/modules/rag_v2/retrieval/rrf.py`
- Create: `api/src/modules/rag_v2/retrieval/context_expander.py`
- Create: `api/src/modules/rag_v2/retrieval/pipeline.py`
- Modify: `api/src/modules/rag_v2/rag_main/system.py`
- Modify: `api/src/app/services/knowledge_document_service.py`
- Create: `api/src/tests/retrieval/test_rrf.py`
- Create: `api/src/tests/retrieval/test_retrieval_pipeline.py`
- Create: `api/src/tests/retrieval/test_context_expansion.py`

- [ ] Write a regression test where two relevant chunks from one document must both reach reranking.
- [ ] Retrieve 30–50 dense and BM25 candidates under access-scope and knowledge-node filters.
- [ ] Keep original query retrieval even when query rewrite is enabled; add rewritten query as another recall route.
- [ ] Fuse routes with deterministic RRF and retain representation provenance.
- [ ] Rerank the fused candidate set, then apply per-document diversity caps.
- [ ] Expand selected children to parents and neighbors within a configurable context budget.
- [ ] Calibrate thresholds through the evaluation set rather than fixed distance constants.
- [ ] Make `test_retrieval` call the production retrieval pipeline and return stage-level evidence.
- [ ] Preserve clear degradation when BM25 or reranker is unavailable.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/retrieval tests/test_rag_document_lifecycle.py -q
```

**Gate:** no pre-rerank source dedup, real pipeline test endpoint, deterministic filters/fusion/expansion.

---

## Task 7: Build an executable retrieval evaluation harness

**Files:**

- Create: `api/src/app/services/knowledge_quality/evaluation_models.py`
- Create: `api/src/app/services/knowledge_quality/retrieval_evaluator.py`
- Create: `api/src/scripts/evaluate_course_retrieval.py`
- Create: `api/src/tests/knowledge_quality/test_retrieval_evaluator.py`
- Create: `api/course_data/evaluations/computational-thinking/README.md`
- Create: `api/course_data/evaluations/computational-thinking/gold-queries.jsonl`

- [ ] Define versioned gold records with question type, target node, relevant documents/chunks/assets and acceptable evidence.
- [ ] Seed at least five queries per approved leaf node before final release; early development may begin with a representative subset.
- [ ] Compute Recall@5/10, MRR@10, node hit@5, modality hit@10, latency and scope leakage.
- [ ] Support A/B runs for old splitter, structural child retrieval, parent expansion and multimodal retrieval.
- [ ] Save configuration and metrics without API keys or private content.
- [ ] Fail the release command when mandatory thresholds regress.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/knowledge_quality/test_retrieval_evaluator.py -q
D:\anaconda\envs\edu-ai\python.exe -m app.scripts.evaluate_course_retrieval --course-id computational-thinking --build-id staging
```

**Gate:** baseline and candidate results are reproducible; candidate never silently underperforms baseline.

---

## Phase 1 Completion Gate

Do not collect and rebuild the full curriculum corpus until Tasks 1–7 satisfy:

- stable access scopes;
- structure-preserving parsing and chunking;
- zero silent embedding truncation;
- real image indexing;
- staged retrieval with RRF and reranking;
- production-equivalent evaluation;
- bounded-memory evidence.

---

## Task 8: Introduce knowledge graph schema v2 and curriculum validation

**Files:**

- Modify: `api/src/app/schemas/course.py`
- Modify: `api/src/core/course_storage.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `src/stitch/api/types.ts`
- Create: `api/src/app/services/course_graph/graph_models.py`
- Create: `api/src/app/services/course_graph/graph_validator.py`
- Create: `api/src/app/services/course_graph/computational_thinking_blueprint.py`
- Create: `api/src/tests/course_graph/test_graph_validator.py`
- Create: `api/src/tests/course_graph/test_computational_thinking_blueprint.py`

- [ ] Define stable nodes, aliases, objectives, assessment evidence and typed semantic edges.
- [ ] Encode the approved 10-module computational-thinking blueprint with approximately 45–50 atomic leaves.
- [ ] Validate stable unique IDs, normalized duplicate names/aliases, cycles, invalid edges, empty objectives and noncurricular markers.
- [ ] Keep `root.children` backward-compatible for the current tree UI while storing v2 nodes and edges.
- [ ] Produce a coverage matrix mapping each curriculum node to candidate sources before any documents are published.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/course_graph -q
```

**Gate:** no foreword/preface/reference/paper-book nodes, no duplicate leaves, all leaves have objectives and evidence definitions.

---

## Task 9: Build governed source acquisition and provenance

**Files:**

- Refactor: `api/src/app/services/course_knowledge_builder.py`
- Create: `api/src/app/services/course_sources/models.py`
- Create: `api/src/app/services/course_sources/registry.py`
- Create: `api/src/app/services/course_sources/license_policy.py`
- Create: `api/src/app/services/course_sources/fetcher.py`
- Create: `api/src/app/services/course_sources/media_localizer.py`
- Create: `api/src/tests/course_sources/test_license_policy.py`
- Create: `api/src/tests/course_sources/test_fetcher_security.py`
- Create: `api/src/tests/course_sources/test_provenance.py`

- [ ] Define reviewed source records for Chinese open textbooks, official documentation, university/OER material and permitted English supplements.
- [ ] Enforce allowlisted hosts, robots policy, redirect/size/MIME limits and explicit licensing evidence.
- [ ] Reject AI-ingestion denial markers and unknown licenses.
- [ ] Download source media with provenance and stable content hashes.
- [ ] Preserve title, institution/author, URL, revision, retrieved time, language, license and usage restriction.
- [ ] Map source sections to curriculum nodes; never generate graph nodes directly from book navigation.
- [ ] Make source fetching resumable and idempotent.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/course_sources -q
```

**Gate:** every external document and asset is attributable, permitted and mapped to an approved curriculum leaf.

---

## Task 10: Add teaching-document quality gates and controlled authoring

**Files:**

- Create: `api/src/app/services/knowledge_quality/document_quality.py`
- Create: `api/src/app/services/knowledge_quality/coverage_matrix.py`
- Create: `api/src/app/services/course_authoring/templates.py`
- Create: `api/src/app/services/course_authoring/service.py`
- Create: `api/src/tests/knowledge_quality/test_document_quality.py`
- Create: `api/src/tests/knowledge_quality/test_coverage_matrix.py`
- Create: `api/src/tests/course_authoring/test_course_authoring.py`

- [ ] Implement hard failures for empty/short shell content, duplicate content, missing provenance, malformed formulas, broken media and prohibited book matter.
- [ ] Score but do not automatically approve examples, explanations, misconceptions, exercises, answers, code execution and visual evidence.
- [ ] Require at least three accepted documents per leaf and at least two Chinese documents.
- [ ] Use reviewed external materials first; use controlled original authoring only for uncovered document roles or inadequate quality.
- [ ] Generate separate concept, case/lab and exercise/assessment documents, not three paraphrases of the same text.
- [ ] Mark original materials clearly and attach reviewed reference evidence.
- [ ] Produce reviewer queues for borderline content and a machine-readable coverage report.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/knowledge_quality/test_document_quality.py tests/knowledge_quality/test_coverage_matrix.py tests/course_authoring/test_course_authoring.py -q
```

**Gate:** 100% leaf coverage and no document counted merely because it exists or exceeds a length threshold.

---

## Task 11: Finish secure, readable document and media preview

**Files:**

- Modify: `api/src/app/api/courses.py`
- Modify: `src/stitch/components/MarkdownPreview.tsx`
- Modify: `src/stitch/components/knowledgeMarkdown.ts`
- Modify: `src/stitch/course/knowledge/KnowledgeDocumentPreviewDialog.tsx`
- Modify: `src/stitch/course/knowledge/KnowledgeDocumentsView.tsx`
- Modify: `src/stitch/course/knowledge/KnowledgeStructureView.tsx`
- Modify: `src/components/teacher/SourcePanel.tsx`
- Create: `src/stitch/components/__tests__/knowledgeMarkdown.test.ts`
- Create: `api/src/tests/chat/test_course_knowledge_media.py`

- [ ] Test stable document-ID preview from both course knowledge pages and the Q&A source panel.
- [ ] Render GFM tables, fenced code, KaTeX math, known callouts and captions without enabling untrusted raw HTML.
- [ ] Resolve course and personal media through separate authorized endpoints.
- [ ] Add image fallback, video timecode links and readable display titles.
- [ ] Verify direct media URLs cannot cross course or user boundaries.
- [ ] Add keyboard and responsive preview tests.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/chat/test_course_knowledge_media.py tests/chat/test_course_scope_routes.py -q
npm run test -- --run
npm run build
```

**Gate:** representative formula/table/image/video documents are readable in both knowledge-base and Q&A views.

---

## Task 12: Implement staged build, atomic activation and rollback

**Files:**

- Create: `api/src/app/services/course_builds/models.py`
- Create: `api/src/app/services/course_builds/store.py`
- Create: `api/src/app/services/course_builds/orchestrator.py`
- Create: `api/src/app/services/course_builds/activation.py`
- Modify: `api/src/app/services/generation_task_handlers.py`
- Modify: `api/src/app/api/courses.py`
- Create: `api/src/scripts/build_course_knowledge_base.py`
- Create: `api/src/scripts/activate_course_knowledge_build.py`
- Create: `api/src/tests/course_builds/test_atomic_activation.py`
- Create: `api/src/tests/course_builds/test_build_resume.py`

- [ ] Write failure-injection tests for source acquisition, parsing, embedding, graph save, quality evaluation and pointer activation.
- [ ] Build all files and vectors under a staging build ID.
- [ ] Record source, parser, chunker, embedding, graph and retrieval configuration versions.
- [ ] Resume from the last durable stage without duplicating documents or vectors.
- [ ] Activate only after graph, coverage, media, index and retrieval gates pass.
- [ ] Keep the previous active pointer and provide a tested rollback command.
- [ ] Make cleanup of expired builds a separate explicit command.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/course_builds -q
```

**Gate:** injected failure leaves the old course library fully usable; successful activation switches graph/documents/vectors as one version.

---

## Task 13: Build the complete computational-thinking corpus in staging

**Files:**

- Create/update under: `api/course_data/courses/computational-thinking/knowledge_base/builds/<build_id>/`
- Create: `docs/qa/computational-thinking-source-manifest-<build_id>.md`
- Create: `docs/qa/computational-thinking-quality-report-<build_id>.md`
- Create: `docs/qa/computational-thinking-retrieval-report-<build_id>.md`

- [ ] Freeze the approved graph blueprint.
- [ ] Acquire and review Chinese-first source material.
- [ ] Localize permitted figures/tables/media and verify hashes.
- [ ] Map materials to leaves and run deduplication.
- [ ] Author missing concept/case/exercise roles.
- [ ] Run document quality and coverage gates.
- [ ] Parse, chunk and multimodally index the staging corpus.
- [ ] Complete at least five gold queries per leaf and run retrieval evaluation.
- [ ] Manually review at least 10 knowledge points, 20 formulas, 10 tables and 20 images.
- [ ] Confirm that no foreword, preface, references directory or paper-book information appears.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m app.scripts.build_course_knowledge_base --course-id computational-thinking --staging
D:\anaconda\envs\edu-ai\python.exe -m app.scripts.evaluate_course_retrieval --course-id computational-thinking --build-id <build_id>
```

**Gate:** all SPEC thresholds pass before activation is offered.

---

## Task 14: Activate, verify and retire the old generated corpus

**Files:**

- Update: `docs/qa/computational-thinking-release-acceptance-<build_id>.md`
- Update: `docs/DEVELOPMENT_HANDOVER.md`

- [ ] Back up the active graph/index pointers.
- [ ] Activate the approved staging build atomically.
- [ ] Verify course document count, graph coverage, personal/course counts and media availability through real APIs.
- [ ] Run a browser acceptance pass for course knowledge, graph, Q&A selection and preview.
- [ ] Run the production-equivalent retrieval suite after activation.
- [ ] Verify teacher A/B, course member and course outsider boundaries.
- [ ] Remove old generated corpus only after the rollback window and only through an explicit cleanup command; never delete user uploads or `api/data/`.
- [ ] Record recovery commands and final evidence.

```powershell
D:\anaconda\envs\edu-ai\python.exe -m app.scripts.activate_course_knowledge_build --course-id computational-thinking --build-id <build_id>
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/knowledge_ingestion tests/retrieval tests/knowledge_quality tests/course_graph tests/course_sources tests/course_builds -q
npm run build
```

---

## Final Completion Gate

Do not mark the goal complete until all of the following have evidence:

- user uploads and deep research remain personal by default;
- system course-building documents exist only in the course scope;
- the approved curriculum graph has no duplicate or book-only nodes;
- every leaf has at least three accepted documents and two Chinese documents;
- sources, licenses, versions and original authorship are traceable;
- formulas, tables, code, images and video survive parsing, indexing and preview;
- no embedding input is silently truncated;
- dense + BM25 + RRF + reranker + parent expansion is the production path;
- Recall@10, MRR@10, node hit rate, modality hit rate and latency meet the SPEC thresholds;
- cross-user and cross-course leakage is zero;
- a large textbook build completes without OOM;
- active build activation and rollback are tested;
- old generated placeholders are removed without touching user-owned data;
- frontend production build, backend focused suites and manual acceptance all pass.
