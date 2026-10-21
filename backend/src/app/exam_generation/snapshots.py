"""Freeze resolved configuration encrypted, including environment defaults."""
from app.services.runtime_config_resolver import runtime_config_resolver


class SnapshotCodec:
    def __init__(self, resolver=None):
        self.resolver = resolver or runtime_config_resolver

    def capture(self, owner):
        revisions = self.resolver.capture_snapshot(owner)
        values = {name: self.resolver.resolve(name, owner_user_id=owner, snapshot=revisions)
                  for name in ('llm', 'pdf_parser')}
        llm = values['llm']
        if not llm.get('model') or not llm.get('base_url'):
            raise ValueError('请先配置可用的生成模型')
        # Match Edu_AI's existing generation model policy, without altering
        # the upstream Explore/Plan/Quiz stages or their iteration budgets.
        from app.chat.agents.report_generation import _thinking_extra_body
        thinking = _thinking_extra_body(str(llm['model']))
        llm['reasoning_effort'] = 'none' if thinking else None
        llm['binding'] = 'deepseek' if str(llm['model']).lower().startswith('deepseek') else 'openai'
        # Freeze the existing visual provider for scanned figures. It is used
        # by the same generation engine, never for indexing or a second parser.
        from core.config import Config
        if Config.VISION_MODEL_ID and Config.QWEN_BASE_URL:
            values['vision_llm'] = {'model': Config.VISION_MODEL_ID,
                'base_url': Config.QWEN_BASE_URL,
                'api_key': Config.resolve_llm_api_key(Config.QWEN_BASE_URL, Config.QWEN_API_KEY),
                'binding': 'openai', 'supports_vision': True,
                'reasoning_effort': 'none' if _thinking_extra_body(Config.VISION_MODEL_ID) else None}
        # Parser's environment defaults must also be frozen before queueing.
        from app.integrations.pdf.configuration import resolve_pdf_config
        values['pdf_parser'] = resolve_pdf_config(values['pdf_parser'])
        return self.resolver.store._encrypt({'owner': owner, 'providers': values})

    def read(self, owner, encrypted):
        value = self.resolver.store._decrypt(encrypted)
        if value.get('owner') != owner:
            raise PermissionError('MODEL_SNAPSHOT_OWNER_MISMATCH')
        return value['providers']
