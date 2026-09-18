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


def test_utf8_chinese_spans_and_docx_reuse_existing_reader():
    text='学习 Agent 的状态和工具调用。'*700
    parsed=DocumentParser().parse(text.encode(),filename='资料.md')
    assert ''.join(u['content'] for u in parsed.units)==text
    assert parsed.units[1]['offset_chars']==4000
    word=DocumentParser().parse(docx_bytes(),filename='讲义.docx')
    assert '开发面试' in word.content
    assert word.defects==()


def test_doc_conversion_is_explicit_and_failures_are_not_success():
    def convert(path,root):
        target=root/'converted.docx'; target.write_bytes(docx_bytes()); return target
    parsed=DocumentParser(doc_converter=convert).parse(b'legacy fixture',filename='讲义.doc')
    assert 'Agent' in parsed.content
    with pytest.raises(DocumentUnreadable): DocumentParser().parse(b'broken',filename='scan.pdf')
    with pytest.raises(DocumentUnreadable): DocumentParser().parse(b'broken',filename='资料.docx')


def test_pdf_partial_coverage_is_recorded_and_empty_scan_rejected():
    from pypdf import PdfWriter
    from app.integrations.pdf.base import ParsedPdf
    pdf=PdfWriter(); pdf.add_blank_page(300,400); pdf.add_blank_page(300,400)
    stream=BytesIO(); pdf.write(stream); data=stream.getvalue()
    class Parser:
        def parse(self,*a,**kw): return ParsedPdf(text='Only first page with enough text for the fixture.',metadata={'pageCount':1})
    result=DocumentParser(pdf_factory=Parser).parse(data,filename='partial.pdf')
    assert result.defects==('PAGE_COVERAGE_UNVERIFIED',)
    class Empty:
        def parse(self,*a,**kw): return ParsedPdf(text='',metadata={'pageCount':2})
    with pytest.raises(DocumentUnreadable,match='DOCUMENT_EMPTY'):
        DocumentParser(pdf_factory=Empty).parse(data,filename='empty.pdf')


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
