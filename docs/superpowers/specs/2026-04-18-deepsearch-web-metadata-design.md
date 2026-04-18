# DeepSearch Web Metadata Design

## Goal

Make deep-search imported web documents readable and recognizable in the knowledge base.

After this change:
- web document display names use `site_name + full-width bar + page_title`
- web documents carry a site logo URL based on favicon discovery
- the teacher knowledge-base list shows the site logo for web documents and falls back safely when unavailable

## Scope

This change is limited to deep-search web ingestion metadata and teacher-side knowledge-base display.

In scope:
- generate stable web display names during deep-search ingestion
- derive `source_site_name` from page metadata or URL
- derive `source_logo_url` from favicon-related metadata or a deterministic fallback
- persist the new fields into RAG document metadata
- expose the new fields through document list APIs
- render web logos in the teacher source panel with graceful fallback
- add regression tests for metadata generation and UI fallback behavior

Out of scope:
- downloading and caching favicon files locally
- extracting page-body brand images instead of site favicon
- backfilling previously imported web documents
- redesigning the entire knowledge-base list UI

## Current Problem

Deep-search web imports currently produce file names such as `web_<domain>_<title>_<hash>.md`. These names are useful for storage uniqueness but poor for human scanning in the knowledge base.

The backend already stores `source_url`, `source_title`, `source_domain`, and `doc_kind = "web"`, but there is no dedicated site-name field and no logo field. The teacher source panel therefore falls back to generic web labeling and cannot show a recognizable site identity.

## Approach

Use backend-owned metadata generation during deep-search ingestion, then let the frontend render directly from those normalized fields.

Recommended metadata shape for web documents:
- `file_name`: `site_name + full-width bar + page_title`
- `source_site_name`: normalized site name for display
- `source_logo_url`: resolved favicon URL
- keep existing `source_url`, `source_title`, `source_domain`, `doc_kind`

This keeps storage, API output, and UI display consistent across entry points that consume RAG document metadata.

## Metadata Rules

### Site Name

Derive the site name in this order:
1. cleaned metadata field that represents `og:site_name` or equivalent page-level site metadata
2. a meaningful title split heuristic when the page title contains common separators such as `-`, `|`, or `_`
3. normalized hostname fallback derived from the URL

Normalization rules:
- trim whitespace
- collapse repeated spaces
- keep human-readable Unicode text
- avoid storage-unsafe filename characters when writing `file_name`

### Display Name

Use:
- `site_name + full-width bar + page_title` when both values exist and are not duplicates
- `site_name` when the page title is empty or redundant
- `page_title` when site name extraction fails
- hostname fallback only when neither site name nor title is usable

This display name is written into document metadata as `file_name`. Physical filenames on disk may remain storage-oriented and unique.

The exact separator is the full-width vertical bar character used for Chinese UI display.

### Logo URL

Treat the website logo as favicon, not as an arbitrary image from the page body.

Resolve in this order:
1. `<link rel="icon">`
2. `<link rel="shortcut icon">`
3. `<link rel="apple-touch-icon">`
4. `https://<host>/favicon.ico`

If the extracted icon path is relative, resolve it against the page URL.

If backend extraction fails, still persist the document without `source_logo_url`. The frontend must then fall back to a generic web icon.

## Architecture

### Backend Ingestion

Add a shared helper in the deep-search ingestion path that:
- inspects crawl result metadata and source URL
- derives site name
- derives display name
- derives favicon URL
- returns a normalized metadata payload for web documents

Apply the helper in both:
- `Edu_AI/api/Edu_AI/app/deepsearch.py`
- `Edu_AI/api/Edu_AI/app/deepsearch_pipeline.py`

Both code paths should produce identical web metadata so that direct API usage and tool-driven deep-search imports stay aligned.

### Metadata Extraction Source

The existing crawl pipeline already carries `result.metadata`, but it may not always preserve raw HTML head tags. The implementation should therefore use a two-tier strategy:
- if structured icon metadata is available in `result.metadata`, use it
- otherwise synthesize the deterministic `/favicon.ico` fallback from the source URL without blocking ingestion

This removes any dependency on storing full HTML just to support the initial version of the feature.

### API Surface

Extend the RAG document response models and serialization so list/detail responses include:
- `source_site_name`
- `source_logo_url`

Existing consumers remain backward-compatible because the new fields are additive.

### Frontend Rendering

Update `Edu_AI/src/components/teacher/SourcePanel.tsx` so web documents:
- prefer `source_logo_url` for the list icon
- fall back to `GlobalOutlined` on load failure or missing URL
- prefer the backend-provided `file_name`
- retain the existing source-title/domain fallback only for older documents without new metadata

## Data Flow

1. deep-search finds URLs
2. crawler fetches page content
3. cleaning step produces content plus metadata
4. ingestion helper derives normalized web metadata
5. RAG import writes the file and persists metadata into the document index
6. list-documents API returns the enriched metadata
7. teacher source panel renders `file_name` and `source_logo_url`

## Error Handling

- Missing title: fall back to site name or hostname
- Missing site metadata: fall back to hostname
- Missing favicon metadata: fall back to `/favicon.ico`
- Invalid favicon URL or broken image response: frontend falls back to `GlobalOutlined`
- PDF imports from deep-search remain unchanged and do not receive web-logo treatment unless they originate from web metadata that can safely support it later

The ingestion flow must not fail solely because site-name or logo extraction fails.

## Testing

Add backend tests that prove:
- a web import record gets `file_name = site_name + full-width bar + page_title`
- `source_site_name` is persisted when site metadata exists
- `source_logo_url` falls back to `/favicon.ico` when explicit icon metadata is absent
- duplicate site name and page title do not create noisy display names

Add frontend tests or pure-function tests that prove:
- web documents prefer `source_logo_url`
- missing or broken logos fall back to the generic web icon
- old web documents without the new fields still render readable labels

## Risks

- Some crawled pages may not expose structured head metadata, so site-name quality will vary
- Title-splitting heuristics can misidentify the site name for unusual page titles
- External favicon URLs may be blocked, missing, or slow, so frontend fallback must remain reliable

## Decision Summary

Use backend-owned web metadata normalization with favicon-based logo extraction and frontend fallback rendering. This keeps the feature lightweight, deterministic, and compatible with the current deep-search ingestion architecture.
