"""Owner-authorized document reads with immutable byte hashes and parse defects."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


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


class DocumentParser:
    def __init__(self, pdf_factory=None, word_reader=None, doc_converter=None):
        self.pdf_factory, self.word_reader, self.doc_converter = pdf_factory, word_reader, doc_converter

    def parse(self, data, *, filename):
        suffix = Path(filename).suffix.lower()
        if len(data) > 30 * 1024 * 1024: raise DocumentUnreadable('DOCUMENT_TOO_LARGE')
        source_hash = hashlib.sha256(data).hexdigest()
        defects, units = [], []
        antiword = os.getenv('PREPARATION_ANTIWORD_BIN') or shutil.which('antiword')
        if suffix == '.doc' and not self.doc_converter and not (shutil.which('libreoffice') or shutil.which('soffice')) and antiword:
            with tempfile.TemporaryDirectory(prefix='preparation-doc-') as tmp:
                path=Path(tmp)/'source.doc'; path.write_bytes(data)
                env=dict(os.environ)
                mappings=os.getenv('PREPARATION_ANTIWORD_MAPS')
                if mappings: env['ANTIWORDHOME']=mappings
                try:
                    result=subprocess.run([antiword,'-m','UTF-8.txt',str(path)],capture_output=True,check=True,timeout=60,env=env)
                    text=result.stdout.decode('utf-8')
                except (OSError,subprocess.SubprocessError,UnicodeError) as exc:
                    raise DocumentUnreadable('DOC_PARSE_FAILED') from exc
                parsed=self.parse(text.encode(),filename='converted.txt')
                return ParsedDocument(parsed.content,'antiword-text-v1',source_hash,parsed.units,
                    ('DOC_PARSER_WARNING',) if result.stderr.strip() else ())
        if suffix in ('.md','.markdown','.txt'):
            try: content = data.decode('utf-8-sig')
            except UnicodeError as exc: raise DocumentUnreadable('DOCUMENT_ENCODING_INVALID') from exc
            parser = 'utf8-text-v1'
        elif suffix == '.pdf':
            from io import BytesIO
            from pypdf import PdfReader
            try:
                expected_pages = len(PdfReader(BytesIO(data), strict=True).pages)
            except Exception as exc: raise DocumentUnreadable('PDF_INVALID') from exc
            factory = self.pdf_factory
            if factory is None:
                from app.integrations.pdf import get_pdf_parser
                factory = get_pdf_parser
            try: parsed = factory().parse(data, filename=filename)
            except Exception as exc: raise DocumentUnreadable('PDF_PARSE_FAILED') from exc
            content, parser = parsed.text, str(parsed.metadata.get('parser') or 'mineru-cloud')
            actual_pages = parsed.metadata.get('pageCount', 0)
            if actual_pages != expected_pages: defects.append('PAGE_COVERAGE_UNVERIFIED')
            if parsed.metadata.get('failed_units', 0): defects.append('PARTIAL_PARSE')
        elif suffix in ('.docx','.doc'):
            with tempfile.TemporaryDirectory(prefix='preparation-document-') as tmp:
                path = Path(tmp) / ('source'+suffix)
                path.write_bytes(data)
                if suffix == '.doc':
                    if self.doc_converter:
                        path = Path(self.doc_converter(path, Path(tmp)))
                    else:
                        executable = shutil.which('libreoffice') or shutil.which('soffice')
                        if not executable: raise DocumentUnreadable('DOC_CONVERTER_UNAVAILABLE')
                        try:
                            subprocess.run([executable, '-env:UserInstallation='+ (Path(tmp)/'profile').as_uri(),
                                '--headless','--convert-to','docx','--outdir',tmp,str(path)],
                                capture_output=True, check=True, timeout=60)
                        except (OSError, subprocess.SubprocessError) as exc: raise DocumentUnreadable('DOC_CONVERSION_FAILED') from exc
                        path = path.with_suffix('.docx')
                try:
                    with zipfile.ZipFile(path) as archive:
                        if sum(i.file_size for i in archive.infolist()) > 60 * 1024 * 1024:
                            raise DocumentUnreadable('DOCUMENT_TOO_LARGE')
                        if any(n.startswith('word/media/') for n in archive.namelist()):
                            defects.append('EMBEDDED_MEDIA_NOT_PARSED')
                    reader = self.word_reader
                    if reader is None:
                        from modules.rag_v2.rag_main.system import DocumentProcessor
                        reader = lambda p: DocumentProcessor._read_docx_text(None, str(p))
                    content = reader(path)
                except DocumentUnreadable: raise
                except Exception as exc: raise DocumentUnreadable('WORD_PARSE_FAILED') from exc
            parser = 'rag-docx-text-v1' if suffix == '.docx' else 'libreoffice+rag-docx-text-v1'
        else:
            raise DocumentUnreadable('DOCUMENT_TYPE_UNSUPPORTED')
        if not content or len(content.strip()) < 20: raise DocumentUnreadable('DOCUMENT_EMPTY')
        # Character spans are genuine locators; DOCX paragraphs are not invented pages.
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
