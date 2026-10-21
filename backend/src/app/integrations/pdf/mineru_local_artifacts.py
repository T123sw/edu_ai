"""Normalize the self-contained MinerU 4.x bundle without inventing pages."""
import base64
import io
import json
import re
import zipfile
from pathlib import PurePosixPath
from urllib.parse import unquote

from .base import ParsedPdf, PdfParseError

_IMAGE_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.webp': 'image/webp', '.gif': 'image/gif'}
_MAX_BUNDLE_BYTES = 256 * 1024 * 1024


def _pages(document):
    pages = document.get('pages') if isinstance(document, dict) else None
    if not isinstance(pages, list) or not pages:
        raise PdfParseError('MinerU local missing page evidence')
    indices = [p.get('page_idx') if isinstance(p, dict) else None for p in pages]
    if any(type(i) is not int or i < 0 for i in indices) or len(set(indices)) != len(indices):
        raise PdfParseError('MinerU local invalid page evidence')
    return pages, sorted(indices)


def parse_bundle(data):
    try:
        return _parse_bundle(data)
    except (zipfile.BadZipFile, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise PdfParseError('MinerU local invalid artifact bundle') from exc


def _parse_bundle(data):
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        entries = bundle.infolist()
        if sum(i.file_size for i in entries) > _MAX_BUNDLE_BYTES or len(entries) > 20000:
            raise PdfParseError('MinerU local artifact bundle too large')
        names = [i.filename for i in entries if not i.is_dir()]
        if len(names) != len(set(names)) or any(
            PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n for n in names
        ):
            raise PdfParseError('MinerU local invalid artifact path')
        markdown = bundle.read('markdown.md').decode('utf-8')
        middle = json.loads(bundle.read('middle_json.json'))
        structured = json.loads(bundle.read('structured_content.json'))
        _, indices = _pages(middle)
        pages, structured_indices = _pages(structured)
        if indices != structured_indices:
            raise PdfParseError('MinerU local inconsistent page evidence')
        document = middle.get('metadata', {}).get('document', {})
        count = document.get('page_count')
        if count is None:
            count = max(indices) + 1  # Evidence remains sparse; callers check coverage.
        if type(count) is not int or count <= max(indices):
            raise PdfParseError('MinerU local invalid page count')
        mapping, paths = {}, {}
        for name in names:
            suffix = PurePosixPath(name).suffix.lower()
            if suffix not in _IMAGE_TYPES:
                continue
            basename = PurePosixPath(name).name
            payload = 'data:' + _IMAGE_TYPES[suffix] + ';base64,' + base64.b64encode(bundle.read(name)).decode()
            if basename in mapping and mapping[basename] != payload:
                raise PdfParseError('MinerU local ambiguous image basename')
            mapping[basename] = payload
            paths[name] = basename

        def image_path(source):
            path = unquote(source).removeprefix('./')
            if path not in paths:
                raise PdfParseError('MinerU local referenced image is missing')
            return 'images/' + paths[path]

        def rewrite_markdown(value):
            # The server emits local Markdown assets. Do not retrieve arbitrary URLs.
            return re.sub(r'(!\[[^\]]*\]\()([^\s)]+)(\))',
                          lambda m: m[1] + image_path(m[2]) + m[3], value)

        markdown = rewrite_markdown(markdown)
        if not markdown.strip():
            raise PdfParseError('MinerU local empty markdown')
        layout, formulas, tables = [], [], []
        for page in pages:
            blocks = page.get('blocks')
            if not isinstance(blocks, list):
                raise PdfParseError('MinerU local missing page blocks')
            for block in blocks:
                if not isinstance(block, dict) or not isinstance(block.get('content'), str):
                    raise PdfParseError('MinerU local invalid layout block')
                text = rewrite_markdown(block['content'])
                item = {**block, 'page_idx': page['page_idx'], 'text': text, 'content': text}
                source = block.get('image_source')
                if source:
                    item['img_path'] = image_path(source)
                    item['image_source'] = item['img_path']
                kind = block.get('type')
                if kind in ('image', 'chart'):
                    item['type'] = 'image'
                    item['image_caption'] = [c.get('content', '') for c in block.get('captions', [])]
                elif kind in ('equation', 'formula'):
                    formulas.append({'latex': block['content'], 'page': page['page_idx']})
                elif kind == 'table':
                    item['table_body'] = text
                    item['table_caption'] = [c.get('content', '') for c in block.get('captions', [])]
                    tables.append({'page': page['page_idx'], 'caption': item['table_caption'], 'html': text})
                layout.append(item)
        return ParsedPdf(text=markdown, images=list(mapping.values()), tables=tables, formulas=formulas,
                         metadata={'pageCount': count, 'pageIndices': indices, 'layout': layout,
                                   'imageMapping': mapping, 'failed_units': 0,
                                   'parserVersion': middle.get('metadata', {}).get('producer', {}).get('version')})
