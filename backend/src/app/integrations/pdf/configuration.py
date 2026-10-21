"""Resolve parser selection once, then use the same values for jobs and calls."""
import os

from .base import PdfParseError

_ALIASES = {
    'mineru-local': 'mineru-local', 'mineru_local': 'mineru-local', 'local': 'mineru-local',
    'mineru-cloud': 'mineru-cloud', 'mineru_cloud': 'mineru-cloud', 'mineru': 'mineru-cloud',
}


def resolve_pdf_config(resolved):
    values = dict(resolved)
    # Explicit provider selection in a saved profile takes precedence. Older
    # profiles named "custom"/"environment" use the deployment selection.
    selection = str(values.get('provider_id') or values.get('provider_name', '')).strip().lower()
    if selection not in _ALIASES:
        selection = os.getenv('PDF_PARSER_PROVIDER', 'mineru-cloud').strip().lower()
    if selection not in _ALIASES:
        raise PdfParseError('Unknown PDF parser provider')
    provider = _ALIASES[selection]
    local = provider == 'mineru-local'
    environment = values.get('_source', 'environment') == 'environment'
    timeout = (os.getenv('PDF_MINERU_LOCAL_TIMEOUT', '1800') if local else 900)
    if not environment:
        timeout = values.get('timeout_seconds') or timeout
    values.update(
        provider_id=provider,
        base_url=values.get('base_url') or os.getenv(
            'PDF_MINERU_LOCAL_BASE_URL' if local else 'PDF_MINERU_CLOUD_BASE_URL',
            'http://127.0.0.1:8190' if local else 'https://mineru.net/api/v4'),
        api_key=values.get('api_key') or os.getenv(
            'PDF_MINERU_LOCAL_API_KEY' if local else 'PDF_MINERU_CLOUD_API_KEY', ''),
        model=values.get('model') or ('basic' if local else 'vlm'),
        timeout_seconds=float(timeout),
    )
    return values


def create_pdf_parser(config):
    """Construct from a frozen config. Pre-migration exam snapshots were cloud."""
    from .mineru_cloud import MinerUCloudProvider
    from .mineru_local import LocalMinerUProvider
    provider = config.get('provider_id', 'mineru-cloud')
    if provider == 'mineru-local':
        return LocalMinerUProvider(base_url=config['base_url'], api_key=config.get('api_key', ''),
                                   timeout_s=config.get('timeout_seconds', 1800))
    if provider == 'mineru-cloud':
        parser = MinerUCloudProvider(api_key=config.get('api_key', ''), base_url=config['base_url'],
                                     model_version=config.get('model') or 'vlm')
        # An empty frozen key must not pick up a later environment credential.
        parser.api_key = config.get('api_key', '')
        return parser
    raise PdfParseError('Unknown frozen PDF parser provider')
