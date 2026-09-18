"""Owner-authorized document reads with immutable byte hashes and parse defects."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from app.integrations.pdf.formats import MINERU_SUPPORTED_SUFFIXES


class DocumentUnreadable(ValueError):
    def __init__(self, code, defects=()):
        self.code, self.defects = code, tuple(defects)
        super().__init__(code)


@dataclass(frozen=True)
class ParsedDocument:
    content: str
    parser: str
    source_hash: str
    units: tuple[dict, ...]
    defects: tuple[str, ...] = ()


TEXT_SUFFIXES = frozenset({'.md', '.markdown', '.txt'})
SUPPORTED_DOCUMENT_SUFFIXES = TEXT_SUFFIXES | MINERU_SUPPORTED_SUFFIXES


class DocumentParser:
    def __init__(self, mineru_factory=None):
        self.mineru_factory = mineru_factory

    def parse(self, data, *, filename):
        suffix = Path(filename).suffix.lower()
        if len(data) > 30 * 1024 * 1024: raise DocumentUnreadable('DOCUMENT_TOO_LARGE')
        source_hash = hashlib.sha256(data).hexdigest()
        defects, units = [], []
        if suffix in TEXT_SUFFIXES:
            try: content = data.decode('utf-8-sig')
            except UnicodeError as exc: raise DocumentUnreadable('DOCUMENT_ENCODING_INVALID') from exc
            parser = 'utf8-text-v1'
        elif suffix in MINERU_SUPPORTED_SUFFIXES:
            expected_pages = None
            if suffix == '.pdf':
                from io import BytesIO
                from pypdf import PdfReader
                try:
                    expected_pages = len(PdfReader(BytesIO(data), strict=True).pages)
                except Exception as exc: raise DocumentUnreadable('PDF_INVALID') from exc
            factory = self.mineru_factory
            if factory is None:
                from app.integrations.pdf import get_pdf_parser
                factory = get_pdf_parser
            try: parsed = factory().parse(data, filename=filename)
            except Exception as exc: raise DocumentUnreadable('MINERU_PARSE_FAILED') from exc
            content, parser = parsed.text, str(parsed.metadata.get('parser') or 'mineru-cloud')
            if expected_pages is not None and parsed.metadata.get('pageCount', 0) != expected_pages:
                defects.append('PAGE_COVERAGE_UNVERIFIED')
            if parsed.metadata.get('failed_units', 0): defects.append('PARTIAL_PARSE')
        else:
            raise DocumentUnreadable('DOCUMENT_TYPE_UNSUPPORTED')
        if not content or len(content.strip()) < 20: raise DocumentUnreadable('DOCUMENT_EMPTY')
        # Character spans are genuine locators; never invent pages for Office/HTML.
        for offset in range(0,len(content),4000):
            units.append({'offset_chars':offset,'content':content[offset:offset+4000]})
        return ParsedDocument(content, parser, source_hash, tuple(units), tuple(defects))


class PersonalDocumentReader:
    def __init__(self, personal_service): self.service = personal_service

    def read_bytes(self, username, document_id):
        record = self.service.get_document(owner_user_id=username, document_id=document_id)
        manager = self.service.manager_for(username)
        root = manager.get_course_dir(self.service.access_domain(username)).resolve()
        path = (root / str(record.get('path') or '')).resolve()
        if not path.is_relative_to(root) or not path.is_file(): raise PermissionError('DOCUMENT_UNAVAILABLE')
        if path.stat().st_size > 30*1024*1024: raise DocumentUnreadable('DOCUMENT_TOO_LARGE')
        return record, path.read_bytes()
