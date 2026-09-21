from io import BytesIO
import json
import zipfile
import httpx
import pytest
from app.integrations.pdf.mineru_cloud import MinerUCloudProvider, ParseStopped
from app.course_preparation.adapters.documents import DocumentParser


@pytest.fixture
def parse_transport():
    class Run:
        now = 0.
        canceled = False
        cancel_at = None
        calls = []
        tasks = []
        def sleep(self, seconds): self.now += seconds
        def handle(self, request):
            self.calls.append(request)
            assert request.extensions['timeout']['read'] <= 10-self.now
            path = request.url.path
            if path.endswith('/file-urls/batch'):
                data = {'batch_id':'remote-1','file_urls':['https://upload.test/file']}
            elif request.method == 'PUT':
                if self.cancel_at == 'upload': self.canceled = True
                return httpx.Response(200)
            elif '/extract-results/' in path:
                if self.cancel_at == 'poll': self.canceled = True
                data = {'extract_result':[{'file_name':'notes.docx','state':'done','full_zip_url':'https://result.test/result.zip'}]}
            else:
                stream=BytesIO()
                with zipfile.ZipFile(stream,'w') as z:
                    z.writestr('full.md','Document has a genuine table and diagram.\n|A|B|\n|1|2|')
                    z.writestr('content_list.json',json.dumps([{'type':'table','page_idx':0}]))
                if self.cancel_at == 'download': self.canceled = True
                return httpx.Response(200,content=stream.getvalue())
            return httpx.Response(200,json={'code':0,'data':data})
        def run(self):
            provider=MinerUCloudProvider(api_key='test',clock=lambda:self.now,sleep=self.sleep,
                client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(self.handle),**kw))
            return provider.parse(b'fixture',filename='notes.docx',deadline=10,
                canceled=lambda:self.canceled,on_remote_task=self.tasks.append)
    return Run()


def test_cancel_after_first_poll_stops_before_download(parse_transport):
    run=parse_transport; run.cancel_at='poll'
    with pytest.raises(ParseStopped) as error: run.run()
    assert error.value.code == 'CANCELED'
    assert sum('/extract-results/' in r.url.path for r in run.calls)==1
    assert len(run.calls)==3
    assert error.value.remote_task==run.tasks[0]=={'provider':'mineru-cloud','task_id':'remote-1'}


@pytest.mark.parametrize('phase, calls',[('upload',2),('download',4)])
def test_cancel_never_returns_success(parse_transport,phase,calls):
    run=parse_transport; run.cancel_at=phase
    with pytest.raises(ParseStopped,match='CANCELED'): run.run()
    assert len(run.calls)==calls


def test_cancel_before_submission(parse_transport):
    run=parse_transport; run.canceled=True
    with pytest.raises(ParseStopped,match='CANCELED'): run.run()
    assert not run.calls


def test_deadline_checked_without_real_wait(parse_transport):
    run=parse_transport
    run.now=10
    with pytest.raises(ParseStopped,match='DEADLINE_EXCEEDED'): run.run()
    assert not run.calls


def test_normal_office_has_actual_layout_no_invented_document_pages(parse_transport):
    parsed=parse_transport.run()
    assert parsed.metadata['taskId']=='remote-1'
    assert parsed.metadata['pageIndices']==[0]
    assert parsed.tables==[{'page':0,'caption':None}]


def test_document_adapter_preserves_cancellation():
    class Provider:
        def parse(self,*a,**kw): raise ParseStopped('CANCELED',{'task_id':'remote-2'})
    with pytest.raises(ParseStopped) as error:
        DocumentParser(mineru_factory=Provider).parse(b'fixture',filename='slides.pptx')
    assert error.value.remote_task['task_id']=='remote-2'


def test_canceled_text_never_returns_success():
    with pytest.raises(ParseStopped,match='CANCELED'):
        DocumentParser().parse(b'Long enough text document for validation',filename='notes.txt',canceled=lambda:True)


def test_retry_sleep_and_poll_deadline_are_bounded():
    from app.integrations.pdf.mineru_cloud import ParseControl, _retry
    now=[0.]; calls=[]
    control=ParseControl(deadline=.3,clock=lambda:now[0],sleep=lambda seconds:now.__setitem__(0,now[0]+seconds))
    def fail(): calls.append(1); raise httpx.ConnectError('temporary')
    with pytest.raises(ParseStopped,match='DEADLINE_EXCEEDED'):
        _retry(fail,'retry',control=control)
    assert calls==[1] and now[0]==.3


def test_cancel_after_parse_does_not_cache_success(db_engine):
    from app.database.models import PreparationDocumentVersion
    from app.course_preparation.adapters.document_store import DocumentStore
    from app.course_preparation.schemas import UploadRef
    from sqlalchemy.orm import Session
    PreparationDocumentVersion.__table__.create(db_engine)
    flag=[False]
    class Reader:
        def read_bytes(self,*a): return {'filename':'notes.txt'},b'A text document with enough actual bytes for parsing.'
    class Parser:
        def parse(self,data,**kw):
            result=DocumentParser().parse(data,filename=kw['filename'])
            flag[0]=True
            return result
    store=DocumentStore(db_engine,Reader(),Parser())
    ref=UploadRef(**store.register('alice','doc'))
    with pytest.raises(ParseStopped,match='CANCELED'):
        store.parse_controlled('alice',ref,canceled=lambda:flag[0])
    with Session(db_engine) as session:
        assert session.get(PreparationDocumentVersion,('alice','doc',1)).parsed is None


def test_real_task_control_records_remote_reference_and_cancel(runtime_engine):
    from tests.course_preparation.test_runtime_foundation import repo, request
    from app.course_preparation.adapters.documents import controlled_parse
    from app.course_preparation.schemas import UploadRef
    repository=repo(runtime_engine)
    task=repository.submit('alice',request())
    context=repository.claim('worker',preparation_id=task['preparation_id'])
    checkpoint={}
    class Documents:
        def parse_controlled(self,owner,ref,**controls):
            from app.integrations.pdf.mineru_cloud import ParseControl
            control=ParseControl(**controls)
            control.submitted('real-submission-fixture')
            repository.cancel('alice',task['preparation_id'])
            control.check()
    with pytest.raises(ParseStopped,match='CANCELED'):
        controlled_parse(Documents(),'alice',UploadRef(document_id='doc',version=1),
                         context=context,repository=repository,checkpoint=checkpoint)
    assert checkpoint['parse_tasks'][0]['task_id']=='real-submission-fixture'
