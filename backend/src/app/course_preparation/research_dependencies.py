"""Configured infrastructure. No schema creation or secrets in task checkpoints."""
import os
from functools import lru_cache

from sqlalchemy import create_engine, inspect

from .research_repository import ResearchRepository
from .research_runtime import ResearchRuntime


def enabled():
    return os.getenv('COURSE_RESEARCH_ENABLED', '').lower() in ('1', 'true', 'yes')


@lru_cache(maxsize=1)
def repository():
    url = os.getenv('DATABASE_URL', '').strip()
    if not url:
        raise RuntimeError('DATABASE_URL is required')
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name != 'postgresql':
        engine.dispose()
        raise RuntimeError('course research requires PostgreSQL')
    if not inspect(engine).has_table('course_research_runs'):
        engine.dispose()
        raise RuntimeError('apply migration 20260917_0025 before enabling course research')
    return ResearchRepository(engine)


def snapshot(username):
    from app.services.runtime_config_resolver import runtime_config_resolver
    return runtime_config_resolver.capture_snapshot(username)


def agent_factory(username, snapshot):
    from app.chat.model_gateway import ChatModelGateway
    from app.services.runtime_config_resolver import runtime_config_resolver
    from .harness_adapter import HarnessPreparationAdapter
    from .research_agent import ResearchAgent
    from .research_sources import ResearchSources
    config = runtime_config_resolver.resolve('llm', owner_user_id=username, snapshot=snapshot)
    if snapshot.get('llm') and config.get('_revision_id') != snapshot['llm'].split(':', 1)[1]:
        from .research_agent import ResearchError
        raise ResearchError('CONFIG_REVISION_UNAVAILABLE', '任务绑定的模型配置已不可用')
    gateway = ChatModelGateway(api_base=config['base_url'], api_key=config.get('api_key'), model_name=config['model'])
    from .model_capacity import model_capacity
    return ResearchAgent(model=HarnessPreparationAdapter(gateway, context_tokens=model_capacity(gateway)[0]), sources=ResearchSources(
        tavily_key=os.getenv('TAVILY_API_KEY', ''), bocha_key=os.getenv('BOCHA_API_KEY', ''),
        tavily_base=os.getenv('TAVILY_BASE_URL', 'https://api.tavily.com')))


def build_runtime():
    return ResearchRuntime(repository(), agent_factory) if enabled() else None
