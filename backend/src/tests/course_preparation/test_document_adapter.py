from io import BytesIO
from pathlib import Path
import zipfile
import pytest
from app.course_preparation.adapters.documents import DocumentParser, DocumentUnreadable


def docx_bytes(text='课程讲义介绍 Agent 工具调用、记忆、状态管理以及开发面试准备。'):
    output=BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+text+'</w:t></w:r></w:p></w:body></w:document>')
    return output.getvalue()


def test_utf8_chinese_spans_stay_local():
    text='学习 Agent 的状态和工具调用。'*700
    def no_remote(): pytest.fail('text must not call MinerU')
    parsed=DocumentParser(mineru_factory=no_remote).parse(text.encode(),filename='资料.md')
    assert ''.join(u['content'] for u in parsed.units)==text
    assert parsed.units[1]['offset_chars']==4000


@pytest.mark.parametrize('suffix', ['.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
                                  '.png', '.jpg', '.jpeg', '.jp2', '.webp', '.gif', '.bmp', '.html'])
def test_supported_formats_use_mineru_with_original_bytes(suffix):
    from app.integrations.pdf.base import ParsedPdf
    data = docx_bytes() if suffix == '.docx' else b'format routing fixture'
    calls = []
    class MinerU:
        def parse(self, payload, *, filename):
            calls.append((payload, filename))
            return ParsedPdf(text='课程讲义介绍 Agent 工具调用、记忆、状态管理以及开发面试准备。', metadata={'parser':'mineru-cloud'})
    parsed = DocumentParser(mineru_factory=MinerU).parse(data, filename='讲义'+suffix)
    assert calls == [(data, '讲义'+suffix)]
    assert parsed.parser == 'mineru-cloud' and parsed.defects == ()
    import hashlib
    assert parsed.source_hash == hashlib.sha256(data).hexdigest()


def test_mineru_failure_does_not_fall_back_to_local_word_reader():
    class Broken:
        def parse(self, *args, **kwargs): raise RuntimeError('upstream failed')
    with pytest.raises(DocumentUnreadable, match='MINERU_PARSE_FAILED'):
        DocumentParser(mineru_factory=Broken).parse(docx_bytes(),filename='资料.docx')
    with pytest.raises(DocumentUnreadable, match='PDF_INVALID'):
        DocumentParser(mineru_factory=Broken).parse(b'broken',filename='scan.pdf')
    with pytest.raises(DocumentUnreadable, match='DOCUMENT_TYPE_UNSUPPORTED'):
        DocumentParser(mineru_factory=Broken).parse(b'broken',filename='archive.zip')


def test_pdf_partial_coverage_is_recorded_and_empty_scan_rejected():
    from pypdf import PdfWriter
    from app.integrations.pdf.base import ParsedPdf
    pdf=PdfWriter(); pdf.add_blank_page(300,400); pdf.add_blank_page(300,400)
    stream=BytesIO(); pdf.write(stream); data=stream.getvalue()
    class Parser:
        def parse(self,*a,**kw): return ParsedPdf(text='Only first page with enough text for the fixture.',metadata={'pageCount':1})
    result=DocumentParser(mineru_factory=Parser).parse(data,filename='partial.pdf')
    assert result.defects==('PAGE_COVERAGE_UNVERIFIED',)
    class Empty:
        def parse(self,*a,**kw): return ParsedPdf(text='',metadata={'pageCount':2})
    with pytest.raises(DocumentUnreadable,match='DOCUMENT_EMPTY'):
        DocumentParser(mineru_factory=Empty).parse(data,filename='empty.pdf')


def test_registered_versions_reject_changed_or_revoked_sources(db_engine):
    from app.database.models import PreparationDocumentVersion
    from app.course_preparation.adapters.document_store import DocumentStore
    from app.course_preparation.schemas import UploadRef
    PreparationDocumentVersion.__table__.create(db_engine)
    class Reader:
        data=('课程讲义说明工具选择、状态转换和 Agent 开发。'*30).encode()
        denied=False
        def read_bytes(self,owner,doc):
            if owner!='alice' or self.denied: raise PermissionError('denied')
            return {'filename':'notes.md'},self.data
    reader=Reader(); store=DocumentStore(db_engine,reader)
    ref=UploadRef(**store.register('alice','doc'))
    assert store.register('alice','doc')['version']==1
    assert store.read('alice',ref)['content']
    with pytest.raises(PermissionError): store.read('bob',ref)
    reader.data+=b'changed'
    with pytest.raises(PermissionError): store.read('alice',ref)
    new=UploadRef(**store.register('alice','doc'))
    assert new.version==2
    reader.denied=True
    with pytest.raises(PermissionError): store.read('alice',new)


def test_legacy_word_cache_is_reparsed_once_with_mineru(db_engine):
    from sqlalchemy.orm import Session
    from app.database.models import PreparationDocumentVersion
    from app.course_preparation.adapters.document_store import DocumentStore
    from app.course_preparation.schemas import UploadRef
    from app.integrations.pdf.base import ParsedPdf
    PreparationDocumentVersion.__table__.create(db_engine)
    class Reader:
        def read_bytes(self, owner, doc): return {'filename':'notes.docx'}, docx_bytes()
    calls = []
    class MinerU:
        def parse(self, data, *, filename):
            calls.append(filename)
            return ParsedPdf(text='MinerU parsed full document including the table and image captions.', metadata={'parser':'mineru-cloud'})
    store = DocumentStore(db_engine, Reader(), DocumentParser(mineru_factory=MinerU))
    ref = UploadRef(**store.register('alice', 'word'))
    with Session(db_engine) as session, session.begin():
        row = session.get(PreparationDocumentVersion, ('alice','word',ref.version))
        row.parsed = {'parser':'rag-docx-text-v1','content':'old incomplete text'}
    assert store.parse('alice', ref)['parser'] == 'mineru-cloud'
    assert store.parse('alice', ref)['parser'] == 'mineru-cloud'
    assert calls == ['notes.docx']


def test_upload_api_accepts_mineru_formats_and_rejects_archives(monkeypatch):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import course_preparations as api
    from app.course_preparation.adapters import document_store, memory
    from app.services import personal_knowledge_service
    saved = []
    class Personal:
        def create_document(self, **kw):
            saved.append(kw)
            return {'id':'uploaded'}
    class Store:
        def __init__(self, *args): pass
        def register(self, owner, doc): return {'document_id':doc,'version':1}
    monkeypatch.setattr(personal_knowledge_service, 'PersonalKnowledgeService', Personal)
    monkeypatch.setattr(document_store, 'DocumentStore', Store)
    monkeypatch.setattr(memory.PreparationMemory, 'subject', lambda self, owner: owner)
    app = FastAPI(); app.include_router(api.router)
    app.state.preparation_service = SimpleNamespace(repository=SimpleNamespace(engine=None))
    app.dependency_overrides[api.owner] = lambda: 'alice'
    with TestClient(app) as client:
        for ext in ('.docx', '.pptx', '.xlsx', '.png', '.html', '.markdown'):
            response = client.post('/api/course-preparations/uploads', files={'file':('notes'+ext,b'original upload')})
            assert response.status_code == 201, response.text
            assert saved[-1]['filename'] == 'notes'+ext
            assert saved[-1]['file_data'] == b'original upload'
        assert client.post('/api/course-preparations/uploads', files={'file':('bad.zip',b'zip')}).status_code == 422
    assert len(saved) == 6
