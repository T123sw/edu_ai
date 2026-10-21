"""Package authorized, already-localized product assets into native projects."""
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .projects import digest_bytes


def selected_media(snapshot, *, owner):
    files, selected, rejected = {}, [], []
    for item in snapshot.get('selected', []):
        try:
            parsed = urlsplit(item['local_url'])
            if parsed.path.startswith('/api/images/searched/'):
                from app.api.searched_images import _resolve_safe_path
                path = _resolve_safe_path(parsed.path.removeprefix('/api/images/searched/'))
            elif parsed.path in ('/api/rag/image', '/api/rag/media'):
                from modules.rag_v2.rag_main.api import _guarded_storage_file_response
                response = _guarded_storage_file_response(parse_qs(parsed.query)['path'][0], {'username': owner})
                path = Path(response.path)
            else:
                raise ValueError('Unsupported localized asset')
            if path is None or not path.is_file(): raise ValueError('Localized asset is missing')
            if path.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.gif','.svg','.mp4','.webm','.mp3','.wav','.ogg','.m4a'}:
                raise ValueError('Unsupported media type')
            body = path.read_bytes()
            name = 'assets/media/' + digest_bytes(body) + path.suffix.lower()
            files[name] = body
            selected.append({**item, 'local_url': name})
        except Exception:
            # Optional retrieval must not authorize arbitrary files or silently
            # claim unavailable images were incorporated into the project.
            rejected.append({'slot_id': item.get('slot_id'), 'reason': 'unavailable_or_unauthorized'})
    return files, {**snapshot, 'selected': selected, 'packaging_rejected': rejected}
