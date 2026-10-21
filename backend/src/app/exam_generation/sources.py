"""Read exam uploads and parse original files without indexing or retrieval."""
import base64
import hashlib
from pathlib import Path
from app.services.personal_knowledge_service import PersonalKnowledgeNotFound
from .uploads import ExamSourceReader


class GenerationSources:
    def __init__(self, reader=None, parser_factory=None):
        self.reader = reader or ExamSourceReader()
        self.parser_factory = parser_factory

    def _read(self, owner, document_id):
        try:
            return self.reader.read_bytes(owner, document_id)
        except PersonalKnowledgeNotFound:
            raise PermissionError('DOCUMENT_UNAVAILABLE') from None

    def freeze(self, owner, refs):
        result = []
        for ref in refs:
            record, data = self._read(owner, ref['document_id'])
            if ref['role'] == 'template' and Path(record['filename']).suffix.lower() != '.pdf':
                raise ValueError('当前仿卷模板须为 PDF')
            result.append({**ref, 'filename': record['filename'], 'source_hash': hashlib.sha256(data).hexdigest()})
        return result

    def parse(self, owner, refs, config, *, canceled, on_remote_task):
        from app.integrations.pdf.mineru_cloud import ParseControl
        from app.integrations.pdf.configuration import create_pdf_parser
        from app.integrations.pdf.formats import MINERU_SUPPORTED_SUFFIXES
        import io
        from pypdf import PdfReader
        parser = None
        result = []
        for ref in refs:
            ParseControl(canceled=canceled).check()
            record, data = self._read(owner, ref['document_id'])
            if hashlib.sha256(data).hexdigest() != ref['source_hash']:
                raise PermissionError('SOURCE_VERSION_CHANGED')
            suffix = Path(ref['filename']).suffix.lower()
            images, layout = {}, []
            if suffix in {'.txt', '.md', '.markdown'}:
                content, parser_name = data.decode('utf-8-sig'), 'utf8-text-v1'
            elif suffix in MINERU_SUPPORTED_SUFFIXES:
                if parser is None:
                    parser = (self.parser_factory or create_pdf_parser)(config)
                parsed = parser.parse(data, filename=ref['filename'], canceled=canceled, on_remote_task=on_remote_task)
                content, parser_name = parsed.text, parsed.metadata.get('parser', 'mineru-cloud')
                layout = parsed.metadata.get('layout') or []
                if suffix == '.pdf':
                    pages = len(PdfReader(io.BytesIO(data), strict=True).pages)
                    if parsed.metadata.get('pageCount') != pages or set(parsed.metadata.get('pageIndices', [])) != set(range(pages)):
                        raise ValueError('PDF_PAGE_COVERAGE_UNVERIFIED')
                if parsed.metadata.get('failed_units'):
                    raise ValueError('PARTIAL_PARSE')
                # Keep original single-image scanned pages as source evidence.
                # MinerU can omit a question header; extracting these original
                # assets is local PDF handling, not another OCR/model pass.
                if suffix == '.pdf':
                    for page_index, page in enumerate(PdfReader(io.BytesIO(data), strict=True).pages):
                        if not (page.extract_text() or '').strip() and len(page.images) == 1:
                            original = page.images[0]
                            extension = Path(original.name).suffix.lower()
                            if extension in {'.jpg', '.jpeg', '.png'}:
                                name = f'exam_original_page_{page_index + 1}{extension}'
                                images[name] = base64.b64encode(original.data).decode()
                                layout.append({'type': 'image', 'page_idx': page_index,
                                               'img_path': 'images/' + name, 'original_scan': True})
                for name, value in (parsed.metadata.get('imageMapping') or {}).items():
                    if Path(name).name != name or '\\' in name:
                        raise ValueError('INVALID_PARSED_ASSET')
                    encoded = value.split(',', 1)[-1]
                    base64.b64decode(encoded, validate=True)
                    images[name] = encoded
            else:
                raise ValueError('DOCUMENT_TYPE_UNSUPPORTED')
            if not content.strip():
                raise ValueError('DOCUMENT_EMPTY')
            ParseControl(canceled=canceled).check()
            result.append({**ref, 'parser': parser_name, 'content': content, 'content_list': layout, 'images': images})
        return result
