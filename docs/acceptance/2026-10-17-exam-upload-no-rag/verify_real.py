"""Real MinerU after authenticated upload, with all other model traffic forbidden."""
import json,os,tempfile,time
from pathlib import Path
from core.config import Config
os.environ['PGOPTIONS']='-c default_transaction_read_only=on'
from app.exam_generation.snapshots import SnapshotCodec
codec=SnapshotCodec();owner='exam-upload-validation'
config=codec.read(owner,codec.capture(owner))['pdf_parser']
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import exam_generations as api
from app.auth import get_current_user
from app.exam_generation.sources import GenerationSources
from app.services.personal_knowledge_service import PersonalKnowledgeService
from app.services import knowledge_document_service
import httpx,requests
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
calls=[]
def forbidden(*args,**kwargs):raise AssertionError('Unexpected indexing, embedding or other model call')
PersonalKnowledgeService.create_document=forbidden
PersonalKnowledgeService.submit_index=forbidden
knowledge_document_service.submit_index_job=forbidden
requests.Session.send=forbidden
original=httpx.Client.send
def checked(self,request,*args,**kwargs):
    if request.url.host!='testserver' and (request.url.host!='127.0.0.1' or request.url.port!=8190):forbidden()
    response=original(self,request,*args,**kwargs)
    calls.append({'method':request.method,'host':request.url.host,'path':request.url.path,'status':response.status_code})
    return response
httpx.Client.send=checked
with tempfile.TemporaryDirectory(prefix='exam-upload-validation-') as temporary:
    Config.STORAGE_ROOT=Path(temporary)
    app=FastAPI();app.include_router(api.router)
    app.dependency_overrides[get_current_user]=lambda:{'username':owner}
    sample=ROOT/'docs/acceptance/2026-10-17-deeptutor-migration-m3/sample-paper.pdf'
    started=time.monotonic()
    with TestClient(app) as client:
        response=client.post('/api/exam-generations/documents',files={'file':('paper.pdf',sample.read_bytes(),'application/pdf')})
    assert response.status_code==201,response.text
    uploaded=response.json();print('upload_http_calls',calls,flush=True)
    assert not any(c['host']!='testserver' for c in calls) # Upload itself has no model requests.
    sources=GenerationSources()
    frozen=sources.freeze(owner,[{'document_id':uploaded['document_id'],'role':'template'}])
    parsed=sources.parse(owner,frozen,config,canceled=lambda:False,on_remote_task=lambda _:None)
    assert parsed[0]['parser']=='mineru-local'
    assert not (Config.STORAGE_ROOT/'personal_knowledge').exists()
    result={'upload_status':response.status_code,'parser':parsed[0]['parser'],'characters':len(parsed[0]['content']),
            'layout_blocks':len(parsed[0]['content_list']),'seconds':round(time.monotonic()-started,2),
            'knowledge_ingestion_calls':0,'embedding_calls':0,'llm_calls':0,
            'production_business_writes':False,'http_calls':calls}
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
