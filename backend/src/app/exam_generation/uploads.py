"""Owner-scoped exam files. Uploading never schedules knowledge-base ingestion."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4

from core.config import Config
from app.integrations.pdf.formats import MINERU_SUPPORTED_SUFFIXES

MAX_UPLOAD_BYTES = 30 * 1024 * 1024
SUPPORTED_SUFFIXES = MINERU_SUPPORTED_SUFFIXES | {'.txt', '.md', '.markdown'}
_ID = re.compile(r'examdoc_[0-9a-f]{32}')


class ExamUploads:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else Path(Config.STORAGE_ROOT) / 'exam_uploads'

    def _owner_root(self, owner):
        if not isinstance(owner, str) or not owner.strip():
            raise PermissionError('DOCUMENT_UNAVAILABLE')
        return self.root / hashlib.sha256(owner.encode()).hexdigest()

    @staticmethod
    def validate_filename(filename):
        if (not filename or len(filename) > 240 or '/' in filename or '\\' in filename
                or any(ord(c) < 32 for c in filename)
                or Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES):
            raise ValueError('不支持的文件名或资料格式')

    def create(self, owner, filename, data):
        self.validate_filename(filename)
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise ValueError('资料不能为空，且不能超过 30 MB')
        folder = self._owner_root(owner)
        folder.mkdir(parents=True, exist_ok=True)
        identifier = 'examdoc_' + uuid4().hex
        record = {'document_id': identifier, 'filename': filename, 'size_bytes': len(data),
                  'source_hash': hashlib.sha256(data).hexdigest(), 'status': 'uploaded'}
        # Publish metadata and original bytes together. Client filenames never
        # become filesystem paths. The UUID identifies an immutable upload.
        with tempfile.TemporaryDirectory(prefix='.upload-', dir=folder) as temporary:
            staged = Path(temporary) / 'document'
            staged.mkdir(mode=0o700)
            (staged / 'source').write_bytes(data)
            (staged / 'metadata.json').write_text(json.dumps(record, ensure_ascii=False))
            os.replace(staged, folder / identifier)
        return record

    def read_bytes(self, owner, document_id):
        if not _ID.fullmatch(document_id):
            raise PermissionError('DOCUMENT_UNAVAILABLE')
        folder = self._owner_root(owner) / document_id
        try:
            record = json.loads((folder / 'metadata.json').read_text())
            if (folder / 'source').stat().st_size > MAX_UPLOAD_BYTES:
                raise PermissionError('DOCUMENT_UNAVAILABLE')
            data = (folder / 'source').read_bytes()
        except (OSError, ValueError) as exc:
            raise PermissionError('DOCUMENT_UNAVAILABLE') from exc
        if (record.get('document_id') != document_id or not data
                or record.get('source_hash') != hashlib.sha256(data).hexdigest()):
            raise PermissionError('SOURCE_VERSION_CHANGED')
        return record, data


class ExamSourceReader:
    def __init__(self, uploads=None):
        self.uploads = uploads or ExamUploads()

    def read_bytes(self, owner, document_id):
        if document_id.startswith('examdoc_'):
            return self.uploads.read_bytes(owner, document_id)
        # Keep previously selected personal documents readable. This is a read
        # of existing bytes; it never indexes or searches the knowledge base.
        from app.course_preparation.adapters.documents import PersonalDocumentReader
        from app.services.personal_knowledge_service import PersonalKnowledgeService
        return PersonalDocumentReader(PersonalKnowledgeService()).read_bytes(owner, document_id)
