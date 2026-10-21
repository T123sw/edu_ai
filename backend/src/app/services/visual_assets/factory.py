"""Shared image retrieval for resource types that still support visuals."""
from .pipeline import VisualAssetPipeline


def build_default_visual_pipeline():
    from app.chat.runtime.agent_tools.handlers.providers import build_default_image_search_provider

    def knowledge_search(*, query, selected_document_ids, owner, **_kwargs):
        from app.chat.application.knowledge_base_summary_provider import KnowledgeBaseSummaryProvider
        from app.chat.workflows.report.media_assets import extract_image_assets
        sources = KnowledgeBaseSummaryProvider().get_document_image_sources(
            selected_doc_ids=list(selected_document_ids), owner=owner, query_text=query, top_k=8)
        return extract_image_assets(list(sources or []))

    provider = build_default_image_search_provider()

    def web_search(*, query, kind, owner, **_kwargs):
        if provider is None:
            return []
        return provider.search(query=query, count=6, style=kind, safe=True, license_='any', owner=owner)

    return VisualAssetPipeline(knowledge_search=knowledge_search, web_search=web_search)
