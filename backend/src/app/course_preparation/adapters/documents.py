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
    assets: tuple[dict, ...] = ()
    layout: tuple[dict, ...] = ()
    remote_task: dict | None = None


TEXT_SUFFIXES = frozenset({'.md', '.markdown', '.txt'})
SUPPORTED_DOCUMENT_SUFFIXES = TEXT_SUFFIXES | MINERU_SUPPORTED_SUFFIXES


class DocumentParser:
    def __init__(self, mineru_factory=None):
        self.mineru_factory = mineru_factory

    def parse(self, data, *, filename, deadline=None, canceled=None, on_remote_task=None):
        from app.integrations.pdf.mineru_cloud import ParseControl
        control = ParseControl(deadline=deadline, canceled=canceled, on_remote_task=on_remote_task)
        control.check()
        suffix = Path(filename).suffix.lower()
        if len(data) > 30 * 1024 * 1024: raise DocumentUnreadable('DOCUMENT_TOO_LARGE')
        source_hash = hashlib.sha256(data).hexdigest()
        defects, units, assets, layout = [], [], [], []
        remote_task = None
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
            options = {k:v for k,v in {'deadline':deadline, 'canceled':canceled,
                       'on_remote_task':on_remote_task}.items() if v is not None}
            try:
                parsed = factory().parse(data, filename=filename, **options)
            except Exception as exc:
                if getattr(exc, 'code', '') in ('CANCELED', 'DEADLINE_EXCEEDED'):
                    raise
                error = DocumentUnreadable('MINERU_PARSE_FAILED')
                error.remote_task = getattr(exc, 'remote_task', None)
                raise error from exc
            control.check()
            if parsed.metadata.get('taskId'):
                remote_task = {'provider':'mineru-cloud','task_id':parsed.metadata['taskId']}
            for index, value in enumerate(parsed.images):
                import base64
                try:
                    header, encoded = value.split(',', 1)
                    payload = base64.b64decode(encoded, validate=True)
                except (ValueError, TypeError):
                    continue
                assets.append({'asset_id':f'asset_{index}', 'content_sha256':hashlib.sha256(payload).hexdigest(),
                               'mime_type':header.removeprefix('data:').split(';')[0], 'data':value})
            layout = parsed.metadata.get('layout') or []
            content, parser = parsed.text, str(parsed.metadata.get('parser') or 'mineru-cloud')
            if expected_pages is not None and parsed.metadata.get('pageCount', 0) != expected_pages:
                defects.append('PAGE_COVERAGE_UNVERIFIED')
            if expected_pages is not None and 'pageIndices' in parsed.metadata and set(parsed.metadata['pageIndices']) != set(range(expected_pages)):
                if 'PAGE_COVERAGE_UNVERIFIED' not in defects: defects.append('PAGE_COVERAGE_UNVERIFIED')
            if parsed.metadata.get('failed_units', 0): defects.append('PARTIAL_PARSE')
        else:
            raise DocumentUnreadable('DOCUMENT_TYPE_UNSUPPORTED')
        if not content or len(content.strip()) < 20: raise DocumentUnreadable('DOCUMENT_EMPTY')
        # Character spans are genuine locators; never invent pages for Office/HTML.
        for offset in range(0,len(content),4000):
            units.append({'offset_chars':offset,'content':content[offset:offset+4000]})
        control.check()
        return ParsedDocument(content, parser, source_hash, tuple(units), tuple(defects),
                              tuple(assets), tuple(layout), remote_task)


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


def controlled_parse(documents, owner, ref, *, context, repository, checkpoint):
    """Use live server authority without putting callbacks in a checkpoint."""
    if not hasattr(documents, 'parse_controlled'):
        return documents.parse(owner, ref)  # Compatibility for legacy ports.
    import time
    from datetime import datetime, timezone
    deadline = None
    if context.deadline:
        deadline = time.monotonic() + (datetime.fromisoformat(context.deadline)-datetime.now(timezone.utc)).total_seconds()
    def canceled():
        record = repository.get(owner_user_id=owner, preparation_id=context.preparation_id)
        if record.status == 'canceled':
            return True
        repository.heartbeat(context)
        return False
    def submitted(task):
        receipts = checkpoint.setdefault('parse_tasks', [])
        receipts.append({**task, 'document_id':ref.document_id, 'version':ref.version})
        repository.checkpoint(context, checkpoint)
    return documents.parse_controlled(owner, ref, deadline=deadline, canceled=canceled, on_remote_task=submitted)
