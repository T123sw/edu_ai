import io
import json
import zipfile
from copy import deepcopy

import httpx
import pytest
from pypdf import PdfWriter

from app.integrations.pdf.base import PdfParseError
from app.integrations.pdf.mineru_cloud import ParseStopped
from app.integrations.pdf.mineru_local import LocalMinerUProvider
from app.integrations.pdf.mineru_local_artifacts import parse_bundle
from app.integrations.pdf.configuration import resolve_pdf_config, create_pdf_parser
from app.course_preparation.adapters.documents import DocumentParser


def artifact(*, indices=(0, 1), count=2, missing_image=False, extra=None):
    blocks = [
        {'type': 'text', 'content': 'This is a sufficiently long sample question.', 'bbox': [0, 0, .5, .2]},
        {'type': 'image', 'content': '![](images/figure.png)', 'image_source': 'images/figure.png',
         'captions': [{'content': 'A real diagram'}]},
        {'type': 'equation', 'content': 'x^2 + y^2'},
        {'type': 'table', 'content': '<table><tr><td>value</td></tr></table>', 'captions': []},
    ]
    middle = {'metadata': {'document': {'page_count': count}, 'producer': {'version': '4.0.12'}},
              'pages': [{'page_idx': i, 'blocks': []} for i in indices]}
    structured = {'pages': [{'page_idx': i, 'blocks': blocks if i == 0 else []} for i in indices]}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        z.writestr('markdown.md', 'Sample question with diagram.\n![](images/figure.png)')
        z.writestr('middle_json.json', json.dumps(middle))
        z.writestr('structured_content.json', json.dumps(structured))
        if not missing_image: z.writestr('images/figure.png', b'fixture-image')
        for name, data in (extra or {}).items(): z.writestr(name, data)
    return stream.getvalue()


class Server:
    def __init__(self):
        self.now = 0.; self.canceled = False; self.calls = []; self.receipts = []
        self.phase = ''; self.state = 'completed'; self.bundle = artifact()
    def sleep(self, seconds): self.now += seconds
    def handle(self, request):
        self.calls.append((request.method, request.url.path))
        if request.method == 'DELETE': return httpx.Response(200, json={'status': 'canceled'})
        assert request.extensions['timeout']['read'] <= 10-self.now
        if request.method == 'POST':
            assert request.url.params['output_formats'] == 'zip'
            assert b'original file bytes' in request.content
            if self.phase == 'submit': self.canceled = True
            return httpx.Response(202, json={'task_id': 'job_1', 'status': 'queued'})
        if request.url.path.endswith('/result'):
            if self.phase == 'download': self.canceled = True
            return httpx.Response(200, content=self.bundle)
        if self.phase == 'poll': self.canceled = True
        return httpx.Response(200, json={'status': self.state, 'files': [{'status': self.state}]})
    def run(self, callback=None):
        provider = LocalMinerUProvider(clock=lambda:self.now, sleep=self.sleep,
            client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(self.handle), **kw))
        return provider.parse(b'original file bytes', filename='notes.pdf', deadline=10,
                              canceled=lambda:self.canceled, on_remote_task=callback or self.receipts.append)


def test_full_artifacts_and_blank_page_coverage():
    run=Server(); parsed=run.run()
    assert parsed.metadata['pageIndices'] == [0,1] and parsed.metadata['pageCount']==2
    assert parsed.metadata['layout'][1]['img_path']=='images/figure.png'
    assert parsed.images == list(parsed.metadata['imageMapping'].values())
    assert parsed.formulas[0]['latex']=='x^2 + y^2' and 'value' in parsed.tables[0]['html']
    assert parsed.metadata['layout'][0]['bbox']==[0,0,.5,.2]
    assert run.receipts==[{'provider':'mineru-local','task_id':'job_1'}]
    assert parsed.metadata['adapterRevision']==LocalMinerUProvider.adapter_revision


@pytest.mark.parametrize('phase', ['submit','poll','download'])
def test_cancel_reaches_remote_task_and_never_returns_success(phase):
    run=Server(); run.phase=phase
    with pytest.raises(ParseStopped,match='CANCELED') as exc: run.run()
    assert exc.value.remote_task==run.receipts[0]
    assert run.calls[-1]==('DELETE','/v1/tasks/job_1')


def test_pre_canceled_has_no_network():
    run=Server(); run.canceled=True
    with pytest.raises(ParseStopped,match='CANCELED'):run.run()
    assert run.calls==[]


def test_deadline_polling_cancels_remote():
    run=Server(); run.state='running'
    with pytest.raises(ParseStopped,match='DEADLINE_EXCEEDED'):run.run()
    assert run.now==10 and run.calls[-1][0]=='DELETE'


def test_receipt_failure_is_not_swallowed():
    run=Server()
    def failed(_):raise RuntimeError('receipt persistence failed')
    with pytest.raises(RuntimeError,match='receipt persistence failed'):run.run(failed)
    assert run.calls[-1][0]=='DELETE'


@pytest.mark.parametrize('state',['failed','canceled','partial_completed'])
def test_partial_or_failed_task_not_accepted(state):
    run=Server();run.state=state
    with pytest.raises(PdfParseError):run.run()
    assert not any(path.endswith('/result') for _,path in run.calls)


@pytest.mark.parametrize('kwargs',[
    {'indices':(0,0)}, {'indices':(False,1)}, {'indices':(-1,0)}, {'count':1},
    {'missing_image':True}, {'extra':{'../secret.png':b'x'}},
    {'extra':{'other/figure.png':b'different'}},
])
def test_invalid_bundle_fails_closed(kwargs):
    with pytest.raises(PdfParseError):parse_bundle(artifact(**kwargs))


def test_missing_middle_page_is_not_invented():
    parsed=parse_bundle(artifact(indices=(0,2),count=3))
    assert parsed.metadata['pageIndices']==[0,2]
    writer=PdfWriter()
    for _ in range(3):writer.add_blank_page(600,800)
    buffer=io.BytesIO();writer.write(buffer)
    class Provider:
        def parse(self,*args,**kwargs):return parsed
    result=DocumentParser(mineru_factory=Provider).parse(buffer.getvalue(),filename='three.pdf')
    assert 'PAGE_COVERAGE_UNVERIFIED' in result.defects


def test_local_config_frozen_and_cloud_profile_selection(monkeypatch):
    monkeypatch.setenv('PDF_PARSER_PROVIDER','mineru-local')
    monkeypatch.setenv('PDF_MINERU_LOCAL_BASE_URL','http://127.0.0.1:8190')
    monkeypatch.setenv('PDF_MINERU_LOCAL_TIMEOUT','1800')
    monkeypatch.setenv('PDF_MINERU_CLOUD_API_KEY','cloud-secret')
    frozen=resolve_pdf_config({'_source':'environment','timeout_seconds':60})
    assert frozen['api_key']!='cloud-secret' and frozen['timeout_seconds']==1800
    monkeypatch.setenv('PDF_PARSER_PROVIDER','mineru-cloud')
    monkeypatch.setenv('PDF_MINERU_LOCAL_BASE_URL','http://wrong.invalid')
    parser=create_pdf_parser(frozen)
    assert isinstance(parser,LocalMinerUProvider) and parser.base_url=='http://127.0.0.1:8190'
    cloud=resolve_pdf_config({'provider_name':'mineru-cloud','base_url':'https://cloud.test/api/v4','_source':'user'})
    assert create_pdf_parser(cloud).provider_id=='mineru-cloud'


def test_legacy_exam_snapshot_keeps_cloud(monkeypatch):
    monkeypatch.setenv('PDF_PARSER_PROVIDER','mineru-local')
    parser=create_pdf_parser({'base_url':'https://cloud.test/api/v4','api_key':'frozen','model':'vlm'})
    assert parser.provider_id=='mineru-cloud' and parser.api_key=='frozen'


def test_public_factory_does_not_reuse_other_config(monkeypatch):
    from app.integrations import pdf
    monkeypatch.setenv('PDF_PARSER_PROVIDER','mineru-local')
    selected={'_source':'user','provider_name':'mineru-local','base_url':'http://first.test:8190'}
    monkeypatch.setattr(pdf.runtime_config_resolver,'resolve',lambda _:deepcopy(selected))
    first=pdf.get_pdf_parser()
    selected['base_url']='http://second.test:8190'
    assert pdf.get_pdf_parser().base_url != first.base_url


def test_course_document_preserves_local_receipt_and_revision():
    parsed=parse_bundle(artifact());parsed.metadata.update(parser='mineru-local',taskId='job_2',adapterRevision='mineru-local-v2')
    writer=PdfWriter();writer.add_blank_page(600,800);writer.add_blank_page(600,800)
    buffer=io.BytesIO();writer.write(buffer)
    class Provider:
        def parse(self,*a,**kw):return parsed
    result=DocumentParser(mineru_factory=Provider).parse(buffer.getvalue(),filename='paper.pdf')
    assert not result.defects and result.remote_task['provider']=='mineru-local'
    assert result.parser_revision=='mineru-local-v2' and len(result.assets)==1


def test_old_local_cache_is_stale():
    from app.course_preparation.adapters.document_store import _legacy_parse
    assert _legacy_parse({'parser':'mineru-local','defects':['PAGE_COVERAGE_UNVERIFIED']})
    assert not _legacy_parse({'parser':'mineru-local','parser_revision':'mineru-local-v2'})
    assert not _legacy_parse({'parser':'mineru-cloud'})


def test_cloud_snapshot_empty_key_does_not_use_new_secret(monkeypatch):
    monkeypatch.setenv('PDF_MINERU_CLOUD_API_KEY','later-secret')
    assert create_pdf_parser({'provider_id':'mineru-cloud','base_url':'https://cloud.test','api_key':''}).api_key==''


def test_local_profile_verification_uses_health_endpoint(monkeypatch):
    from app.api.runtime_config import _verify_provider
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        return httpx.Response(200,json={'status':'ok'},request=httpx.Request('GET',url))
    monkeypatch.setattr(httpx,'get',get)
    _verify_provider('pdf_parser',{'provider_name':'mineru-local','base_url':'http://localhost:8190/v1'})
    assert calls==['http://localhost:8190/v1/health']
