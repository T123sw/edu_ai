"""Exercise the actual batch/upload/result protocol without external requests."""
import io
import json
import zipfile

import httpx
import pytest

from app.integrations.pdf import mineru_cloud
from app.integrations.pdf.base import PdfParseError
from app.integrations.pdf.formats import MINERU_SUPPORTED_SUFFIXES


@pytest.mark.parametrize('suffix', sorted(MINERU_SUPPORTED_SUFFIXES))
def test_batch_preserves_format_and_selects_html_model(monkeypatch, suffix):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        z.writestr('result/full.md', '# Learning notes\nTool use, state, memory and evaluation.')
        z.writestr('result/content_list.json', '[{"type":"text","page_idx":0}]')
    requests = []
    def respond(request):
        requests.append(request)
        if request.url.path == '/api/v4/file-urls/batch':
            body = json.loads(request.content)
            assert body['files'] == [{'name': '讲义'+suffix}]
            assert body['model_version'] == ('MinerU-HTML' if suffix == '.html' else 'vlm')
            return httpx.Response(200, json={'code':0,'data':{'batch_id':'batch','file_urls':['https://upload.test/file']}})
        if request.method == 'PUT':
            assert request.content == b'original bytes'
            assert 'authorization' not in request.headers and 'content-type' not in request.headers
            return httpx.Response(200)
        if request.url.path == '/api/v4/extract-results/batch/batch':
            return httpx.Response(200,json={'code':0,'data':{'extract_result':[{'file_name':'讲义'+suffix,'state':'done','full_zip_url':'https://result.test/file.zip'}]}})
        assert request.url.host == 'result.test'
        return httpx.Response(200, content=output.getvalue())
    client = httpx.Client
    monkeypatch.setattr(mineru_cloud.httpx, 'Client', lambda **kw: client(transport=httpx.MockTransport(respond), **kw))
    monkeypatch.setattr(mineru_cloud.time, 'sleep', lambda _: None)
    parsed = mineru_cloud.MinerUCloudProvider(api_key='test').parse(b'original bytes', filename='讲义'+suffix.upper())
    assert parsed.metadata['fileName'] == '讲义'+suffix
    assert parsed.metadata['parser'] == 'mineru-cloud'
    assert parsed.metadata['pageCount'] == 1
    assert 'Tool use' in parsed.text and len(requests) == 4


def test_long_filename_keeps_extension_and_unsupported_is_rejected():
    assert mineru_cloud._sanitize_filename('x'*300+'.DOCX').endswith('.docx')
    assert len(mineru_cloud._sanitize_filename('x'*300+'.DOCX')) <= 240
    assert mineru_cloud._sanitize_filename('../notes.pptx') == 'notes.pptx'
    with pytest.raises(PdfParseError, match='unsupported file type'):
        mineru_cloud._sanitize_filename('archive.zip')
