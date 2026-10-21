"""Provider capabilities, distinct from task quotas or content-length targets.

Official DeepSeek V4/Flash limits verified 2026-10-13:
https://api-docs.deepseek.com/quick_start/pricing/
model_capacity retains historical compatibility defaults for bounded callers.
Production uses provider_output_limit and does not enforce those input estimates.
"""
from urllib.parse import urlparse


def model_capacity(gateway):
    from app.services.deepseek_key_failover import upstream_base_url
    capacities = []
    for candidate in getattr(gateway, 'candidates', ()):
        model = str(candidate.get('model_name', ''))
        official = urlparse(upstream_base_url(candidate.get('api_base', ''))).hostname == 'api.deepseek.com'
        if official and (model.startswith('deepseek-v4-') or model == 'deepseek-flash'):
            capacities.append((1_000_000, 384_000))
        else:
            capacities.append((128_000, 12_000))
    return tuple(min(values) for values in zip(*capacities)) if capacities else (128_000, 12_000)


def provider_output_limit(candidate):
    """Known provider capacity, or None to let the provider choose its default."""
    from app.services.deepseek_key_failover import upstream_base_url
    model = str(candidate.get('model_name', ''))
    official = urlparse(upstream_base_url(candidate.get('api_base', ''))).hostname == 'api.deepseek.com'
    return 384_000 if official and (model.startswith('deepseek-v4-') or model == 'deepseek-flash') else None
