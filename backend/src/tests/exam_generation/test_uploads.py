import io
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.api import exam_generations as api
from app.auth import get_current_user
from app.exam_generation.uploads import ExamUploads
from app.exam_generation.sources import GenerationSources
from app.integrations.pdf.base import ParsedPdf
from core.config import Config


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(Config,'STORAGE_ROOT',tmp_path)
    # These operations are forbidden throughout the exam upload/read/parse tests.
    from app.services.personal_knowledge_service import PersonalKnowledgeService
    from app.services import knowledge_document_service
    def forbidden(*args,**kwargs):pytest.fail('Exam upload invoked knowledge-base ingestion')
    monkeypatch.setattr(PersonalKnowledgeService,'create_document',forbidden)
    monkeypatch.setattr(PersonalKnowledgeService,'submit_index',forbidden)
    monkeypatch.setattr(knowledge_document_service,'submit_index_job',forbidden)
    return ExamUploads()


def client_for(owner='alice'):
    app=FastAPI();app.include_router(api.router)
    app.dependency_overrides[get_current_user]=lambda:{'username':owner}
    return TestClient(app)


def paper():
    writer=PdfWriter();writer.add_blank_page(600,800)
    stream=io.BytesIO();writer.write(stream);return stream.getvalue()


def test_upload_to_default_source_reader_only_calls_parser(uploads):
    payload=paper()
    with client_for() as client:
        response=client.post('/api/exam-generations/documents',files={'file':('试卷.pdf',payload,'application/pdf')})
    assert response.status_code==201
    record=response.json();assert 'path' not in record and 'job' not in record
    calls=[]
    class Parser:
        def parse(self,data,**kwargs):
            calls.append((data,kwargs['filename']))
            return ParsedPdf(text='A complete source question with four choices.',metadata={
                'parser':'mineru-local','pageCount':1,'pageIndices':[0],
                'layout':[{'type':'text','page_idx':0,'text':'Original question'}]})
    sources=GenerationSources(parser_factory=lambda config:Parser())
    refs=sources.freeze('alice',[{'document_id':record['document_id'],'role':'template'}])
    result=sources.parse('alice',refs,{},canceled=lambda:False,on_remote_task=lambda t:None)
    assert calls==[(payload,'试卷.pdf')] and result[0]['parser']=='mineru-local'
    assert result[0]['content_list'][0]['page_idx']==0
    assert not (Config.STORAGE_ROOT/'personal_knowledge').exists()
    assert not (Config.STORAGE_ROOT/'vector_db').exists()


def test_cross_owner_and_file_replacement_rejected(uploads):
    record=uploads.create('alice','paper.pdf',paper());doc=record['document_id']
    with pytest.raises(PermissionError):GenerationSources().freeze('bob',[{'document_id':doc,'role':'template'}])
    refs=GenerationSources().freeze('alice',[{'document_id':doc,'role':'template'}])
    next(uploads.root.glob('*/'+doc+'/source')).write_bytes(b'changed')
    with pytest.raises(PermissionError):GenerationSources().parse('alice',refs,{},canceled=lambda:False,on_remote_task=lambda t:None)


@pytest.mark.parametrize('filename,data',[('bad.zip',b'zip'),('../paper.pdf',b'x'),('empty.pdf',b'')])
def test_invalid_upload_does_not_publish_files(uploads,filename,data):
    with client_for() as client:
        assert client.post('/api/exam-generations/documents',files={'file':(filename,data)}).status_code==422
    assert not list(uploads.root.glob('*/examdoc_*'))


def test_size_bound(uploads,monkeypatch):
    monkeypatch.setattr(api,'MAX_UPLOAD_BYTES',10)
    with client_for() as client:
        assert client.post('/api/exam-generations/documents',files={'file':('paper.pdf',b'x'*11)}).status_code==413
    assert not list(uploads.root.glob('*/examdoc_*'))


def test_no_upload_without_authentication(uploads):
    app=FastAPI();app.include_router(api.router)
    with TestClient(app) as client:
        assert client.post('/api/exam-generations/documents',files={'file':('paper.pdf',paper())}).status_code in (401,403)
    assert not uploads.root.exists()


@pytest.mark.parametrize('identifier',['examdoc_../escape','examdoc_'+'a'*32+'/..','examdoc_unknown'])
def test_malformed_exam_id_never_uses_legacy_reader(uploads,identifier):
    with pytest.raises(PermissionError):GenerationSources().freeze('alice',[{'document_id':identifier,'role':'context'}])
