import json
from unittest.mock import AsyncMock
import pytest
from deeptutor.tools.question import question_extractor as e

@pytest.fixture(autouse=True)
def parameters(monkeypatch):
    monkeypatch.setattr(e,'get_agent_params',lambda _: {'temperature':0.5,'max_tokens':4096})

@pytest.mark.parametrize('response', ['[]', '{"questions":[{"question_text":"ok"}],"incomplete_questions":', '{"questions":42}', 'null'])
def test_extraction_rejects_partial_or_non_object_response(monkeypatch,tmp_path,response):
    monkeypatch.setattr(e,'llm_complete',AsyncMock(return_value=response))
    with pytest.raises(ValueError,match='EXAM_EXTRACTION_INVALID_JSON'):
        e._extract_question_window('[L1] Q',[],tmp_path,'key','https://invalid','model',binding='openai')

def test_complete_fenced_response_and_larger_output_budget(monkeypatch,tmp_path):
    result={'questions':[],'incomplete_questions':[1]}
    call=AsyncMock(return_value='```json\n'+json.dumps(result)+'\n```')
    monkeypatch.setattr(e,'llm_complete',call)
    assert e._extract_question_window('[L1] Q',[],tmp_path,'key','https://invalid','model',binding='openai')==result
    assert call.call_args.kwargs['max_tokens']>=16384

def test_invalid_json_retries_once_then_reports_failure(monkeypatch,tmp_path):
    call=AsyncMock(return_value='[]');monkeypatch.setattr(e,'llm_complete',call)
    with pytest.raises(ValueError,match='expected object'):
        e.extract_questions_with_llm('Question',[],tmp_path,'key','https://invalid','model',binding='openai')
    assert call.await_count==2


def test_scan_evidence_is_sent_in_same_extraction_call(monkeypatch,tmp_path):
    from types import SimpleNamespace
    (tmp_path/'exam_original_page_1.jpg').write_bytes(b'original-scan')
    monkeypatch.setattr(e,'get_llm_config',lambda:SimpleNamespace(edu_supports_vision=True))
    call=AsyncMock(return_value='{"questions":[],"incomplete_questions":[1]}')
    monkeypatch.setattr(e,'llm_complete',call)
    e._extract_question_window('[L1] continuation',[],tmp_path,'key','https://invalid','model',binding='openai')
    assert call.await_count==1
    parts=call.call_args.kwargs['messages'][1]['content']
    assert any(part['type']=='image_url' for part in parts)


def test_scan_requires_explicit_visual_provider(monkeypatch,tmp_path):
    from types import SimpleNamespace
    (tmp_path/'exam_original_page_1.jpg').write_bytes(b'original-scan')
    monkeypatch.setattr(e,'get_llm_config',lambda:SimpleNamespace())
    with pytest.raises(ValueError,match='visual model'):
        e._extract_question_window('[L1] Q',[],tmp_path,'key','https://invalid','model',binding='openai')
